'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Shield, Lock, Eye, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface TEEStatus {
  health: {
    tee_enabled: boolean;
    attestation_available: boolean;
    secure_execution: boolean;
    memory_protection: boolean;
    status: string;
  };
  capabilities: {
    supported_features: string[];
    encryption_algorithms: string[];
    secure_memory_size: number;
    max_concurrent_sessions: number;
  };
  metrics: {
    total_requests: number;
    secure_requests: number;
    attestations_generated: number;
    privacy_score: number;
    data_encrypted_mb: number;
    active_sessions: number;
    avg_response_time_ms: number;
  };
  models: {
    available: number;
    list: Array<{
      name: string;
      provider: string;
      privacy_level: string;
      attestation_required: boolean;
    }>;
  };
  summary: {
    tee_enabled: boolean;
    secure_inference_available: boolean;
    attestation_available: boolean;
    privacy_score: number;
  };
}

interface AttestationData {
  report: string;
  signature: string;
  certificate_chain: string;
  measurements: Record<string, string>;
  timestamp: string;
  validity_period: number;
}

interface SecureSession {
  session_id: string;
  user_id: string;
  capabilities: string[];
  created_at: string;
  expires_at: string;
  status: string;
}

export default function TEEMonitor() {
  const [teeStatus, setTeeStatus] = useState<TEEStatus | null>(null);
  const [attestationData, setAttestationData] = useState<AttestationData | null>(null);
  const [secureSession, setSecureSession] = useState<SecureSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTEEStatus = async () => {
    try {
      const data = await apiClient.get('/api-internal/v1/tee/status');
      if (data.success) {
        setTeeStatus(data.data);
      } else {
        throw new Error('Failed to fetch TEE status');
      }
    } catch (err) {
      console.error('Error fetching TEE status:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const generateAttestation = async () => {
    try {
      const data = await apiClient.post('/api-internal/v1/tee/attestation', {
        nonce: Date.now().toString()
      });
      if (data.success) {
        setAttestationData(data.data);
      } else {
        throw new Error('Failed to generate attestation');
      }
    } catch (err) {
      console.error('Error generating attestation:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const createSecureSession = async () => {
    try {
      const data = await apiClient.post('/api-internal/v1/tee/session', {
        capabilities: ['confidential_inference', 'secure_memory', 'attestation']
      });
      if (data.success) {
        setSecureSession(data.data);
      } else {
        throw new Error('Failed to create secure session');
      }
    } catch (err) {
      console.error('Error creating secure session:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const refreshData = async () => {
    setRefreshing(true);
    await fetchTEEStatus();
    setRefreshing(false);
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchTEEStatus();
      setLoading(false);
    };

    loadData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(refreshData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: boolean) => {
    return status ? 'bg-green-500' : 'bg-red-500';
  };

  const getStatusIcon = (status: boolean) => {
    return status ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center space-x-2">
          <RefreshCw className="w-6 h-6 animate-spin" />
          <span>Loading TEE status...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert className="border-red-200 bg-red-50">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Error loading TEE status: {error}
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            className="ml-2"
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!teeStatus) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          No TEE status data available
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Shield className="w-6 h-6 text-blue-600" />
          <h2 className="text-2xl font-bold">TEE Monitor</h2>
        </div>
        <Button
          onClick={refreshData}
          disabled={refreshing}
          variant="outline"
          size="sm"
        >
          {refreshing ? (
            <RefreshCw className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <RefreshCw className="w-4 h-4 mr-2" />
          )}
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">TEE Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${getStatusColor(teeStatus.summary.tee_enabled)}`} />
              <span className="text-2xl font-bold">
                {teeStatus.summary.tee_enabled ? 'Active' : 'Inactive'}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Privacy Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-2xl font-bold">{teeStatus.summary.privacy_score}%</div>
              <Progress 
                value={teeStatus.summary.privacy_score} 
                className="h-2"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Secure Models</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{teeStatus.models.available}</div>
            <p className="text-sm text-muted-foreground">Available</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{teeStatus.metrics.active_sessions}</div>
            <p className="text-sm text-muted-foreground">Secure sessions</p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Information */}
      <Tabs defaultValue="status" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="status">Status</TabsTrigger>
          <TabsTrigger value="attestation">Attestation</TabsTrigger>
          <TabsTrigger value="session">Session</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Shield className="w-5 h-5 mr-2" />
                  Health Status
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span>TEE Enabled</span>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(teeStatus.health.tee_enabled)}
                    <Badge variant={teeStatus.health.tee_enabled ? "default" : "destructive"}>
                      {teeStatus.health.tee_enabled ? "Yes" : "No"}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span>Attestation Available</span>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(teeStatus.health.attestation_available)}
                    <Badge variant={teeStatus.health.attestation_available ? "default" : "destructive"}>
                      {teeStatus.health.attestation_available ? "Yes" : "No"}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span>Secure Execution</span>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(teeStatus.health.secure_execution)}
                    <Badge variant={teeStatus.health.secure_execution ? "default" : "destructive"}>
                      {teeStatus.health.secure_execution ? "Yes" : "No"}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span>Memory Protection</span>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(teeStatus.health.memory_protection)}
                    <Badge variant={teeStatus.health.memory_protection ? "default" : "destructive"}>
                      {teeStatus.health.memory_protection ? "Yes" : "No"}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Lock className="w-5 h-5 mr-2" />
                  Privacy Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span>Total Requests</span>
                  <span className="font-mono">{teeStatus.metrics.total_requests.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Secure Requests</span>
                  <span className="font-mono">{teeStatus.metrics.secure_requests.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Attestations Generated</span>
                  <span className="font-mono">{teeStatus.metrics.attestations_generated.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Data Encrypted</span>
                  <span className="font-mono">{teeStatus.metrics.data_encrypted_mb.toFixed(2)} MB</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Avg Response Time</span>
                  <span className="font-mono">{teeStatus.metrics.avg_response_time_ms}ms</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="attestation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Eye className="w-5 h-5 mr-2" />
                TEE Attestation
              </CardTitle>
              <CardDescription>
                Generate and verify cryptographic attestation reports
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <Button onClick={generateAttestation} className="flex-1">
                  Generate Attestation
                </Button>
              </div>
              
              {attestationData && (
                <div className="space-y-3">
                  <Separator />
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label className="text-sm font-medium">Report ID</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm break-all">
                        {attestationData.report.substring(0, 64)}...
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Signature</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm break-all">
                        {attestationData.signature.substring(0, 64)}...
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Timestamp</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm">
                        {new Date(attestationData.timestamp).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Validity Period</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm">
                        {attestationData.validity_period} seconds
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="session" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Secure Session Management</CardTitle>
              <CardDescription>
                Create and manage secure TEE sessions
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <Button onClick={createSecureSession} className="flex-1">
                  Create Secure Session
                </Button>
              </div>
              
              {secureSession && (
                <div className="space-y-3">
                  <Separator />
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label className="text-sm font-medium">Session ID</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm">
                        {secureSession.session_id}
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Status</label>
                      <div className="mt-1">
                        <Badge variant={secureSession.status === 'active' ? 'default' : 'secondary'}>
                          {secureSession.status}
                        </Badge>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Capabilities</label>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {secureSession.capabilities.map((cap) => (
                          <Badge key={cap} variant="outline" className="text-xs">
                            {cap}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Created</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm">
                        {new Date(secureSession.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium">Expires</label>
                      <div className="mt-1 p-2 bg-gray-50 rounded font-mono text-sm">
                        {new Date(secureSession.expires_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="models" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Available TEE Models</CardTitle>
              <CardDescription>
                AI models with confidential computing capabilities
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-80">
                <div className="space-y-3">
                  {teeStatus.models.list.map((model, index) => (
                    <div key={index} className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium">{model.name}</h4>
                        <div className="flex items-center space-x-2">
                          <Badge variant="secondary">{model.provider}</Badge>
                          <Badge variant={model.privacy_level === 'high' ? 'default' : 'outline'}>
                            {model.privacy_level}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                        <span>Attestation Required:</span>
                        <Badge variant={model.attestation_required ? 'default' : 'secondary'}>
                          {model.attestation_required ? 'Yes' : 'No'}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}