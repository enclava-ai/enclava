"use client"

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  RefreshCw,
  Activity,
  DollarSign,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  ExternalLink,
  Key,
  BarChart3,
  Loader2,
  Zap,
  Bot,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/components/providers/auth-provider'

// Type definitions
interface UsageSummary {
  total_requests: number
  total_tokens: number
  total_cost_dollars: number
  error_rate_percent: number
  successful_requests: number
  failed_requests: number
}

interface ProviderBreakdown {
  provider_id: string
  provider_name: string
  requests: number
  tokens: number
  cost_dollars: number
}

interface ModelBreakdown {
  model: string
  provider_id: string
  requests: number
  tokens: number
  cost_dollars: number
}

interface SourceBreakdown {
  source: string
  source_name: string
  total_requests: number
  total_tokens: number
  total_cost_dollars: number
}

interface DailyTrend {
  date: string
  requests: number
  tokens: number
  cost_dollars: number
}

interface UsageStats {
  summary: UsageSummary
  by_provider: ProviderBreakdown[]
  by_model: ModelBreakdown[]
  by_source?: SourceBreakdown[]
  daily_trend: DailyTrend[]
}

interface ApiKey {
  id: number
  name: string
  key_prefix: string
  is_active: boolean
  created_at: string
  last_used_at?: string
}

interface ApiKeyWithStats extends ApiKey {
  stats?: UsageStats
  statsLoading?: boolean
  statsError?: string
}

type Period = '7d' | '30d' | '90d'

// Icon mapping for sources
const sourceIcons: Record<string, React.ReactNode> = {
  api_key: <Key className="h-4 w-4" />,
  playground: <Zap className="h-4 w-4" />,
  agent: <Bot className="h-4 w-4" />,
}

