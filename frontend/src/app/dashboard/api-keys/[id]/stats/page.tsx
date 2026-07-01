"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { apiClient } from "@/lib/api-client"
import { useToast } from "@/hooks/use-toast"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  ArrowLeft,
  RefreshCw,
  Download,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  AlertCircle,
  CheckCircle,
  Clock,
  ChevronDown,
  ChevronUp,
} from "lucide-react"

// Type definitions based on backend schemas
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
  daily_trend: DailyTrend[]
}

interface UsageRecord {
  id: number
  request_id: string
  created_at: string
  provider_id: string
  provider_model: string
  normalized_model: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost_cents: number
  output_cost_cents: number
  total_cost_cents: number
  total_cost_dollars: number
  endpoint: string
  method: string
  status: string
  error_type?: string
  is_streaming: boolean
  latency_ms?: number
  ttft_ms?: number
}

interface UsageRecordsResponse {
  records: UsageRecord[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

type Period = "7d" | "30d" | "90d"

export default function ApiKeyStatsPage() {
  const params = useParams()
  const router = useRouter()
  const { toast } = useToast()
  const apiKeyId = params.id as string

  // State
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [period, setPeriod] = useState<Period>("30d")
  const [stats, setStats] = useState<UsageStats | null>(null)
  const [records, setRecords] = useState<UsageRecordsResponse | null>(null)
  const [expandedRecordId, setExpandedRecordId] = useState<number | null>(null)

  // Filters for records
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(50)
  const [providerFilter, setProviderFilter] = useState("")
  const [modelFilter, setModelFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [startDateFilter, setStartDateFilter] = useState("")
  const [endDateFilter, setEndDateFilter] = useState("")

  // Fetch stats
  const fetchStats = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      else setRefreshing(true)

      const data = await apiClient.get<UsageStats>(
        `/api-internal/v1/usage/api-keys/${apiKeyId}/stats?period=${period}`
      )
      setStats(data)
    } catch (error: any) {
      toast({
        title: "Error loading statistics",
        description: error?.details?.detail || "Failed to load usage statistics",
        variant: "destructive",
      })

      if (error?.code === "FORBIDDEN" || error?.code === "NOT_FOUND") {
        router.push("/dashboard/api-keys")
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  // Fetch records
  const fetchRecords = async () => {
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        page_size: pageSize.toString(),
      })

      if (providerFilter) params.append("provider", providerFilter)
      if (modelFilter) params.append("model", modelFilter)
      if (statusFilter && statusFilter !== "all") params.append("status_filter", statusFilter)
      if (startDateFilter) params.append("start_date", startDateFilter)
      if (endDateFilter) params.append("end_date", endDateFilter)

      const data = await apiClient.get<UsageRecordsResponse>(
        `/api-internal/v1/usage/api-keys/${apiKeyId}/records?${params.toString()}`
      )
      setRecords(data)
    } catch (error: any) {
      toast({
        title: "Error loading records",
        description: error?.details?.detail || "Failed to load usage records",
        variant: "destructive",
      })
    }
  }

  // Initial load
  useEffect(() => {
    fetchStats()
  }, [period])

  useEffect(() => {
    if (!loading) {
      fetchRecords()
    }
  }, [currentPage, providerFilter, modelFilter, statusFilter, startDateFilter, endDateFilter])

  // Export functions
  const exportData = (format: "csv" | "json") => {
    if (!records) return

    if (format === "json") {
      const dataStr = JSON.stringify(records.records, null, 2)
      const dataBlob = new Blob([dataStr], { type: "application/json" })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement("a")
      link.href = url
      link.download = `api-key-${apiKeyId}-usage-${new Date().toISOString().split("T")[0]}.json`
      link.click()
      URL.revokeObjectURL(url)
    } else if (format === "csv") {
      const headers = [
        "Timestamp",
        "Provider",
        "Model",
        "Input Tokens",
        "Output Tokens",
        "Total Tokens",
        "Cost (USD)",
        "Status",
        "Latency (ms)",
      ]
      const rows = records.records.map((r) => [
        new Date(r.created_at).toISOString(),
        r.provider_id,
        r.normalized_model,
        r.input_tokens.toString(),
        r.output_tokens.toString(),
        r.total_tokens.toString(),
        r.total_cost_dollars.toFixed(6),
        r.status,
        r.latency_ms?.toString() || "",
      ])

      const csvContent = [
        headers.join(","),
        ...rows.map((row) => row.map((cell) => `"${cell}"`).join(",")),
      ].join("\n")

      const dataBlob = new Blob([csvContent], { type: "text/csv" })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement("a")
      link.href = url
      link.download = `api-key-${apiKeyId}-usage-${new Date().toISOString().split("T")[0]}.csv`
      link.click()
      URL.revokeObjectURL(url)
    }

    toast({
      title: "Export successful",
      description: `Downloaded usage data as ${format.toUpperCase()}`,
      variant: "success",
    })
  }

  // Format helpers
  const formatNumber = (num: number) => num.toLocaleString()
  const formatCurrency = (amount: number) => `$${amount.toFixed(4)}`
  const formatPercent = (percent: number) => `${percent.toFixed(2)}%`
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }
  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.back()}
            className="text-foreground"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </div>
        <div className="text-center py-12">
          <p className="text-muted-foreground">No usage data available</p>
        </div>
      </div>
    )
  }

  const { summary, by_provider, by_model, daily_trend } = stats

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.back()}
            className="text-foreground"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-foreground">API Key Usage Statistics</h1>
            <p className="text-muted-foreground mt-1">API Key ID: {apiKeyId}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchStats(false)}
            disabled={refreshing}
            className="border-border text-foreground hover:bg-accent"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Period Selector */}
      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground">Period:</Label>
        <div className="flex gap-2">
          {(["7d", "30d", "90d"] as Period[]).map((p) => (
            <Button
              key={p}
              variant={period === p ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod(p)}
              className={
                period === p
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "border-border text-foreground hover:bg-accent"
              }
            >
              {p === "7d" ? "Last 7 days" : p === "30d" ? "Last 30 days" : "Last 90 days"}
            </Button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Requests</CardTitle>
            <Activity className="h-4 w-4 text-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {formatNumber(summary.total_requests)}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatNumber(summary.successful_requests)} successful, {formatNumber(summary.failed_requests)} failed
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Tokens</CardTitle>
            <TrendingUp className="h-4 w-4 text-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {formatNumber(summary.total_tokens)}
            </div>
            <p className="text-xs text-muted-foreground">
              {summary.total_requests > 0
                ? `${formatNumber(Math.round(summary.total_tokens / summary.total_requests))} avg per request`
                : "No requests"}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Cost</CardTitle>
            <DollarSign className="h-4 w-4 text-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {formatCurrency(summary.total_cost_dollars)}
            </div>
            <p className="text-xs text-muted-foreground">
              {summary.total_requests > 0
                ? `${formatCurrency(summary.total_cost_dollars / summary.total_requests)} avg per request`
                : "No requests"}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Error Rate</CardTitle>
            {summary.error_rate_percent > 5 ? (
              <AlertCircle className="h-4 w-4 text-danger" />
            ) : (
              <CheckCircle className="h-4 w-4 text-success" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {formatPercent(summary.error_rate_percent)}
            </div>
            <p className="text-xs text-muted-foreground">
              Success rate: {formatPercent(100 - summary.error_rate_percent)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs Section */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="bg-card border border-border">
          <TabsTrigger value="overview" className="data-[state=active]:bg-accent-soft data-[state=active]:text-foreground">
            Overview
          </TabsTrigger>
          <TabsTrigger value="providers" className="data-[state=active]:bg-accent-soft data-[state=active]:text-foreground">
            Providers
          </TabsTrigger>
          <TabsTrigger value="models" className="data-[state=active]:bg-accent-soft data-[state=active]:text-foreground">
            Models
          </TabsTrigger>
          <TabsTrigger value="trends" className="data-[state=active]:bg-accent-soft data-[state=active]:text-foreground">
            Trends
          </TabsTrigger>
          <TabsTrigger value="records" className="data-[state=active]:bg-accent-soft data-[state=active]:text-foreground">
            Records
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Request Breakdown */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-foreground">Request Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Successful</span>
                    <span className="text-sm font-medium text-success">
                      {formatNumber(summary.successful_requests)}
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div
                      className="bg-success h-2 rounded-full"
                      style={{
                        width: `${summary.total_requests > 0 ? (summary.successful_requests / summary.total_requests) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Failed</span>
                    <span className="text-sm font-medium text-danger">
                      {formatNumber(summary.failed_requests)}
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div
                      className="bg-danger h-2 rounded-full"
                      style={{
                        width: `${summary.total_requests > 0 ? (summary.failed_requests / summary.total_requests) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Top Provider */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-foreground">Top Provider</CardTitle>
              </CardHeader>
              <CardContent>
                {by_provider.length > 0 ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-medium text-foreground">
                        {by_provider[0].provider_name}
                      </span>
                      <Badge variant="outline" className="border-border text-foreground">
                        #{1}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Requests</p>
                        <p className="text-foreground font-medium">{formatNumber(by_provider[0].requests)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Tokens</p>
                        <p className="text-foreground font-medium">{formatNumber(by_provider[0].tokens)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Cost</p>
                        <p className="text-foreground font-medium">{formatCurrency(by_provider[0].cost_dollars)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Share</p>
                        <p className="text-foreground font-medium">
                          {formatPercent((by_provider[0].requests / summary.total_requests) * 100)}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground">No provider data</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Providers Tab */}
        <TabsContent value="providers">
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Provider Breakdown</CardTitle>
              <CardDescription>Usage statistics by provider</CardDescription>
            </CardHeader>
            <CardContent>
              {by_provider.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="border-border hover:bg-muted/50">
                      <TableHead className="text-muted-foreground">Provider</TableHead>
                      <TableHead className="text-muted-foreground text-right">Requests</TableHead>
                      <TableHead className="text-muted-foreground text-right">Tokens</TableHead>
                      <TableHead className="text-muted-foreground text-right">Cost</TableHead>
                      <TableHead className="text-muted-foreground text-right">Share</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {by_provider.map((provider) => (
                      <TableRow key={provider.provider_id} className="border-border hover:bg-muted/50">
                        <TableCell className="font-medium text-foreground">
                          {provider.provider_name}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatNumber(provider.requests)}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatNumber(provider.tokens)}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatCurrency(provider.cost_dollars)}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatPercent((provider.requests / summary.total_requests) * 100)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-center py-8 text-muted-foreground">No provider data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Models Tab */}
        <TabsContent value="models">
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Model Breakdown</CardTitle>
              <CardDescription>Usage statistics by model (top 20)</CardDescription>
            </CardHeader>
            <CardContent>
              {by_model.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="border-border hover:bg-muted/50">
                      <TableHead className="text-muted-foreground">Model</TableHead>
                      <TableHead className="text-muted-foreground">Provider</TableHead>
                      <TableHead className="text-muted-foreground text-right">Requests</TableHead>
                      <TableHead className="text-muted-foreground text-right">Tokens</TableHead>
                      <TableHead className="text-muted-foreground text-right">Cost</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {by_model.slice(0, 20).map((model, idx) => (
                      <TableRow key={`${model.provider_id}-${model.model}-${idx}`} className="border-border hover:bg-muted/50">
                        <TableCell className="font-medium text-foreground">
                          {model.model}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{model.provider_id}</TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatNumber(model.requests)}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatNumber(model.tokens)}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {formatCurrency(model.cost_dollars)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-center py-8 text-muted-foreground">No model data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends">
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Daily Usage Trends</CardTitle>
              <CardDescription>Request volume and cost over time</CardDescription>
            </CardHeader>
            <CardContent>
              {daily_trend.length > 0 ? (
                <div className="space-y-6">
                  {/* Simple bar chart visualization */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-muted-foreground">Requests per Day</h4>
                    <div className="space-y-2">
                      {daily_trend.map((day) => {
                        const maxRequests = Math.max(...daily_trend.map((d) => d.requests))
                        const barWidth = maxRequests > 0 ? (day.requests / maxRequests) * 100 : 0
                        return (
                          <div key={day.date} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">{formatDate(day.date)}</span>
                              <span className="text-muted-foreground">{formatNumber(day.requests)}</span>
                            </div>
                            <div className="w-full bg-muted rounded-full h-2">
                              <div
                                className="bg-primary h-2 rounded-full"
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Cost chart */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-muted-foreground">Cost per Day</h4>
                    <div className="space-y-2">
                      {daily_trend.map((day) => {
                        const maxCost = Math.max(...daily_trend.map((d) => d.cost_dollars))
                        const barWidth = maxCost > 0 ? (day.cost_dollars / maxCost) * 100 : 0
                        return (
                          <div key={day.date} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">{formatDate(day.date)}</span>
                              <span className="text-muted-foreground">{formatCurrency(day.cost_dollars)}</span>
                            </div>
                            <div className="w-full bg-muted rounded-full h-2">
                              <div
                                className="bg-success h-2 rounded-full"
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Summary table */}
                  <div className="border-t border-border pt-4">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-border hover:bg-muted/50">
                          <TableHead className="text-muted-foreground">Date</TableHead>
                          <TableHead className="text-muted-foreground text-right">Requests</TableHead>
                          <TableHead className="text-muted-foreground text-right">Tokens</TableHead>
                          <TableHead className="text-muted-foreground text-right">Cost</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {daily_trend.map((day) => (
                          <TableRow key={day.date} className="border-border hover:bg-muted/50">
                            <TableCell className="text-foreground">{formatDate(day.date)}</TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {formatNumber(day.requests)}
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {formatNumber(day.tokens)}
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {formatCurrency(day.cost_dollars)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              ) : (
                <p className="text-center py-8 text-muted-foreground">No trend data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Records Tab */}
        <TabsContent value="records" className="space-y-4">
          {/* Filters */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Filters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Provider</Label>
                  <Input
                    placeholder="Filter by provider"
                    value={providerFilter}
                    onChange={(e) => {
                      setProviderFilter(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="bg-muted border-border text-foreground"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Model</Label>
                  <Input
                    placeholder="Filter by model"
                    value={modelFilter}
                    onChange={(e) => {
                      setModelFilter(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="bg-muted border-border text-foreground"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Status</Label>
                  <Select
                    value={statusFilter}
                    onValueChange={(value) => {
                      setStatusFilter(value)
                      setCurrentPage(1)
                    }}
                  >
                    <SelectTrigger className="bg-muted border-border text-foreground">
                      <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="success">Success</SelectItem>
                      <SelectItem value="error">Error</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">Start Date</Label>
                  <Input
                    type="date"
                    value={startDateFilter}
                    onChange={(e) => {
                      setStartDateFilter(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="bg-muted border-border text-foreground"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">End Date</Label>
                  <Input
                    type="date"
                    value={endDateFilter}
                    onChange={(e) => {
                      setEndDateFilter(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="bg-muted border-border text-foreground"
                  />
                </div>
              </div>
              <div className="flex justify-between items-center mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setProviderFilter("")
                    setModelFilter("")
                    setStatusFilter("all")
                    setStartDateFilter("")
                    setEndDateFilter("")
                    setCurrentPage(1)
                  }}
                  className="border-border text-foreground hover:bg-accent"
                >
                  Clear Filters
                </Button>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => exportData("csv")}
                    disabled={!records || records.records.length === 0}
                    className="border-border text-foreground hover:bg-accent"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => exportData("json")}
                    disabled={!records || records.records.length === 0}
                    className="border-border text-foreground hover:bg-accent"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export JSON
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Records Table */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-foreground">Usage Records</CardTitle>
              <CardDescription>
                {records ? `Showing ${records.records.length} of ${formatNumber(records.total)} records` : "Loading..."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {records && records.records.length > 0 ? (
                <div className="space-y-4">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-border hover:bg-muted/50">
                        <TableHead className="text-muted-foreground w-[40px]"></TableHead>
                        <TableHead className="text-muted-foreground">Timestamp</TableHead>
                        <TableHead className="text-muted-foreground">Provider</TableHead>
                        <TableHead className="text-muted-foreground">Model</TableHead>
                        <TableHead className="text-muted-foreground text-right">Tokens (In/Out)</TableHead>
                        <TableHead className="text-muted-foreground text-right">Cost</TableHead>
                        <TableHead className="text-muted-foreground">Status</TableHead>
                        <TableHead className="text-muted-foreground text-right">Latency</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {records.records.map((record) => (
                        <>
                          <TableRow
                            key={record.id}
                            className="border-border hover:bg-muted/50 cursor-pointer"
                            onClick={() => setExpandedRecordId(expandedRecordId === record.id ? null : record.id)}
                          >
                            <TableCell>
                              {expandedRecordId === record.id ? (
                                <ChevronUp className="h-4 w-4 text-foreground" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-foreground" />
                              )}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-xs">
                              {formatDateTime(record.created_at)}
                            </TableCell>
                            <TableCell className="text-muted-foreground">{record.provider_id}</TableCell>
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {record.normalized_model}
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground text-xs">
                              {formatNumber(record.input_tokens)} / {formatNumber(record.output_tokens)}
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {formatCurrency(record.total_cost_dollars)}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={
                                  record.status === "success"
                                    ? "border-success-border text-success"
                                    : "border-danger-border text-danger"
                                }
                              >
                                {record.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground">
                              {record.latency_ms ? `${record.latency_ms}ms` : "-"}
                            </TableCell>
                          </TableRow>
                          {expandedRecordId === record.id && (
                            <TableRow className="border-border bg-muted/50">
                              <TableCell colSpan={8} className="p-6">
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                                  <div>
                                    <p className="text-muted-foreground text-xs">Request ID</p>
                                    <p className="text-foreground font-mono text-xs">{record.request_id}</p>
                                  </div>
                                  <div>
                                    <p className="text-muted-foreground text-xs">Provider Model</p>
                                    <p className="text-foreground">{record.provider_model}</p>
                                  </div>
                                  <div>
                                    <p className="text-muted-foreground text-xs">Endpoint</p>
                                    <p className="text-foreground">{record.endpoint}</p>
                                  </div>
                                  <div>
                                    <p className="text-muted-foreground text-xs">Method</p>
                                    <p className="text-foreground">{record.method}</p>
                                  </div>
                                  <div>
                                    <p className="text-muted-foreground text-xs">Streaming</p>
                                    <p className="text-foreground">{record.is_streaming ? "Yes" : "No"}</p>
                                  </div>
                                  {record.ttft_ms && (
                                    <div>
                                      <p className="text-muted-foreground text-xs">Time to First Token</p>
                                      <p className="text-foreground">{record.ttft_ms}ms</p>
                                    </div>
                                  )}
                                  <div>
                                    <p className="text-muted-foreground text-xs">Input Cost</p>
                                    <p className="text-foreground">{formatCurrency(record.input_cost_cents / 100)}</p>
                                  </div>
                                  <div>
                                    <p className="text-muted-foreground text-xs">Output Cost</p>
                                    <p className="text-foreground">{formatCurrency(record.output_cost_cents / 100)}</p>
                                  </div>
                                  {record.error_type && (
                                    <div className="col-span-2 md:col-span-3">
                                      <p className="text-muted-foreground text-xs">Error Type</p>
                                      <p className="text-danger">{record.error_type}</p>
                                    </div>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </>
                      ))}
                    </TableBody>
                  </Table>

                  {/* Pagination */}
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-muted-foreground">
                      Page {records.page} of {records.total_pages}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(currentPage - 1)}
                        disabled={currentPage === 1}
                        className="border-border text-foreground hover:bg-accent"
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(currentPage + 1)}
                        disabled={currentPage >= records.total_pages}
                        className="border-border text-foreground hover:bg-accent"
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-center py-8 text-muted-foreground">
                  {records ? "No records found" : "Loading records..."}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
