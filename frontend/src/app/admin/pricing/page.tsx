"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  RefreshCw,
  DollarSign,
  Database,
  History,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Trash2,
  Search,
  BarChart3,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface PricingResponse {
  id: number;
  provider_id: string;
  model_id: string;
  model_name: string | null;
  input_price_per_million_cents: number;
  output_price_per_million_cents: number;
  input_price_per_million_dollars: number;
  output_price_per_million_dollars: number;
  currency: string;
  price_source: string;
  is_override: boolean;
  override_reason: string | null;
  override_by_user_id: number | null;
  context_length: number | null;
  architecture: any | null;
  quantization: string | null;
  effective_from: string;
  effective_until: string | null;
  is_current: boolean;
  created_at: string;
  updated_at: string;
}

interface ProviderMetadata {
  id: string;
  display_name: string;
  currency: string;
  currency_symbol: string;
  supports_api_sync: boolean;
  description: string;
  website: string | null;
}

interface ProviderListResponse {
  providers: ProviderMetadata[];
  total: number;
}

interface PricingListResponse {
  pricing: PricingResponse[];
  total: number;
  providers: string[];
}

interface PricingSummary {
  total_models: number;
  models_by_provider: Record<string, number>;
  override_count: number;
  api_sync_count: number;
  manual_count: number;
  last_sync_at: string | null;
}

interface LLMModel {
  id: string;
  provider: string;
  name?: string;
}

interface PricingHistoryResponse {
  id: number;
  provider_id: string;
  model_id: string;
  model_name: string | null;
  input_price_per_million_cents: number;
  output_price_per_million_cents: number;
  currency: string;
  price_source: string;
  is_override: boolean;
  override_reason: string | null;
  effective_from: string;
  effective_until: string | null;
  created_at: string;
}

interface SyncResultModel {
  model_id: string;
  model_name: string | null;
  action: string;
  old_input_price: number | null;
  old_output_price: number | null;
  new_input_price: number;
  new_output_price: number;
}

interface SyncResultResponse {
  provider_id: string;
  sync_job_id: string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  total_models: number;
  created_count: number;
  updated_count: number;
  unchanged_count: number;
  error_count: number;
  models: SyncResultModel[];
  errors: string[];
}

interface PricingAuditLogResponse {
  id: number;
  provider_id: string;
  model_id: string;
  action: string;
  old_input_price_per_million_cents: number | null;
  old_output_price_per_million_cents: number | null;
  new_input_price_per_million_cents: number;
  new_output_price_per_million_cents: number;
  change_source: string;
  changed_by_user_id: number | null;
  change_reason: string | null;
  sync_job_id: string | null;
  created_at: string;
}

