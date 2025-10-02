"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { 
  Activity, 
  Users, 
  MessageSquare, 
  DollarSign, 
  TrendingUp, 
  Clock, 
  AlertCircle,
  BarChart3,
  PieChart,
  RefreshCw
} from 'lucide-react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { apiClient } from '@/lib/api-client'

interface AnalyticsData {
  overview: {
    totalUsers: number;
    totalRequests: number;
    totalCost: number;
    averageResponseTime: number;
  };
  usage: {
    requests: Array<{ date: string; count: number }>;
    models: Array<{ name: string; count: number; cost: number }>;
    endpoints: Array<{ path: string; count: number; avgTime: number }>;
  };
  performance: {
    responseTime: Array<{ time: string; value: number }>;
    errorRate: number;
    uptime: number;
  };
  costs: {
    daily: Array<{ date: string; amount: number }>;
    byModel: Array<{ model: string; cost: number; percentage: number }>;
    budget: { used: number; limit: number };
  };
}

export default function AnalyticsPage() {
  return (
    <ProtectedRoute>
      <AnalyticsPageContent />
    </ProtectedRoute>
  )
}

function AnalyticsPageContent() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      
      // Fetch real analytics data from backend API via proxy
      const analyticsData = await apiClient.get('/api-internal/v1/analytics') as any;
      setData(analyticsData);
      setLastUpdated(new Date());
    } catch (error) {
      // Set empty data structure on error
      setData({
        overview: {
          totalUsers: 0,
          totalRequests: 0,
          totalCost: 0,
          averageResponseTime: 0
        },
        usage: {
          requests: [],
          models: [],
          endpoints: []
        },
        performance: {
          responseTime: [],
          errorRate: 0,
          uptime: 0
        },
        costs: {
          daily: [],
          byModel: [],
          budget: { used: 0, limit: 0 }
        }
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Failed to load analytics</h3>
          <p className="text-sm text-muted-foreground">Please try again later</p>
          <Button onClick={fetchAnalytics} className="mt-4">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Analytics</h1>
          <p className="text-muted-foreground">
            Platform usage and performance insights
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-sm text-muted-foreground">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
          <Button onClick={fetchAnalytics} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.overview.totalUsers}</div>
            <p className="text-xs text-muted-foreground">
              {data.overview.totalUsers > 0 ? 'Active users' : 'No users yet'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.overview.totalRequests.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              {data.overview.totalRequests > 0 ? 'Total API requests' : 'No requests yet'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Cost</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${data.overview.totalCost.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">
              {data.overview.totalCost > 0 ? 'Total spending' : 'No costs yet'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.overview.averageResponseTime.toFixed(2)}s</div>
            <p className="text-xs text-muted-foreground">
              {data.overview.averageResponseTime > 0 ? 'Average response time' : 'No data available'}
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="usage" className="space-y-4">
        <TabsList>
          <TabsTrigger value="usage">Usage</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="costs">Costs</TabsTrigger>
        </TabsList>

        <TabsContent value="usage" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <BarChart3 className="w-4 h-4 mr-2" />
                  Model Usage
                </CardTitle>
                <CardDescription>Requests by AI model</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {data.usage.models.map((model) => (
                    <div key={model.name} className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Badge variant="secondary">{model.name}</Badge>
                        <span className="text-sm text-muted-foreground">
                          {model.count.toLocaleString()} requests
                        </span>
                      </div>
                      <div className="text-sm font-medium">${model.cost}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Activity className="w-4 h-4 mr-2" />
                  Endpoint Performance
                </CardTitle>
                <CardDescription>API endpoint statistics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {data.usage.endpoints.map((endpoint) => (
                    <div key={endpoint.path} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <code className="text-sm bg-muted px-2 py-1 rounded">
                          {endpoint.path}
                        </code>
                        <div className="text-sm text-muted-foreground">
                          {endpoint.avgTime}s avg
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span>{endpoint.count.toLocaleString()} requests</span>
                        <Progress 
                          value={(endpoint.count / data.overview.totalRequests) * 100} 
                          className="w-20 h-2" 
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <TrendingUp className="w-4 h-4 mr-2" />
                  System Health
                </CardTitle>
                <CardDescription>Platform performance metrics</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Uptime</span>
                  <div className="flex items-center space-x-2">
                    <Badge variant="outline" className="text-green-600">
                      {data.performance.uptime}%
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Error Rate</span>
                  <div className="flex items-center space-x-2">
                    <Badge variant="outline" className="text-orange-600">
                      {(data.performance.errorRate * 100).toFixed(2)}%
                    </Badge>
                  </div>
                </div>
                <Separator />
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Uptime</span>
                    <span className="text-sm text-muted-foreground">{data.performance.uptime}%</span>
                  </div>
                  <Progress value={data.performance.uptime} className="h-2" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Clock className="w-4 h-4 mr-2" />
                  Response Times
                </CardTitle>
                <CardDescription>24-hour response time trend</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {data.performance.responseTime.map((item) => (
                    <div key={item.time} className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{item.time}</span>
                      <div className="flex items-center space-x-2">
                        <Progress 
                          value={(item.value / 3) * 100} 
                          className="w-20 h-2" 
                        />
                        <span className="text-sm font-medium">{item.value}s</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="costs" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <DollarSign className="w-4 h-4 mr-2" />
                  Budget Status
                </CardTitle>
                <CardDescription>Current month spending</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Used</span>
                    <span className="text-sm text-muted-foreground">
                      ${data.costs.budget.used} / ${data.costs.budget.limit}
                    </span>
                  </div>
                  <Progress 
                    value={(data.costs.budget.used / data.costs.budget.limit) * 100} 
                    className="h-2" 
                  />
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">
                    ${data.costs.budget.limit - data.costs.budget.used} remaining
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {Math.round(((data.costs.budget.limit - data.costs.budget.used) / data.costs.budget.limit) * 100)}% of budget left
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <PieChart className="w-4 h-4 mr-2" />
                  Cost by Model
                </CardTitle>
                <CardDescription>Spending distribution</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {data.costs.byModel.map((model) => (
                    <div key={model.model} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Badge variant="secondary">{model.model}</Badge>
                        <span className="text-sm font-medium">${model.cost}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{model.percentage}%</span>
                        <Progress value={model.percentage} className="w-20 h-2" />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
