'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, RefreshCw } from 'lucide-react';

interface ModelPricing {
  input_per_million_cents: number;
  output_per_million_cents: number;
  source: string;
}

interface ProviderModel {
  id: string;
  capabilities: string[];
  context_window: number | null;
  max_output_tokens: number | null;
  supports_streaming: boolean;
  supports_function_calling: boolean;
  tasks: string[] | null;
  pricing: ModelPricing;
}

interface ProviderHealth {
  provider_id: string;
  display_name: string;
  healthy: boolean;
  last_check_at: string | null;
  last_healthy_at: string | null;
  error: string | null;
  attestation_details: {
    intel_tdx_verified: boolean;
    gpu_attestation_verified: boolean;
    nonce_binding_verified: boolean;
    signing_address: string | null;
  } | null;
  // Pricing from TOKEN_STATS_PLAN.md
  pricing: {
    source: string;
    last_sync_at: string | null;
    model_count: number;
  } | null;
  models: ProviderModel[];
}

export default function ProvidersTab() {
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProviders();
    const interval = setInterval(fetchProviders, 30000);
    return () => clearInterval(interval);
  }, []);

  async function fetchProviders() {
    try {
      setError(null);
      const data = await apiClient.get('/api-internal/v1/providers/health');
      setProviders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch providers');
    } finally {
      setLoading(false);
    }
  }

  async function verifyProvider(providerId: string) {
    setVerifying(providerId);
    try {
      await apiClient.post(`/api-internal/v1/providers/${providerId}/verify`);
      await fetchProviders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setVerifying(null);
    }
  }

  function formatTimeAgo(dateStr: string | null): string {
    if (!dateStr) return 'Never';
    const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  // Get currency symbol based on provider ID
  function getProviderCurrency(providerId: string): { symbol: string; code: string } {
    // PrivateMode uses EUR, others use USD
    if (providerId === 'privatemode') {
      return { symbol: '€', code: 'EUR' };
    }
    return { symbol: '$', code: 'USD' };
  }

  function formatPricing(cents: number, providerId: string): string {
    // Convert cents per million to currency units per million
    const { symbol, code } = getProviderCurrency(providerId);
    const amount = cents / 100;

    // Format based on currency
    if (code === 'EUR') {
      // European format: €1,50
      return `${symbol}${amount.toFixed(2).replace('.', ',')}`;
    }
    // US format: $1.50
    return `${symbol}${amount.toFixed(2)}`;
  }

  // Get mode badges for a model (filter out tee/attestation as they're assumed)
  function getModelModes(model: ProviderModel): string[] {
    const modes: string[] = [];

    // Check tasks array
    if (model.tasks && Array.isArray(model.tasks)) {
      if (model.tasks.includes('generate')) modes.push('generate');
      if (model.tasks.includes('embed') || model.tasks.includes('embedding')) modes.push('embed');
      if (model.tasks.includes('vision')) modes.push('vision');
      if (model.tasks.includes('transcribe')) modes.push('transcribe');
    }

    // Check function calling support
    if (model.supports_function_calling) modes.push('tool_calling');

    return modes;
  }

  // Get badge style for mode
  function getModeBadgeStyle(mode: string): string {
    const styles: Record<string, string> = {
      'generate': 'bg-info-soft text-info-soft-foreground',
      'tool_calling': 'bg-muted text-muted-foreground',
      'vision': 'bg-success-soft text-success-soft-foreground',
      'transcribe': 'bg-warning-soft text-warning-soft-foreground',
      'embed': 'bg-info-soft text-info-soft-foreground',
    };
    return styles[mode] || '';
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Inference Providers</h2>
          <p className="text-muted-foreground text-sm">
            Confidential AI providers with TEE attestation.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={fetchProviders}
          disabled={loading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 rounded-md text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {providers.map((provider) => (
          <Card key={provider.provider_id}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg">{provider.display_name}</CardTitle>
              {provider.healthy ? (
                <Badge variant="success">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Healthy
                </Badge>
              ) : (
                <Badge variant="destructive">
                  <XCircle className="w-3 h-3 mr-1" />
                  Unhealthy
                </Badge>
              )}
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm text-muted-foreground">
                Last checked: {formatTimeAgo(provider.last_check_at)}
              </div>

              {/* Pricing info (from TOKEN_STATS_PLAN.md) */}
              {provider.pricing && (
                <div className="text-sm text-muted-foreground">
                  Pricing: {provider.pricing.source === 'api_sync' ? (
                    <>Auto-sync (last synced {formatTimeAgo(provider.pricing.last_sync_at)}, {provider.pricing.model_count} models)</>
                  ) : (
                    <>Manual ({provider.pricing.model_count} models)</>
                  )}
                </div>
              )}

              {/* Error message */}
              {!provider.healthy && provider.error && (
                <div className="p-3 bg-destructive/10 rounded-md text-sm text-destructive">
                  {provider.error}
                </div>
              )}

              {/* Available Models */}
              {provider.models && provider.models.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Available Models ({provider.models.length})</h4>
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {provider.models.map((model) => (
                      <div
                        key={model.id}
                        className="p-2 bg-muted/50 rounded-md text-sm"
                      >
                        <div className="font-mono text-xs break-all">{model.id}</div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {getModelModes(model).map((mode) => (
                            <Badge key={mode} className={`text-xs border-0 ${getModeBadgeStyle(mode)}`}>
                              {mode}
                            </Badge>
                          ))}
                          {model.supports_streaming && (
                            <Badge variant="secondary" className="text-xs">
                              streaming
                            </Badge>
                          )}
                        </div>
                        {model.pricing && (
                          <div className="text-xs mt-1 flex items-center gap-2">
                            <span className="text-success font-medium">
                              In: {formatPricing(model.pricing.input_per_million_cents, provider.provider_id)}/M
                            </span>
                            <span className="text-warning font-medium">
                              Out: {formatPricing(model.pricing.output_per_million_cents, provider.provider_id)}/M
                            </span>
                            {model.pricing.source === 'default' && (
                              <span className="text-muted-foreground">(default)</span>
                            )}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-2">
                          {model.context_window && (
                            <span>Context: {model.context_window.toLocaleString()}</span>
                          )}
                          {model.max_output_tokens && (
                            <span>Max output: {model.max_output_tokens.toLocaleString()}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={() => verifyProvider(provider.provider_id)}
                disabled={verifying === provider.provider_id}
              >
                {verifying === provider.provider_id ? 'Verifying...' : 'Verify Now'}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
