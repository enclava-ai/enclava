"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Database, 
  Play, 
  Square, 
  RefreshCw, 
  Settings, 
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Cpu,
  BarChart3
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { useModules, triggerModuleRefresh } from '@/contexts/ModulesContext'
import { apiClient } from '@/lib/api-client'

interface Module {
  name: string;
  status: "loaded" | "failed" | "disabled";
  dependencies: string[];
  config: Record<string, any>;
  metrics?: {
    requests_processed: number;
    average_response_time: number;
    error_rate: number;
    last_activity: string;
  };
  health?: {
    status: "healthy" | "warning" | "error";
    message: string;
    uptime: number;
  };
}

interface ModuleStats {
  total_modules: number;
  loaded_modules: number;
  failed_modules: number;
  system_health: "healthy" | "warning" | "error";
}

export default function ModulesPage() {
  return (
    <ProtectedRoute>
      <ModulesPageContent />
    </ProtectedRoute>
  )
}

function ModulesPageContent() {
  const { toast } = useToast();
  const { modules: contextModules, isLoading: contextLoading, refreshModules } = useModules();
  const [stats, setStats] = useState<ModuleStats | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Transform context modules to match existing interface
  const modules: Module[] = contextModules.map(module => ({
    name: module.name,
    status: module.initialized && module.enabled ? "loaded" : 
            !module.enabled ? "disabled" : "failed",
    dependencies: [], // Not provided in current API
    config: module.stats || {},
    metrics: {
      requests_processed: module.stats?.total_requests || 0,
      average_response_time: module.stats?.avg_analysis_time || 0,
      error_rate: module.stats?.errors || 0,
      last_activity: new Date().toISOString(),
    },
    health: {
      status: module.initialized && module.enabled ? "healthy" : "error",
      message: module.initialized && module.enabled ? "Module is running" : 
               !module.enabled ? "Module is disabled" : "Module failed to initialize",
      uptime: module.stats?.uptime || 0,
    }
  }));

  const loading = contextLoading;

  useEffect(() => {
    // Calculate stats from context modules
    setStats({
      total_modules: contextModules.length,
      loaded_modules: contextModules.filter(m => m.initialized && m.enabled).length,
      failed_modules: contextModules.filter(m => !m.initialized || !m.enabled).length,
      system_health: contextModules.some(m => !m.initialized) ? "warning" : "healthy"
    });
  }, [contextModules]);


  const handleModuleAction = async (moduleName: string, action: "start" | "stop" | "restart" | "reload") => {
    try {
      setActionLoading(`${moduleName}-${action}`);

      const responseData = await apiClient.post(`/api-internal/v1/modules/${moduleName}/${action}`, {});

      toast({
        title: "Success",
        description: `Module ${moduleName} ${action}ed successfully`,
      });

      // Refresh modules context and trigger navigation update
      await refreshModules();
      
      // Trigger navigation refresh if the response indicates it's needed
      if (responseData.refreshRequired) {
        triggerModuleRefresh();
      }
    } catch (error) {
      console.error(`Failed to ${action} module:`, error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : `Failed to ${action} module`,
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleModuleToggle = async (moduleName: string, enabled: boolean) => {
    await handleModuleAction(moduleName, enabled ? "start" : "stop");
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "loaded":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case "disabled":
        return <Square className="h-4 w-4 text-gray-500" />;
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      loaded: "default",
      failed: "destructive",
      disabled: "secondary"
    };
    return <Badge variant={variants[status] || "outline"}>{status}</Badge>;
  };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Module Manager</h1>
          <p className="text-muted-foreground">
            Manage dynamic modules and monitor system performance
          </p>
        </div>
        <div className="flex space-x-2">
          <Button onClick={refreshModules} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={() => handleModuleAction("all", "reload")}>
            <Database className="mr-2 h-4 w-4" />
            Reload All
          </Button>
        </div>
      </div>

      {/* System Health Alert */}
      {stats && stats.system_health !== "healthy" && (
        <Alert className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            System health: {stats.system_health}. Some modules may not be functioning properly.
          </AlertDescription>
        </Alert>
      )}

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Modules</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_modules || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Loaded</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats?.loaded_modules || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats?.failed_modules || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            {getStatusIcon(stats?.system_health || "unknown")}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{stats?.system_health || "Unknown"}</div>
          </CardContent>
        </Card>
      </div>

      {/* Modules List */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {modules.map((module) => (
            <Card key={module.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    {getStatusIcon(module.status)}
                    <div>
                      <CardTitle className="text-lg">{module.name}</CardTitle>
                      <CardDescription>
                        Dependencies: {module.dependencies.length > 0 ? module.dependencies.join(", ") : "None"}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    {getStatusBadge(module.status)}
                    <Switch
                      checked={module.status === "loaded"}
                      onCheckedChange={(checked) => handleModuleToggle(module.name, checked)}
                      disabled={actionLoading?.startsWith(module.name)}
                    />
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-2 mb-4">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleModuleAction(module.name, "restart")}
                    disabled={actionLoading === `${module.name}-restart`}
                  >
                    <RefreshCw className="mr-2 h-3 w-3" />
                    Restart
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleModuleAction(module.name, "reload")}
                    disabled={actionLoading === `${module.name}-reload`}
                  >
                    <Database className="mr-2 h-3 w-3" />
                    Reload
                  </Button>
                  {module.name === 'signal' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => window.location.href = '/signal'}
                    >
                      <Settings className="mr-2 h-3 w-3" />
                      Configure
                    </Button>
                  )}
                  {module.name === 'zammad' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => window.location.href = '/zammad'}
                    >
                      <Settings className="mr-2 h-3 w-3" />
                      Configure
                    </Button>
                  )}
                </div>

                {module.health && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="font-medium">Health:</span> {module.health.status}
                    </div>
                    <div>
                      <span className="font-medium">Uptime:</span> {formatUptime(module.health.uptime)}
                    </div>
                    <div>
                      <span className="font-medium">Message:</span> {module.health.message}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          {modules
            .filter((module) => module.metrics)
            .map((module) => (
              <Card key={module.name}>
                <CardHeader>
                  <CardTitle className="flex items-center">
                    <BarChart3 className="mr-2 h-5 w-5" />
                    {module.name} Performance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold">{module.metrics?.requests_processed || 0}</div>
                      <p className="text-xs text-muted-foreground">Requests Processed</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">{module.metrics?.average_response_time || 0}ms</div>
                      <p className="text-xs text-muted-foreground">Avg Response Time</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">{(module.metrics?.error_rate || 0).toFixed(2)}%</div>
                      <p className="text-xs text-muted-foreground">Error Rate</p>
                    </div>
                    <div className="text-center">
                      <div className="text-sm font-medium">
                        {module.metrics?.last_activity ? 
                          new Date(module.metrics.last_activity).toLocaleString() : 
                          "Never"
                        }
                      </div>
                      <p className="text-xs text-muted-foreground">Last Activity</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
        </TabsContent>

        <TabsContent value="configuration" className="space-y-4">
          {modules.map((module) => (
            <Card key={module.name}>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Settings className="mr-2 h-5 w-5" />
                  {module.name} Configuration
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted p-4 rounded-lg text-sm overflow-auto">
                  {JSON.stringify(module.config, null, 2)}
                </pre>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}