export default function AdminPricingPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pricingData, setPricingData] = useState<PricingListResponse | null>(null);
  const [summary, setSummary] = useState<PricingSummary | null>(null);
  const [syncableProviders, setSyncableProviders] = useState<string[]>([]);
  const [availableProviders, setAvailableProviders] = useState<ProviderMetadata[]>([]);
  const [availableLLMModels, setAvailableLLMModels] = useState<LLMModel[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PricingResponse[]>([]);

  // History dialog
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [historyData, setHistoryData] = useState<PricingHistoryResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryModel, setSelectedHistoryModel] = useState<{ provider: string; model: string } | null>(null);

  // Sync result dialog
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResultResponse | null>(null);

  // Audit log
  const [auditLog, setAuditLog] = useState<PricingAuditLogResponse[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // Set pricing form - prices stored in full currency units (e.g., 5.00 EUR, not cents)
  const [setPricingForm, setSetPricingForm] = useState({
    provider_id: "",
    model_id: "",
    custom_model_id: "",
    use_custom_model: false,
    input_price: "",  // Full currency units (e.g., 5.00 for 5 EUR)
    output_price: "", // Full currency units (e.g., 5.00 for 5 EUR)
    reason: "",
  });
  const [setPricingLoading, setSetPricingLoading] = useState(false);

  // Get the selected provider's metadata
  const selectedProviderMeta = availableProviders.find(
    p => p.id === setPricingForm.provider_id
  );

  // Get models for selected provider from LLM models list (primary source)
  // Also include models from pricing data as fallback
  const modelsForSelectedProvider = setPricingForm.provider_id
    ? [...new Set([
        // Models from LLM service (live available models)
        ...availableLLMModels
          .filter(m => m.provider === setPricingForm.provider_id)
          .map(m => m.id),
        // Models from existing pricing data (may include historical models)
        ...(pricingData?.pricing || [])
          .filter(p => p.provider_id === setPricingForm.provider_id)
          .map(p => p.model_id)
      ])].sort()
    : [];

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [pricingRes, summaryRes, syncableRes, providersRes, modelsRes] = await Promise.all([
        apiClient.get<PricingListResponse>("/api-internal/v1/admin/pricing/all"),
        apiClient.get<PricingSummary>("/api-internal/v1/admin/pricing/summary"),
        apiClient.get<string[]>("/api-internal/v1/admin/pricing/syncable-providers"),
        apiClient.get<ProviderListResponse>("/api-internal/v1/admin/pricing/available-providers"),
        apiClient.get<{ data: LLMModel[] }>("/api-internal/v1/llm/models"),
      ]);

      setPricingData(pricingRes);
      setSummary(summaryRes);
      setSyncableProviders(syncableRes);
      setAvailableProviders(providersRes.providers);
      setAvailableLLMModels(modelsRes.data || []);
    } catch (err) {
      setError("Failed to load pricing data");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      const params = new URLSearchParams({
        query: searchQuery,
        limit: "50",
      });
      if (selectedProvider !== "all") {
        params.append("provider_id", selectedProvider);
      }

      const results = await apiClient.get<PricingResponse[]>(
        `/api-internal/v1/admin/pricing/search?${params.toString()}`
      );
      setSearchResults(results);
    } catch (err) {
      setError("Search failed");
    }
  };

  const handleSetPricing = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSetPricingLoading(true);
      setError(null);

      // Convert from full currency units to cents (multiply by 100)
      const inputPriceCents = Math.round(parseFloat(setPricingForm.input_price) * 100);
      const outputPriceCents = Math.round(parseFloat(setPricingForm.output_price) * 100);

      // Handle "All Models" case - set pricing for all models of this provider
      if (setPricingForm.model_id === "_all") {
        const modelsToUpdate = modelsForSelectedProvider;
        if (modelsToUpdate.length === 0) {
          setError("No models found for this provider");
          setSetPricingLoading(false);
          return;
        }

        // Set pricing for each model sequentially
        let successCount = 0;
        let errorCount = 0;
        for (const modelId of modelsToUpdate) {
          try {
            await apiClient.post("/api-internal/v1/admin/pricing/set", {
              provider_id: setPricingForm.provider_id,
              model_id: modelId,
              model_name: null,
              input_price_per_million_cents: inputPriceCents,
              output_price_per_million_cents: outputPriceCents,
              reason: setPricingForm.reason,
            });
            successCount++;
          } catch {
            errorCount++;
          }
        }

        if (errorCount > 0) {
          setError(`Set pricing for ${successCount} models, failed for ${errorCount} models`);
        }
      } else {
        // Single model case
        const modelId = setPricingForm.use_custom_model
          ? setPricingForm.custom_model_id
          : setPricingForm.model_id;

        if (!modelId) {
          setError("Please select or enter a model ID");
          setSetPricingLoading(false);
          return;
        }

        await apiClient.post("/api-internal/v1/admin/pricing/set", {
          provider_id: setPricingForm.provider_id,
          model_id: modelId,
          model_name: null,
          input_price_per_million_cents: inputPriceCents,
          output_price_per_million_cents: outputPriceCents,
          reason: setPricingForm.reason,
        });
      }

      // Reset form
      setSetPricingForm({
        provider_id: "",
        model_id: "",
        custom_model_id: "",
        use_custom_model: false,
        input_price: "",
        output_price: "",
        reason: "",
      });

      // Refresh data
      await fetchAllData();
    } catch (err) {
      setError("Failed to set pricing");
    } finally {
      setSetPricingLoading(false);
    }
  };

  const handleRemoveOverride = async (provider: string, model: string) => {
    if (!confirm(`Remove override for ${provider}/${model}?`)) return;

    try {
      await apiClient.delete(`/api-internal/v1/admin/pricing/override/${provider}/${encodeURIComponent(model)}`);
      await fetchAllData();
    } catch (err) {
      setError("Failed to remove override");
    }
  };

  const handleSync = async (provider: string) => {
    if (!confirm(`Trigger pricing sync for ${provider}? This will fetch pricing from the provider's API.`)) return;

    try {
      setLoading(true);
      const result = await apiClient.post<SyncResultResponse>(
        `/api-internal/v1/admin/pricing/sync/${provider}`
      );
      setSyncResult(result);
      setSyncDialogOpen(true);
      await fetchAllData();
    } catch (err) {
      setError(`Sync failed for ${provider}`);
    } finally {
      setLoading(false);
    }
  };

  const handleViewHistory = async (provider: string, model: string) => {
    setHistoryLoading(true);
    setSelectedHistoryModel({ provider, model });
    setHistoryDialogOpen(true);

    try {
      const history = await apiClient.get<PricingHistoryResponse[]>(
        `/api-internal/v1/admin/pricing/history/${provider}/${encodeURIComponent(model)}?limit=50`
      );
      setHistoryData(history);
    } catch (err) {
      setError("Failed to load history");
    } finally {
      setHistoryLoading(false);
    }
  };

  const fetchAuditLog = async () => {
    try {
      setAuditLoading(true);
      const params = new URLSearchParams({ limit: "100" });
      if (selectedProvider !== "all") {
        params.append("provider_id", selectedProvider);
      }

      const logs = await apiClient.get<PricingAuditLogResponse[]>(
        `/api-internal/v1/admin/pricing/audit-log?${params.toString()}`
      );
      setAuditLog(logs);
    } catch (err) {
      setError("Failed to load audit log");
    } finally {
      setAuditLoading(false);
    }
  };

  const formatCurrency = (cents: number, currency: string = "USD") => {
    const locale = currency === "EUR" ? "de-DE" : "en-US";
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(cents / 100);
  };

  // Helper to get currency for a provider
  const getProviderCurrency = (providerId: string): string => {
    const provider = availableProviders.find(p => p.id === providerId);
    return provider?.currency || "USD";
  };

  // Helper to get currency symbol for a provider
  const getProviderCurrencySymbol = (providerId: string): string => {
    const provider = availableProviders.find(p => p.id === providerId);
    return provider?.currency_symbol || "$";
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("en-US").format(value);
  };

  const getPriceSourceBadge = (source: string) => {
    switch (source) {
      case "api_sync":
        return <Badge variant="outline" className="bg-info-soft text-info-soft-foreground border-info-border">API Sync</Badge>;
      case "manual":
        return <Badge variant="outline" className="bg-muted text-muted-foreground border-border">Manual</Badge>;
      case "default":
        return <Badge variant="outline" className="bg-muted text-muted-foreground border-border">Default</Badge>;
      default:
        return <Badge variant="outline">{source}</Badge>;
    }
  };

  const filteredPricing = selectedProvider === "all"
    ? pricingData?.pricing || []
    : (pricingData?.pricing || []).filter(p => p.provider_id === selectedProvider);

  const displayedPricing = searchQuery.trim() ? searchResults : filteredPricing;

  if (loading && !pricingData) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading pricing data...</span>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Pricing Management</h1>
          <p className="text-muted-foreground mt-1">
            Manage provider pricing, set overrides, and sync from APIs
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={fetchAllData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {error && (
        <div className="flex items-center space-x-2 p-4 bg-danger-soft border border-danger-border rounded-lg text-danger-soft-foreground">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
          <Button variant="ghost" size="sm" onClick={() => setError(null)}>
            Dismiss
          </Button>
        </div>
      )}

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="all-pricing">All Pricing</TabsTrigger>
          <TabsTrigger value="set-pricing">Set Pricing</TabsTrigger>
          <TabsTrigger value="sync">Sync</TabsTrigger>
          <TabsTrigger value="audit-log" onClick={fetchAuditLog}>Audit Log</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {summary && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  title="Total Models"
                  value={formatNumber(summary.total_models)}
                  icon={<Database className="h-4 w-4" />}
                />
                <StatCard
                  title="Override Count"
                  value={formatNumber(summary.override_count)}
                  icon={<AlertCircle className="h-4 w-4" />}
                />
                <StatCard
                  title="API Synced"
                  value={formatNumber(summary.api_sync_count)}
                  icon={<RefreshCw className="h-4 w-4" />}
                />
                <StatCard
                  title="Manual Entries"
                  value={formatNumber(summary.manual_count)}
                  icon={<DollarSign className="h-4 w-4" />}
                />
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Models by Provider</CardTitle>
                  <CardDescription>Distribution of pricing entries across providers</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Object.entries(summary.models_by_provider).map(([provider, count]) => {
                      const providerMeta = availableProviders.find(p => p.id === provider);
                      return (
                        <div key={provider} className="flex items-center justify-between p-3 border rounded-lg">
                          <div className="flex items-center space-x-3">
                            <div>
                              <div className="font-medium text-lg">
                                {providerMeta?.display_name || provider}
                              </div>
                              {providerMeta && (
                                <div className="text-xs text-muted-foreground">
                                  {providerMeta.currency_symbol} {providerMeta.currency} • {providerMeta.description}
                                </div>
                              )}
                            </div>
                            <Badge variant="outline">{count} models</Badge>
                          </div>
                          {syncableProviders.includes(provider) && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleSync(provider)}
                            >
                              <RefreshCw className="h-4 w-4 mr-2" />
                              Sync
                            </Button>
                          )}
                        </div>
                      );
                    })}
                    {/* Show providers without pricing entries */}
                    {availableProviders
                      .filter(p => !Object.keys(summary.models_by_provider).includes(p.id))
                      .map((provider) => (
                        <div key={provider.id} className="flex items-center justify-between p-3 border rounded-lg border-dashed">
                          <div className="flex items-center space-x-3">
                            <div>
                              <div className="font-medium text-lg text-muted-foreground">
                                {provider.display_name}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {provider.currency_symbol} {provider.currency} • {provider.description}
                              </div>
                            </div>
                            <Badge variant="outline" className="text-muted-foreground">No pricing set</Badge>
                          </div>
                          {syncableProviders.includes(provider.id) && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleSync(provider.id)}
                            >
                              <RefreshCw className="h-4 w-4 mr-2" />
                              Sync
                            </Button>
                          )}
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>

              {summary.last_sync_at && (
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                      <History className="h-4 w-4" />
                      <span>Last sync: {new Date(summary.last_sync_at).toLocaleString()}</span>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* All Pricing Tab */}
        <TabsContent value="all-pricing" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>All Pricing Entries</CardTitle>
                  <CardDescription>
                    {displayedPricing.length} of {pricingData?.total || 0} entries
                  </CardDescription>
                </div>
                <div className="flex items-center space-x-2">
                  <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="All Providers" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Providers</SelectItem>
                      {pricingData?.providers.map((provider) => (
                        <SelectItem key={provider} value={provider}>
                          {provider}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center space-x-2 mt-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search models..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="pl-10"
                  />
                </div>
                <Button onClick={handleSearch}>Search</Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-right">Input (/M)</TableHead>
                    <TableHead className="text-right">Output (/M)</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayedPricing.map((pricing) => (
                    <TableRow key={pricing.id}>
                      <TableCell>
                        <div className="font-medium">{pricing.provider_id}</div>
                        <div className="text-xs text-muted-foreground">
                          {pricing.currency || getProviderCurrency(pricing.provider_id)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-sm">{pricing.model_id}</div>
                        {pricing.model_name && (
                          <div className="text-xs text-muted-foreground mt-1">
                            {pricing.model_name}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="font-medium">
                          {formatCurrency(pricing.input_price_per_million_cents, pricing.currency || getProviderCurrency(pricing.provider_id))}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {pricing.input_price_per_million_cents} cents
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="font-medium">
                          {formatCurrency(pricing.output_price_per_million_cents, pricing.currency || getProviderCurrency(pricing.provider_id))}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {pricing.output_price_per_million_cents} cents
                        </div>
                      </TableCell>
                      <TableCell>{getPriceSourceBadge(pricing.price_source)}</TableCell>
                      <TableCell>
                        {pricing.is_override ? (
                          <Badge variant="outline" className="bg-warning-soft text-warning-soft-foreground border-warning-border">
                            Override
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="bg-success-soft text-success-soft-foreground border-success-border">
                            Active
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewHistory(pricing.provider_id, pricing.model_id)}
                          >
                            <History className="h-4 w-4" />
                          </Button>
                          {pricing.is_override && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveOverride(pricing.provider_id, pricing.model_id)}
                            >
                              <Trash2 className="h-4 w-4 text-danger" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Set Pricing Tab */}
        <TabsContent value="set-pricing" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Set Manual Pricing</CardTitle>
              <CardDescription>
                Override or set custom pricing for a model. This will create a manual pricing entry.
                Prices are stored in the provider&apos;s native currency (EUR for PrivateMode, USD for RedPill).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSetPricing} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="provider_id">Provider *</Label>
                    <Select
                      value={setPricingForm.provider_id}
                      onValueChange={(value) => setSetPricingForm({
                        ...setPricingForm,
                        provider_id: value,
                        model_id: "",
                        custom_model_id: "",
                        use_custom_model: false,
                      })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select a provider" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableProviders.map((provider) => (
                          <SelectItem key={provider.id} value={provider.id}>
                            <div className="flex items-center gap-2">
                              <span>{provider.display_name}</span>
                              <Badge variant="outline" className="text-xs">
                                {provider.currency_symbol} {provider.currency}
                              </Badge>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedProviderMeta && (
                      <p className="text-xs text-muted-foreground">
                        {selectedProviderMeta.description}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="model_id">Model *</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setSetPricingForm({
                          ...setPricingForm,
                          use_custom_model: !setPricingForm.use_custom_model,
                          model_id: "",
                          custom_model_id: "",
                        })}
                        disabled={!setPricingForm.provider_id}
                      >
                        {setPricingForm.use_custom_model ? "Select Existing" : "Enter Custom"}
                      </Button>
                    </div>
                    {setPricingForm.use_custom_model ? (
                      <Input
                        id="custom_model_id"
                        type="text"
                        value={setPricingForm.custom_model_id}
                        onChange={(e) => setSetPricingForm({ ...setPricingForm, custom_model_id: e.target.value })}
                        placeholder="e.g., meta-llama/llama-3.1-70b-instruct"
                        disabled={!setPricingForm.provider_id}
                        required
                      />
                    ) : (
                      <Select
                        value={setPricingForm.model_id}
                        onValueChange={(value) => setSetPricingForm({ ...setPricingForm, model_id: value })}
                        disabled={!setPricingForm.provider_id}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={setPricingForm.provider_id ? (modelsForSelectedProvider.length > 0 ? "Select a model" : "No models - use custom") : "Select provider first"} />
                        </SelectTrigger>
                        <SelectContent>
                          {modelsForSelectedProvider.length > 1 && (
                            <SelectItem value="_all" className="font-semibold">
                              All Models ({modelsForSelectedProvider.length})
                            </SelectItem>
                          )}
                          {modelsForSelectedProvider.map((model) => (
                            <SelectItem key={model} value={model}>
                              {model}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    {setPricingForm.model_id === "_all" && (
                      <p className="text-xs text-info">
                        Pricing will be applied to all {modelsForSelectedProvider.length} models for this provider.
                      </p>
                    )}
                    {setPricingForm.provider_id && modelsForSelectedProvider.length === 0 && !setPricingForm.use_custom_model && (
                      <p className="text-xs text-muted-foreground">
                        No existing models for this provider. Click &quot;Enter Custom&quot; to add a new model.
                      </p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="input_price">
                      Input Price ({selectedProviderMeta?.currency_symbol || "$"} per million tokens) *
                    </Label>
                    <Input
                      id="input_price"
                      type="number"
                      min="0"
                      step="0.01"
                      value={setPricingForm.input_price}
                      onChange={(e) => setSetPricingForm({ ...setPricingForm, input_price: e.target.value })}
                      placeholder="5.00"
                      required
                    />
                    {setPricingForm.input_price && selectedProviderMeta && (
                      <p className="text-sm text-muted-foreground">
                        = {selectedProviderMeta.currency_symbol}{parseFloat(setPricingForm.input_price).toFixed(2)} {selectedProviderMeta.currency} per million tokens
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="output_price">
                      Output Price ({selectedProviderMeta?.currency_symbol || "$"} per million tokens) *
                    </Label>
                    <Input
                      id="output_price"
                      type="number"
                      min="0"
                      step="0.01"
                      value={setPricingForm.output_price}
                      onChange={(e) => setSetPricingForm({ ...setPricingForm, output_price: e.target.value })}
                      placeholder="5.00"
                      required
                    />
                    {setPricingForm.output_price && selectedProviderMeta && (
                      <p className="text-sm text-muted-foreground">
                        = {selectedProviderMeta.currency_symbol}{parseFloat(setPricingForm.output_price).toFixed(2)} {selectedProviderMeta.currency} per million tokens
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="reason">Reason *</Label>
                  <Textarea
                    id="reason"
                    value={setPricingForm.reason}
                    onChange={(e) => setSetPricingForm({ ...setPricingForm, reason: e.target.value })}
                    placeholder="Explain why you're setting this pricing..."
                    required
                  />
                </div>

                <Button type="submit" disabled={setPricingLoading}>
                  {setPricingLoading ? (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Setting Pricing...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                      Set Pricing
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sync Tab */}
        <TabsContent value="sync" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Provider Sync</CardTitle>
              <CardDescription>
                Manually trigger pricing sync for providers that support API sync
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {syncableProviders.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No syncable providers available
                  </div>
                ) : (
                  syncableProviders.map((provider) => (
                    <div key={provider} className="flex items-center justify-between p-4 border rounded-lg">
                      <div>
                        <div className="font-medium text-lg">{provider}</div>
                        <div className="text-sm text-muted-foreground">
                          Sync pricing from {provider} API
                        </div>
                      </div>
                      <Button onClick={() => handleSync(provider)}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Sync Now
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Log Tab */}
        <TabsContent value="audit-log" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Pricing Audit Log</CardTitle>
                  <CardDescription>
                    History of all pricing changes and syncs
                  </CardDescription>
                </div>
                <Button variant="outline" onClick={fetchAuditLog} disabled={auditLoading}>
                  {auditLoading ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Provider / Model</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead className="text-right">Old Price</TableHead>
                    <TableHead className="text-right">New Price</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLog.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        {auditLoading ? "Loading..." : "No audit log entries"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    auditLog.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(log.created_at).toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <div className="font-mono text-sm">{log.provider_id}</div>
                          <div className="font-mono text-xs text-muted-foreground">{log.model_id}</div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{log.action}</Badge>
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {log.old_input_price_per_million_cents !== null ? (
                            <div>
                              <div>{formatCurrency(log.old_input_price_per_million_cents)}</div>
                              <div className="text-muted-foreground">
                                {formatCurrency(log.old_output_price_per_million_cents || 0)}
                              </div>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          <div>{formatCurrency(log.new_input_price_per_million_cents)}</div>
                          <div className="text-muted-foreground">
                            {formatCurrency(log.new_output_price_per_million_cents)}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div>{getPriceSourceBadge(log.change_source)}</div>
                          {log.change_reason && (
                            <div className="text-xs text-muted-foreground mt-1">
                              {log.change_reason}
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* History Dialog */}
      <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pricing History</DialogTitle>
            <DialogDescription>
              {selectedHistoryModel && (
                <>
                  {selectedHistoryModel.provider} / {selectedHistoryModel.model}
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
                <span className="ml-2">Loading history...</span>
              </div>
            ) : historyData.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No history available
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Effective From</TableHead>
                    <TableHead>Effective Until</TableHead>
                    <TableHead className="text-right">Input Price</TableHead>
                    <TableHead className="text-right">Output Price</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {historyData.map((history) => {
                    const currency = history.currency || getProviderCurrency(history.provider_id);
                    return (
                    <TableRow key={history.id}>
                      <TableCell className="text-sm">
                        {new Date(history.effective_from).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm">
                        {history.effective_until
                          ? new Date(history.effective_until).toLocaleString()
                          : "Current"
                        }
                      </TableCell>
                      <TableCell className="text-right">
                        <div>{formatCurrency(history.input_price_per_million_cents, currency)}</div>
                        <div className="text-xs text-muted-foreground">
                          {history.input_price_per_million_cents} cents
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div>{formatCurrency(history.output_price_per_million_cents, currency)}</div>
                        <div className="text-xs text-muted-foreground">
                          {history.output_price_per_million_cents} cents
                        </div>
                      </TableCell>
                      <TableCell>
                        {getPriceSourceBadge(history.price_source)}
                        {history.is_override && (
                          <div className="mt-1">
                            <Badge variant="outline" className="bg-warning-soft text-warning-soft-foreground border-warning-border text-xs">
                              Override
                            </Badge>
                          </div>
                        )}
                        {history.override_reason && (
                          <div className="text-xs text-muted-foreground mt-1">
                            {history.override_reason}
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Sync Result Dialog */}
      <Dialog open={syncDialogOpen} onOpenChange={setSyncDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Sync Results</DialogTitle>
            <DialogDescription>
              {syncResult && `Sync job ${syncResult.sync_job_id} for ${syncResult.provider_id}`}
            </DialogDescription>
          </DialogHeader>
          {syncResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 border rounded-lg">
                  <div className="text-sm text-muted-foreground">Total Models</div>
                  <div className="text-2xl font-bold">{syncResult.total_models}</div>
                </div>
                <div className="p-3 border rounded-lg">
                  <div className="text-sm text-muted-foreground">Created</div>
                  <div className="text-2xl font-bold text-success">{syncResult.created_count}</div>
                </div>
                <div className="p-3 border rounded-lg">
                  <div className="text-sm text-muted-foreground">Updated</div>
                  <div className="text-2xl font-bold text-info">{syncResult.updated_count}</div>
                </div>
                <div className="p-3 border rounded-lg">
                  <div className="text-sm text-muted-foreground">Errors</div>
                  <div className="text-2xl font-bold text-danger">{syncResult.error_count}</div>
                </div>
              </div>

              <div className="text-sm text-muted-foreground">
                Duration: {syncResult.duration_ms}ms
              </div>

              {syncResult.errors.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-danger">Errors:</h4>
                  {syncResult.errors.map((error, idx) => (
                    <div key={idx} className="p-2 bg-danger-soft border border-danger-border rounded text-sm text-danger-soft-foreground">
                      {error}
                    </div>
                  ))}
                </div>
              )}

              <div>
                <h4 className="font-medium mb-2">Model Changes:</h4>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Model</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead className="text-right">Old Price</TableHead>
                      <TableHead className="text-right">New Price</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {syncResult.models.map((model, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-mono text-sm">
                          {model.model_id}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              model.action === "created"
                                ? "bg-success-soft text-success-soft-foreground border-success-border"
                                : model.action === "updated"
                                ? "bg-info-soft text-info-soft-foreground border-info-border"
                                : "bg-muted text-muted-foreground border-border"
                            }
                          >
                            {model.action}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {model.old_input_price !== null ? (
                            <div>
                              <div>{formatCurrency(model.old_input_price)}</div>
                              <div className="text-muted-foreground">
                                {formatCurrency(model.old_output_price || 0)}
                              </div>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          <div>{formatCurrency(model.new_input_price)}</div>
                          <div className="text-muted-foreground">
                            {formatCurrency(model.new_output_price)}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setSyncDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center space-x-2 pb-2">
          {icon}
          <span className="text-sm font-medium text-muted-foreground">{title}</span>
        </div>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}