export default function UsageTab() {
  const router = useRouter()
  const { isAuthenticated } = useAuth()

  // State
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [period, setPeriod] = useState<Period>('30d')

  // User-level stats (includes all sources)
  const [userStats, setUserStats] = useState<UsageStats | null>(null)

  // API keys for the breakdown table
  const [apiKeys, setApiKeys] = useState<ApiKeyWithStats[]>([])

  // Format helpers
  const formatNumber = (num: number) => num.toLocaleString()
  const formatCurrency = (amount: number) => `$${amount.toFixed(4)}`
  const formatPercent = (percent: number) => `${percent.toFixed(2)}%`

  // Fetch user-level stats (all sources)
  const fetchUserStats = useCallback(async (): Promise<UsageStats | null> => {
    try {
      const data = await apiClient.get<UsageStats>(
        `/api-internal/v1/usage/me/stats?period=${period}`
      )
      return data
    } catch (error: any) {
      // 500 might mean no data yet
      if (error?.status === 500) {
        return null
      }
      throw error
    }
  }, [period])

  // Fetch API keys
  const fetchApiKeys = useCallback(async () => {
    try {
      const result = await apiClient.get('/api-internal/v1/api-keys/') as any
      const keys = result.api_keys || result.data || []
      return keys
    } catch (error) {
      return []
    }
  }, [])

  // Fetch stats for a single API key
  const fetchApiKeyStats = useCallback(async (apiKeyId: number): Promise<UsageStats | null> => {
    try {
      const data = await apiClient.get<UsageStats>(
        `/api-internal/v1/usage/api-keys/${apiKeyId}/stats?period=${period}`
      )
      return data
    } catch (error: any) {
      return null
    }
  }, [period])

  // Load all data
  const loadData = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    else setRefreshing(true)

    try {
      // Fetch user stats and API keys in parallel
      const [stats, keys] = await Promise.all([
        fetchUserStats(),
        fetchApiKeys(),
      ])

      setUserStats(stats)

      // Fetch stats for each API key
      if (keys.length > 0) {
        setApiKeys(keys.map((k: ApiKey) => ({ ...k, statsLoading: true })))

        const keysWithStats = await Promise.all(
          keys.map(async (key: ApiKey): Promise<ApiKeyWithStats> => {
            const keyStats = await fetchApiKeyStats(key.id)
            return { ...key, stats: keyStats || undefined, statsLoading: false }
          })
        )
        setApiKeys(keysWithStats)
      } else {
        setApiKeys([])
      }
    } catch (error) {
      toast.error('Failed to load usage data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [fetchUserStats, fetchApiKeys, fetchApiKeyStats])

  // Initial load and period change
  useEffect(() => {
    if (isAuthenticated) {
      loadData()
    } else {
      setLoading(false)
    }
  }, [isAuthenticated, period])

  // Refresh handler
  const handleRefresh = () => loadData(false)

  // Navigate to detailed stats
  const navigateToDetailedStats = (apiKeyId: number) => {
    router.push(`/dashboard/api-keys/${apiKeyId}/stats`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const hasUsageData = userStats && userStats.summary.total_requests > 0
  const hasApiKeys = apiKeys.length > 0

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Label className="text-muted-foreground">Period:</Label>
          <Select value={period} onValueChange={(v) => setPeriod(v as Period)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Summary Cards - Total Usage */}
      {hasUsageData && userStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatNumber(userStats.summary.total_requests)}</div>
              <p className="text-xs text-muted-foreground">
                {formatNumber(userStats.summary.successful_requests)} successful
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Tokens</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatNumber(userStats.summary.total_tokens)}</div>
              <p className="text-xs text-muted-foreground">
                {userStats.summary.total_requests > 0
                  ? `${formatNumber(Math.round(userStats.summary.total_tokens / userStats.summary.total_requests))} avg/request`
                  : 'No requests'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Cost</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatCurrency(userStats.summary.total_cost_dollars)}</div>
              <p className="text-xs text-muted-foreground">
                {userStats.summary.total_requests > 0
                  ? `${formatCurrency(userStats.summary.total_cost_dollars / userStats.summary.total_requests)} avg/request`
                  : 'No requests'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
              {userStats.summary.error_rate_percent > 5 ? (
                <AlertCircle className="h-4 w-4 text-destructive" />
              ) : (
                <CheckCircle className="h-4 w-4 text-green-500" />
              )}
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatPercent(userStats.summary.error_rate_percent)}</div>
              <p className="text-xs text-muted-foreground">
                {formatNumber(userStats.summary.failed_requests)} failed requests
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Platform Usage - Playground & Agents (usage without API keys) */}
      {hasUsageData && userStats?.by_source && (() => {
        const platformSources = userStats.by_source.filter(s => s.source === 'playground' || s.source === 'agent')
        const platformTotal = {
          requests: platformSources.reduce((sum, s) => sum + s.total_requests, 0),
          tokens: platformSources.reduce((sum, s) => sum + s.total_tokens, 0),
          cost: platformSources.reduce((sum, s) => sum + s.total_cost_dollars, 0),
        }
        const apiKeySource = userStats.by_source.find(s => s.source === 'api_key')

        if (platformTotal.requests === 0 && (!apiKeySource || apiKeySource.total_requests === 0)) {
          return null
        }

        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Platform Usage Section */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Zap className="h-5 w-5" />
                  Platform Usage
                </CardTitle>
                <CardDescription>
                  Usage from Playground and agent testing (no API key required)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {platformTotal.requests > 0 ? (
                  <div className="space-y-4">
                    {/* Platform Totals */}
                    <div className="grid grid-cols-3 gap-4 p-4 bg-muted/50 rounded-lg">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{formatNumber(platformTotal.requests)}</div>
                        <div className="text-xs text-muted-foreground">Requests</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">{formatNumber(platformTotal.tokens)}</div>
                        <div className="text-xs text-muted-foreground">Tokens</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">{formatCurrency(platformTotal.cost)}</div>
                        <div className="text-xs text-muted-foreground">Cost</div>
                      </div>
                    </div>
                    {/* Individual Sources */}
                    <div className="space-y-2">
                      {platformSources.map((source) => (
                        <div key={source.source} className="flex items-center justify-between p-3 border rounded-lg">
                          <div className="flex items-center gap-2">
                            {sourceIcons[source.source] || <Activity className="h-4 w-4" />}
                            <span className="font-medium">{source.source_name}</span>
                          </div>
                          <div className="flex items-center gap-4 text-sm">
                            <span className="text-muted-foreground">{formatNumber(source.total_requests)} requests</span>
                            <span className="text-muted-foreground">{formatNumber(source.total_tokens)} tokens</span>
                            <span className="font-medium">{formatCurrency(source.total_cost_dollars)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Zap className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No platform usage yet</p>
                    <p className="text-xs mt-1">Use the Playground or test agents to see usage here</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* API Usage Summary Section */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  API Usage
                </CardTitle>
                <CardDescription>
                  Usage from external API calls using API keys
                </CardDescription>
              </CardHeader>
              <CardContent>
                {apiKeySource && apiKeySource.total_requests > 0 ? (
                  <div className="space-y-4">
                    {/* API Totals */}
                    <div className="grid grid-cols-3 gap-4 p-4 bg-muted/50 rounded-lg">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{formatNumber(apiKeySource.total_requests)}</div>
                        <div className="text-xs text-muted-foreground">Requests</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">{formatNumber(apiKeySource.total_tokens)}</div>
                        <div className="text-xs text-muted-foreground">Tokens</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">{formatCurrency(apiKeySource.total_cost_dollars)}</div>
                        <div className="text-xs text-muted-foreground">Cost</div>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground text-center">
                      See detailed breakdown per API key below
                    </p>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No API usage yet</p>
                    <p className="text-xs mt-1">Make API calls with your keys to see usage here</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )
      })()}

      {/* Provider Breakdown */}
      {hasUsageData && userStats?.by_provider && userStats.by_provider.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Usage by Provider</CardTitle>
            <CardDescription>Statistics aggregated across all sources</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead className="text-right">Requests</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {userStats.by_provider.slice(0, 5).map((provider) => (
                  <TableRow key={provider.provider_id}>
                    <TableCell className="font-medium">{provider.provider_name}</TableCell>
                    <TableCell className="text-right">{formatNumber(provider.requests)}</TableCell>
                    <TableCell className="text-right">{formatNumber(provider.tokens)}</TableCell>
                    <TableCell className="text-right">{formatCurrency(provider.cost_dollars)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Top Models */}
      {hasUsageData && userStats?.by_model && userStats.by_model.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Top Models</CardTitle>
            <CardDescription>Most used models across all sources</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead className="text-right">Requests</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {userStats.by_model.slice(0, 10).map((model, idx) => (
                  <TableRow key={`${model.provider_id}-${model.model}-${idx}`}>
                    <TableCell className="font-medium font-mono text-sm">{model.model}</TableCell>
                    <TableCell>{model.provider_id}</TableCell>
                    <TableCell className="text-right">{formatNumber(model.requests)}</TableCell>
                    <TableCell className="text-right">{formatNumber(model.tokens)}</TableCell>
                    <TableCell className="text-right">{formatCurrency(model.cost_dollars)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* API Keys with Stats */}
      {hasApiKeys && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="h-5 w-5" />
              API Key Usage
            </CardTitle>
            <CardDescription>
              Usage statistics per API key. Click on a row for detailed statistics.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>API Key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Requests</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {apiKeys.map((apiKey) => {
                  const hasStats = apiKey.stats && apiKey.stats.summary.total_requests > 0
                  return (
                    <TableRow
                      key={apiKey.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigateToDetailedStats(apiKey.id)}
                    >
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{apiKey.name}</span>
                          <span className="text-xs text-muted-foreground font-mono">
                            {apiKey.key_prefix}...
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={apiKey.is_active ? 'default' : 'secondary'}>
                          {apiKey.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {apiKey.statsLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin ml-auto" />
                        ) : hasStats ? (
                          formatNumber(apiKey.stats!.summary.total_requests)
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {apiKey.statsLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin ml-auto" />
                        ) : hasStats ? (
                          formatNumber(apiKey.stats!.summary.total_tokens)
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {apiKey.statsLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin ml-auto" />
                        ) : hasStats ? (
                          formatCurrency(apiKey.stats!.summary.total_cost_dollars)
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigateToDetailedStats(apiKey.id)
                          }}
                        >
                          <BarChart3 className="h-4 w-4 mr-1" />
                          Details
                          <ExternalLink className="h-3 w-3 ml-1" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* No usage data message */}
      {!hasUsageData && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BarChart3 className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No Usage Data</h3>
            <p className="text-muted-foreground text-center mb-4 max-w-md">
              Start using the Playground, agent testing, or make API requests to see your usage statistics here.
            </p>
            {!hasApiKeys && (
              <Button onClick={() => router.push('/admin/api-keys')}>
                Create API Key
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
