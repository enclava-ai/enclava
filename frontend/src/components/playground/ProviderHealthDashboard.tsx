"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertCircle, 
  RefreshCw, 
  Activity,
  Zap,
  Shield,
  Server
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'

interface ProviderStatus {
  provider: string
  status: 'healthy' | 'degraded' | 'unavailable'
  latency_ms?: number
  success_rate?: number
  last_check: string
  error_message?: string
  models_available: string[]
}

interface LLMMetrics {
  total_requests: number
  successful_requests: number
  failed_requests: number
  security_blocked_requests: number
  average_latency_ms: number
  average_risk_score: number
  provider_metrics: Record<string, any>
  last_updated: string
}

export default function ProviderHealthDashboard() {
  const [providers, setProviders] = useState<Record<string, ProviderStatus>>({})
  const [metrics, setMetrics] = useState<LLMMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)

      const [statusResponse, metricsResponse] = await Promise.allSettled([
        apiClient.get('/api-internal/v1/llm/providers/status'),
        apiClient.get('/api-internal/v1/llm/metrics')
      ])

      // Handle provider status
      if (statusResponse.status === 'fulfilled') {
        setProviders(statusResponse.value.data || {})
      }

      // Handle metrics (optional, might require admin permissions)
      if (metricsResponse.status === 'fulfilled') {
        setMetrics(metricsResponse.value.data)
      }

      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load provider data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'degraded':
        return <Clock className="h-5 w-5 text-yellow-500" />
      case 'unavailable':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <AlertCircle className="h-5 w-5 text-gray-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-50 border-green-200'
      case 'degraded':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      case 'unavailable':
        return 'text-red-600 bg-red-50 border-red-200'
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const getLatencyColor = (latency: number) => {
    if (latency < 500) return 'text-green-600'
    if (latency < 2000) return 'text-yellow-600'
    return 'text-red-600'
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Provider Health Dashboard</h2>
          <RefreshCw className="h-5 w-5 animate-spin" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="space-y-2">
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2"></div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="h-3 bg-gray-200 rounded"></div>
                  <div className="h-3 bg-gray-200 rounded w-2/3"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Provider Health Dashboard</h2>
          <Button onClick={fetchData} size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const totalProviders = Object.keys(providers).length
  const healthyProviders = Object.values(providers).filter(p => p.status === 'healthy').length
  const overallHealth = totalProviders > 0 ? (healthyProviders / totalProviders) * 100 : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Provider Health Dashboard</h2>
        <Button onClick={fetchData} size="sm" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Overall Health Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Overall Health</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Math.round(overallHealth)}%</div>
            <Progress value={overallHealth} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Healthy Providers</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{healthyProviders}</div>
            <p className="text-xs text-muted-foreground">of {totalProviders} providers</p>
          </CardContent>
        </Card>

        {metrics && (
          <>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
                <Zap className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {metrics.total_requests > 0 
                    ? Math.round((metrics.successful_requests / metrics.total_requests) * 100)
                    : 0}%
                </div>
                <p className="text-xs text-muted-foreground">
                  {metrics.successful_requests.toLocaleString()} / {metrics.total_requests.toLocaleString()} requests
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Security Score</CardTitle>
                <Shield className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {Math.round((1 - metrics.average_risk_score) * 100)}%
                </div>
                <p className="text-xs text-muted-foreground">
                  {metrics.security_blocked_requests} blocked requests
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Provider Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(providers).map(([name, provider]) => (
          <Card key={name} className={`border-2 ${getStatusColor(provider.status)}`}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  {getStatusIcon(provider.status)}
                  {provider.provider}
                </CardTitle>
                <Badge 
                  variant={provider.status === 'healthy' ? 'default' : 'destructive'}
                  className="capitalize"
                >
                  {provider.status}
                </Badge>
              </div>
              <CardDescription>
                {provider.models_available.length} models available
              </CardDescription>
            </CardHeader>
            
            <CardContent className="space-y-3">
              {/* Performance Metrics */}
              {provider.latency_ms && (
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Latency</span>
                  <span className={`text-sm font-mono ${getLatencyColor(provider.latency_ms)}`}>
                    {Math.round(provider.latency_ms)}ms
                  </span>
                </div>
              )}

              {provider.success_rate !== undefined && (
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Success Rate</span>
                  <span className="text-sm font-mono">
                    {Math.round(provider.success_rate * 100)}%
                  </span>
                </div>
              )}

              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Last Check</span>
                <span className="text-sm text-muted-foreground">
                  {new Date(provider.last_check).toLocaleTimeString()}
                </span>
              </div>

              {/* Error Message */}
              {provider.error_message && (
                <Alert variant="destructive" className="mt-3">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-xs">
                    {provider.error_message}
                  </AlertDescription>
                </Alert>
              )}

              {/* Models */}
              <div className="space-y-2">
                <span className="text-sm font-medium">Available Models</span>
                <div className="flex flex-wrap gap-1">
                  {provider.models_available.slice(0, 3).map(model => (
                    <Badge key={model} variant="outline" className="text-xs">
                      {model}
                    </Badge>
                  ))}
                  {provider.models_available.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{provider.models_available.length - 3} more
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Provider Metrics Details */}
      {metrics && Object.keys(metrics.provider_metrics).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Provider Performance Metrics
            </CardTitle>
            <CardDescription>
              Detailed performance statistics for each provider
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(metrics.provider_metrics).map(([provider, data]: [string, any]) => (
                <div key={provider} className="border rounded-lg p-4">
                  <h4 className="font-semibold mb-3 capitalize">{provider}</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Total Requests:</span>
                      <span className="font-mono">{data.total_requests?.toLocaleString() || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Success Rate:</span>
                      <span className="font-mono">
                        {data.success_rate ? Math.round(data.success_rate * 100) : 0}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Avg Latency:</span>
                      <span className={`font-mono ${getLatencyColor(data.average_latency_ms || 0)}`}>
                        {Math.round(data.average_latency_ms || 0)}ms
                      </span>
                    </div>
                    {data.token_usage && (
                      <div className="flex justify-between">
                        <span>Total Tokens:</span>
                        <span className="font-mono">
                          {data.token_usage.total_tokens?.toLocaleString() || 0}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}