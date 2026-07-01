"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw, TrendingUp, Users, DollarSign, BarChart3, Activity, AlertCircle, Download } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface AdminUsageOverview {
  summary: {
    total_requests: number;
    total_tokens: number;
    total_cost_dollars: number;
    error_rate_percent: number;
    successful_requests: number;
    failed_requests: number;
    average_response_time_ms: number;
  };
  by_provider: Array<{
    provider_id: string;
    provider_name: string;
    requests: number;
    tokens: number;
    cost_dollars: number;
  }>;
  by_model: Array<{
    model: string;
    provider_id: string;
    requests: number;
    tokens: number;
    cost_dollars: number;
  }>;
  daily_trend: Array<{
    date: string;
    requests: number;
    tokens: number;
    cost_dollars: number;
  }>;
  period_start: string;
  period_end: string;
  total_requests: number;
  total_cost_dollars: number;
}

export default function AdminUsageOverviewPage() {
  const [period, setPeriod] = useState("30d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AdminUsageOverview | null>(null);

  const fetchOverview = async () => {
    try {
      setLoading(true);
      setError(null);

      const periodParam = period === "7d" ? "7" : period === "90d" ? "90" : "30";
      const response = await apiClient.get(
        `/api-internal/v1/usage/admin/overview?period=${periodParam}`
      );

      setData(response);
    } catch (err) {
      console.error("Failed to fetch admin overview:", err);
      setError("Failed to load usage overview");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, [period]);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("en-US").format(value);
  };

  const getPeriodLabel = () => {
    switch (period) {
      case "7d": return "Last 7 days";
      case "30d": return "Last 30 days";
      case "90d": return "Last 90 days";
      default: return "Last 30 days";
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading usage overview...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center space-x-2 text-muted-foreground mb-6">
          <AlertCircle className="h-5 w-5" />
          <span>{error || "Unable to load data"}</span>
        </div>
        <Button onClick={fetchOverview} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">System Usage Overview</h1>
          <p className="text-muted-foreground mt-1">
            System-wide usage statistics across all users
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Badge variant="outline">{getPeriodLabel()}</Badge>
          </div>
          <Button variant="outline" size="icon" onClick={fetchOverview}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon">
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Total Requests"
              value={formatNumber(data.summary.total_requests)}
              icon={<Activity className="h-4 w-4" />}
              trend="+12.5%"
              trendUp
            />
            <StatCard
              title="Total Tokens"
              value={formatNumber(data.summary.total_tokens)}
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              title="Total Cost"
              value={formatCurrency(data.summary.total_cost_dollars)}
              icon={<DollarSign className="h-4 w-4" />}
              trend="+8.2%"
              trendUp
            />
            <StatCard
              title="Error Rate"
              value={`${data.summary.error_rate_percent.toFixed(2)}%`}
              icon={<AlertCircle className="h-4 w-4" />}
              trendDown
            />
            <StatCard
              title="Avg Response Time"
              value={`${(data.summary.average_response_time_ms / 1000).toFixed(0)}s`}
              icon={<BarChart3 className="h-4 w-4" />}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Request Breakdown</CardTitle>
              <CardDescription>Success vs Failure</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-2">
                    <div>
                      <div className="text-sm text-muted-foreground">Successful</div>
                      <div className="text-2xl font-bold text-success">
                        {formatNumber(data.summary.successful_requests)}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">Failed</div>
                      <div className="text-2xl font-bold text-danger">
                        {formatNumber(data.summary.failed_requests)}
                      </div>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">Success Rate</div>
                    <div className="text-2xl font-bold">
                      {(
                        (data.summary.successful_requests / data.summary.total_requests) *
                        100
                      ).toFixed(1)}
                      %
                    </div>
                  </div>
                </div>
                <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-success transition-all duration-500"
                    style={{
                      width: `${(data.summary.successful_requests / data.summary.total_requests) * 100}%`,
                    }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="providers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Provider Breakdown</CardTitle>
              <CardDescription>Usage and costs by provider</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.by_provider.map((provider, idx) => (
                  <div key={idx} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex-1">
                      <div className="font-medium text-lg">{provider.provider_name}</div>
                      <div className="text-sm text-muted-foreground">
                        {provider.provider_id}
                      </div>
                    </div>
                    <div className="flex-1 text-right space-y-2">
                      <div className="text-sm text-muted-foreground">Requests</div>
                      <div className="text-xl font-bold">{formatNumber(provider.requests)}</div>
                      <div className="text-sm text-muted-foreground">Tokens</div>
                      <div className="text-xl font-bold">{formatNumber(provider.tokens)}</div>
                      <div className="text-sm text-muted-foreground">Cost</div>
                      <div className="text-xl font-bold">{formatCurrency(provider.cost_dollars)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="models" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Model Breakdown</CardTitle>
              <CardDescription>Top models by usage and cost</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.by_model.slice(0, 10).map((model, idx) => (
                  <div key={idx} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex-1">
                      <div className="font-medium text-lg">{model.model}</div>
                      <div className="text-sm text-muted-foreground">{model.provider_id}</div>
                    </div>
                    <div className="flex-1 text-right space-y-2">
                      <div className="text-sm text-muted-foreground">Requests</div>
                      <div className="text-xl font-bold">{formatNumber(model.requests)}</div>
                      <div className="text-sm text-muted-foreground">Tokens</div>
                      <div className="text-xl font-bold">{formatNumber(model.tokens)}</div>
                      <div className="text-sm text-muted-foreground">Cost</div>
                      <div className="text-xl font-bold">{formatCurrency(model.cost_dollars)}</div>
                    </div>
                  </div>
                ))}
                {data.by_model.length > 10 && (
                  <div className="text-center text-sm text-muted-foreground mt-4">
                    Showing top 10 of {data.by_model.length} models
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Daily Trend</CardTitle>
              <CardDescription>
                {new Date(data.period_start).toLocaleDateString()} -{" "}
                {new Date(data.period_end).toLocaleDateString()}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <div className="space-y-2">
                  {data.daily_trend.map((day, idx) => (
                    <div key={idx} className="flex items-end space-x-2">
                      <div className="flex-1 text-right text-xs text-muted-foreground">
                        {day.date}
                      </div>
                      <div className="flex-[2px] bg-info rounded-t" style={{ height: `${Math.max(20, (day.requests / data.total_requests) * 60)}px` }} />
                      <div className="flex-1 text-right">
                        <div className="text-xs font-medium">{formatNumber(day.requests)} req</div>
                        <div className="text-xs text-muted-foreground">${formatCurrency(day.cost_dollars)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  trend,
  trendUp,
  trendDown,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
  trendDown?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center space-y-0 pb-2">
          {icon}
          <span className="text-sm font-medium">{title}</span>
          {trend && (
            <div
              className={`text-xs ${
                trendUp ? "text-success" : trendDown ? "text-danger" : ""
              }`}
            >
              {trend}
            </div>
          )}
        </div>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}
