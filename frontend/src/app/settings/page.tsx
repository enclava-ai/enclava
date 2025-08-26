"use client";

import { useState, useEffect } from "react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Settings, 
  Save, 
  RefreshCw,
  Shield,
  Globe,
  Database,
  Mail,
  Bell,
  Key,
  Lock,
  Server,
  AlertTriangle,
  CheckCircle,
  Info,
  Square,
  Clock,
  Play
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api-client";
import { useModules, triggerModuleRefresh } from '@/contexts/ModulesContext';
import { Badge } from '@/components/ui/badge';

interface SystemSettings {
  // Security Settings
  security: {
    password_min_length: number;
    password_require_uppercase: boolean;
    password_require_lowercase: boolean;
    password_require_numbers: boolean;
    password_require_symbols: boolean;
    session_timeout_minutes: number;
    max_login_attempts: number;
    lockout_duration_minutes: number;
    require_2fa: boolean;
    allowed_domains: string[];
  };

  // API Settings
  api: {
    // Security Settings
    security_enabled: boolean;
    threat_detection_enabled: boolean;
    rate_limiting_enabled: boolean;
    ip_reputation_enabled: boolean;
    anomaly_detection_enabled: boolean;
    security_headers_enabled: boolean;
    
    // Rate Limiting by Authentication Level
    rate_limit_authenticated_per_minute: number;
    rate_limit_authenticated_per_hour: number;
    rate_limit_api_key_per_minute: number;
    rate_limit_api_key_per_hour: number;
    rate_limit_premium_per_minute: number;
    rate_limit_premium_per_hour: number;
    
    // Security Thresholds
    security_risk_threshold: number;
    security_warning_threshold: number;
    anomaly_threshold: number;
    
    // Request Settings
    max_request_size_mb: number;
    max_request_size_premium_mb: number;
    enable_cors: boolean;
    cors_origins: string[];
    api_key_expiry_days: number;
    
    // IP Security
    blocked_ips: string[];
    allowed_ips: string[];
    csp_header: string;
  };

  // Notification Settings
  notifications: {
    email_enabled: boolean;
    smtp_host: string;
    smtp_port: number;
    smtp_username: string;
    smtp_use_tls: boolean;
    from_address: string;
    budget_alerts: boolean;
    security_alerts: boolean;
    system_alerts: boolean;
  };
}

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

function SettingsPageContent() {
  const { toast } = useToast();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  
  // Modules state
  const { modules: contextModules, isLoading: modulesLoading, refreshModules } = useModules();
  const [moduleStats, setModuleStats] = useState<ModuleStats | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

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

  useEffect(() => {
    // Calculate stats from context modules
    setModuleStats({
      total_modules: contextModules.length,
      loaded_modules: contextModules.filter(m => m.initialized && m.enabled).length,
      failed_modules: contextModules.filter(m => !m.initialized || !m.enabled).length,
      system_health: contextModules.some(m => !m.initialized) ? "warning" : "healthy"
    });
  }, [contextModules]);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      
      const data = await apiClient.get("/api-internal/v1/settings/");
      
      // Transform backend format to frontend format
      const transformedSettings = {} as SystemSettings;
      
      // Transform each category from backend format {key: {value, type, description}} 
      // to frontend format {key: value}
      for (const [categoryName, categorySettings] of Object.entries(data)) {
        if (typeof categorySettings === 'object' && categorySettings !== null) {
          transformedSettings[categoryName as keyof SystemSettings] = {} as any;
          
          for (const [key, setting] of Object.entries(categorySettings as any)) {
            if (typeof setting === 'object' && setting !== null && 'value' in setting) {
              transformedSettings[categoryName as keyof SystemSettings][key] = setting.value;
            }
          }
        }
      }
      
      setSettings(transformedSettings);
      setIsDirty(false);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to fetch system settings",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const updateSetting = (category: keyof SystemSettings, key: string, value: any) => {
    if (!settings) return;

    const newSettings = {
      ...settings,
      [category]: {
        ...settings[category],
        [key]: value
      }
    };

    setSettings(newSettings);
    setIsDirty(true);
  };

  const handleSaveSection = async (category: keyof SystemSettings) => {
    if (!settings) return;

    try {
      setSaving(category);
      
      await apiClient.put(`/api-internal/v1/settings/${category}`, settings[category]);

      toast({
        title: "Settings Saved",
        description: `${category.charAt(0).toUpperCase() + category.slice(1)} settings have been updated successfully`,
      });

      setIsDirty(false);
    } catch (error) {
      toast({
        title: "Save Failed",
        description: error instanceof Error ? error.message : "Failed to save settings",
        variant: "destructive",
      });
    } finally {
      setSaving(null);
    }
  };

  const handleTestConnection = async (type: "smtp") => {
    try {
      await apiClient.post(`/api-internal/v1/settings/test-connection/${type}`, {});

      toast({
        title: "Connection Test Successful",
        description: `${type.toUpperCase()} connection is working properly`,
      });
    } catch (error) {
      toast({
        title: "Connection Test Failed",
        description: error instanceof Error ? error.message : `Failed to test ${type} connection`,
        variant: "destructive",
      });
    }
  };

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

  if (!settings) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <AlertTriangle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Settings Not Available</h2>
            <p className="text-muted-foreground mb-4">Unable to load system settings. Please try again.</p>
            <Button onClick={fetchSettings} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">System Settings</h1>
          <p className="text-muted-foreground">
            Configure global platform settings and preferences
          </p>
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={fetchSettings}
            disabled={loading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {isDirty && (
        <Alert className="mb-6">
          <Info className="h-4 w-4" />
          <AlertDescription>
            You have unsaved changes. Remember to save each section after making modifications.
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="security" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="api">API</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="modules">Modules</TabsTrigger>
        </TabsList>

        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Shield className="mr-2 h-5 w-5" />
                Security Settings
              </CardTitle>
              <CardDescription>
                Configure password policies, session management, and authentication settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Password Policy</h3>
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor="password-min-length">Minimum Password Length</Label>
                      <Input
                        id="password-min-length"
                        type="number"
                        min="6"
                        max="50"
                        value={settings.security.password_min_length}
                        onChange={(e) => updateSetting("security", "password_min_length", parseInt(e.target.value))}
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={settings.security.password_require_uppercase}
                          onCheckedChange={(checked) => updateSetting("security", "password_require_uppercase", checked)}
                        />
                        <Label>Require uppercase letters</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={settings.security.password_require_lowercase}
                          onCheckedChange={(checked) => updateSetting("security", "password_require_lowercase", checked)}
                        />
                        <Label>Require lowercase letters</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={settings.security.password_require_numbers}
                          onCheckedChange={(checked) => updateSetting("security", "password_require_numbers", checked)}
                        />
                        <Label>Require numbers</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={settings.security.password_require_symbols}
                          onCheckedChange={(checked) => updateSetting("security", "password_require_symbols", checked)}
                        />
                        <Label>Require special characters</Label>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Session & Authentication</h3>
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor="session-timeout">Session Timeout (minutes)</Label>
                      <Input
                        id="session-timeout"
                        type="number"
                        min="5"
                        max="1440"
                        value={settings.security.session_timeout_minutes}
                        onChange={(e) => updateSetting("security", "session_timeout_minutes", parseInt(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="max-login-attempts">Max Login Attempts</Label>
                      <Input
                        id="max-login-attempts"
                        type="number"
                        min="3"
                        max="10"
                        value={settings.security.max_login_attempts}
                        onChange={(e) => updateSetting("security", "max_login_attempts", parseInt(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="lockout-duration">Lockout Duration (minutes)</Label>
                      <Input
                        id="lockout-duration"
                        type="number"
                        min="5"
                        max="60"
                        value={settings.security.lockout_duration_minutes}
                        onChange={(e) => updateSetting("security", "lockout_duration_minutes", parseInt(e.target.value))}
                      />
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.security.require_2fa}
                        onCheckedChange={(checked) => updateSetting("security", "require_2fa", checked)}
                      />
                      <Label>Require Two-Factor Authentication</Label>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <Label htmlFor="allowed-domains">Allowed Email Domains (one per line)</Label>
                <Textarea
                  id="allowed-domains"
                  value={settings.security.allowed_domains.join('\n')}
                  onChange={(e) => updateSetting("security", "allowed_domains", e.target.value.split('\n').filter(d => d.trim()))}
                  placeholder="example.com&#10;company.org"
                  rows={3}
                />
              </div>

              <Button
                onClick={() => handleSaveSection("security")}
                disabled={saving === "security"}
              >
                <Save className="mr-2 h-4 w-4" />
                {saving === "security" ? "Saving..." : "Save Security Settings"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Globe className="mr-2 h-5 w-5" />
                API & Security Settings
              </CardTitle>
              <CardDescription>
                Configure API security, rate limits, threat detection, and request handling
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Security Features */}
              <div className="space-y-4">
                <h3 className="text-lg font-medium flex items-center">
                  <Shield className="mr-2 h-5 w-5" />
                  Security Features
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.security_enabled}
                        onCheckedChange={(checked) => updateSetting("api", "security_enabled", checked)}
                      />
                      <Label>Enable API Security</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.threat_detection_enabled}
                        onCheckedChange={(checked) => updateSetting("api", "threat_detection_enabled", checked)}
                      />
                      <Label>Threat Detection</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.rate_limiting_enabled}
                        onCheckedChange={(checked) => updateSetting("api", "rate_limiting_enabled", checked)}
                      />
                      <Label>Rate Limiting</Label>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.ip_reputation_enabled}
                        onCheckedChange={(checked) => updateSetting("api", "ip_reputation_enabled", checked)}
                      />
                      <Label>IP Reputation Checking</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.anomaly_detection_enabled}
                        onCheckedChange={(checked) => updateSetting("api", "anomaly_detection_enabled", checked)}
                      />
                      <Label>Anomaly Detection</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.security_headers_enabled}
                        onCheckedChange={(checked) => updateSetting("api", "security_headers_enabled", checked)}
                      />
                      <Label>Security Headers</Label>
                    </div>
                  </div>
                </div>
              </div>

              {/* Rate Limiting by Authentication Level */}
              {settings.api.rate_limiting_enabled && (
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Rate Limiting by Authentication Level</h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <div className="space-y-3">
                        <h4 className="font-medium text-sm text-muted-foreground">Authenticated Users</h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label htmlFor="auth-minute">Per Minute</Label>
                            <Input
                              id="auth-minute"
                              type="number"
                              min="1"
                              value={settings.api.rate_limit_authenticated_per_minute}
                              onChange={(e) => updateSetting("api", "rate_limit_authenticated_per_minute", parseInt(e.target.value))}
                            />
                          </div>
                          <div>
                            <Label htmlFor="auth-hour">Per Hour</Label>
                            <Input
                              id="auth-hour"
                              type="number"
                              min="1"
                              value={settings.api.rate_limit_authenticated_per_hour}
                              onChange={(e) => updateSetting("api", "rate_limit_authenticated_per_hour", parseInt(e.target.value))}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="space-y-3">
                        <h4 className="font-medium text-sm text-muted-foreground">API Key Users</h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label htmlFor="api-minute">Per Minute</Label>
                            <Input
                              id="api-minute"
                              type="number"
                              min="1"
                              value={settings.api.rate_limit_api_key_per_minute}
                              onChange={(e) => updateSetting("api", "rate_limit_api_key_per_minute", parseInt(e.target.value))}
                            />
                          </div>
                          <div>
                            <Label htmlFor="api-hour">Per Hour</Label>
                            <Input
                              id="api-hour"
                              type="number"
                              min="1"
                              value={settings.api.rate_limit_api_key_per_hour}
                              onChange={(e) => updateSetting("api", "rate_limit_api_key_per_hour", parseInt(e.target.value))}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h4 className="font-medium text-sm text-muted-foreground">Premium Users</h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label htmlFor="premium-minute">Per Minute</Label>
                            <Input
                              id="premium-minute"
                              type="number"
                              min="1"
                              value={settings.api.rate_limit_premium_per_minute}
                              onChange={(e) => updateSetting("api", "rate_limit_premium_per_minute", parseInt(e.target.value))}
                            />
                          </div>
                          <div>
                            <Label htmlFor="premium-hour">Per Hour</Label>
                            <Input
                              id="premium-hour"
                              type="number"
                              min="1"
                              value={settings.api.rate_limit_premium_per_hour}
                              onChange={(e) => updateSetting("api", "rate_limit_premium_per_hour", parseInt(e.target.value))}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Security Thresholds */}
              {settings.api.security_enabled && (
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Security Thresholds</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label htmlFor="risk-threshold">Risk Threshold (Block)</Label>
                      <Input
                        id="risk-threshold"
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        value={settings.api.security_risk_threshold}
                        onChange={(e) => updateSetting("api", "security_risk_threshold", parseFloat(e.target.value))}
                      />
                      <p className="text-xs text-muted-foreground mt-1">Requests above this score are blocked</p>
                    </div>
                    <div>
                      <Label htmlFor="warning-threshold">Warning Threshold</Label>
                      <Input
                        id="warning-threshold"
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        value={settings.api.security_warning_threshold}
                        onChange={(e) => updateSetting("api", "security_warning_threshold", parseFloat(e.target.value))}
                      />
                      <p className="text-xs text-muted-foreground mt-1">Requests above this score generate warnings</p>
                    </div>
                    <div>
                      <Label htmlFor="anomaly-threshold">Anomaly Threshold</Label>
                      <Input
                        id="anomaly-threshold"
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        value={settings.api.anomaly_threshold}
                        onChange={(e) => updateSetting("api", "anomaly_threshold", parseFloat(e.target.value))}
                      />
                      <p className="text-xs text-muted-foreground mt-1">Anomalies above this threshold are flagged</p>
                    </div>
                  </div>
                </div>
              )}

              {/* IP Security */}
              {settings.api.security_enabled && (
                <div className="space-y-4">
                  <h3 className="text-lg font-medium">IP Security</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <Label htmlFor="blocked-ips">Blocked IPs (one per line)</Label>
                      <Textarea
                        id="blocked-ips"
                        value={settings.api.blocked_ips.join('\n')}
                        onChange={(e) => updateSetting("api", "blocked_ips", e.target.value.split('\n').filter(ip => ip.trim()))}
                        placeholder="192.168.1.100&#10;10.0.0.50"
                        rows={3}
                      />
                    </div>
                    <div>
                      <Label htmlFor="allowed-ips">Allowed IPs (empty = allow all)</Label>
                      <Textarea
                        id="allowed-ips"
                        value={settings.api.allowed_ips.join('\n')}
                        onChange={(e) => updateSetting("api", "allowed_ips", e.target.value.split('\n').filter(ip => ip.trim()))}
                        placeholder="192.168.1.0/24&#10;10.0.0.1"
                        rows={3}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Request Settings */}
              <div className="space-y-4">
                <h3 className="text-lg font-medium">Request Settings</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor="max-request-size">Max Request Size (MB)</Label>
                      <Input
                        id="max-request-size"
                        type="number"
                        min="1"
                        max="100"
                        value={settings.api.max_request_size_mb}
                        onChange={(e) => updateSetting("api", "max_request_size_mb", parseInt(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="max-request-size-premium">Max Request Size Premium (MB)</Label>
                      <Input
                        id="max-request-size-premium"
                        type="number"
                        min="1"
                        max="500"
                        value={settings.api.max_request_size_premium_mb}
                        onChange={(e) => updateSetting("api", "max_request_size_premium_mb", parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor="api-key-expiry">API Key Expiry (days)</Label>
                      <Input
                        id="api-key-expiry"
                        type="number"
                        min="1"
                        max="365"
                        value={settings.api.api_key_expiry_days}
                        onChange={(e) => updateSetting("api", "api_key_expiry_days", parseInt(e.target.value))}
                      />
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={settings.api.enable_cors}
                        onCheckedChange={(checked) => updateSetting("api", "enable_cors", checked)}
                      />
                      <Label>Enable CORS</Label>
                    </div>
                  </div>
                </div>
              </div>

              {/* CORS Settings */}
              {settings.api.enable_cors && (
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="cors-origins">CORS Origins (one per line)</Label>
                    <Textarea
                      id="cors-origins"
                      value={settings.api.cors_origins.join('\n')}
                      onChange={(e) => updateSetting("api", "cors_origins", e.target.value.split('\n').filter(o => o.trim()))}
                      placeholder="https://example.com&#10;https://app.company.org"
                      rows={3}
                    />
                  </div>
                </div>
              )}

              {/* Security Headers */}
              {settings.api.security_headers_enabled && (
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="csp-header">Content Security Policy Header</Label>
                    <Textarea
                      id="csp-header"
                      value={settings.api.csp_header}
                      onChange={(e) => updateSetting("api", "csp_header", e.target.value)}
                      placeholder="default-src 'self'; script-src 'self' 'unsafe-inline';"
                      rows={2}
                    />
                  </div>
                </div>
              )}

              <Button
                onClick={() => handleSaveSection("api")}
                disabled={saving === "api"}
              >
                <Save className="mr-2 h-4 w-4" />
                {saving === "api" ? "Saving..." : "Save API & Security Settings"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Mail className="mr-2 h-5 w-5" />
                Notification Settings
              </CardTitle>
              <CardDescription>
                Configure email notifications and SMTP settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center space-x-2">
                <Switch
                  checked={settings.notifications.email_enabled}
                  onCheckedChange={(checked) => updateSetting("notifications", "email_enabled", checked)}
                />
                <Label>Enable Email Notifications</Label>
              </div>

              {settings.notifications.email_enabled && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">SMTP Configuration</h3>
                      <div className="space-y-3">
                        <div>
                          <Label htmlFor="smtp-host">SMTP Host</Label>
                          <Input
                            id="smtp-host"
                            value={settings.notifications.smtp_host}
                            onChange={(e) => updateSetting("notifications", "smtp_host", e.target.value)}
                            placeholder="smtp.gmail.com"
                          />
                        </div>
                        <div>
                          <Label htmlFor="smtp-port">SMTP Port</Label>
                          <Input
                            id="smtp-port"
                            type="number"
                            value={settings.notifications.smtp_port}
                            onChange={(e) => updateSetting("notifications", "smtp_port", parseInt(e.target.value))}
                          />
                        </div>
                        <div>
                          <Label htmlFor="smtp-username">SMTP Username</Label>
                          <Input
                            id="smtp-username"
                            value={settings.notifications.smtp_username}
                            onChange={(e) => updateSetting("notifications", "smtp_username", e.target.value)}
                          />
                        </div>
                        <div className="flex items-center space-x-2">
                          <Switch
                            checked={settings.notifications.smtp_use_tls}
                            onCheckedChange={(checked) => updateSetting("notifications", "smtp_use_tls", checked)}
                          />
                          <Label>Use TLS</Label>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">Email Settings</h3>
                      <div className="space-y-3">
                        <div>
                          <Label htmlFor="from-address">From Address</Label>
                          <Input
                            id="from-address"
                            type="email"
                            value={settings.notifications.from_address}
                            onChange={(e) => updateSetting("notifications", "from_address", e.target.value)}
                            placeholder="noreply@company.com"
                          />
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center space-x-2">
                            <Switch
                              checked={settings.notifications.budget_alerts}
                              onCheckedChange={(checked) => updateSetting("notifications", "budget_alerts", checked)}
                            />
                            <Label>Budget Alerts</Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              checked={settings.notifications.security_alerts}
                              onCheckedChange={(checked) => updateSetting("notifications", "security_alerts", checked)}
                            />
                            <Label>Security Alerts</Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              checked={settings.notifications.system_alerts}
                              onCheckedChange={(checked) => updateSetting("notifications", "system_alerts", checked)}
                            />
                            <Label>System Alerts</Label>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      onClick={() => handleTestConnection("smtp")}
                    >
                      Test SMTP Connection
                    </Button>
                  </div>
                </>
              )}

              <Button
                onClick={() => handleSaveSection("notifications")}
                disabled={saving === "notifications"}
              >
                <Save className="mr-2 h-4 w-4" />
                {saving === "notifications" ? "Saving..." : "Save Notification Settings"}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="modules" className="space-y-6">
          {/* System Health Alert */}
          {moduleStats && moduleStats.system_health !== "healthy" && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                System health: {moduleStats.system_health}. Some modules may not be functioning properly.
              </AlertDescription>
            </Alert>
          )}

          {/* Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Modules</CardTitle>
                <Database className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{moduleStats?.total_modules || 0}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Loaded</CardTitle>
                <CheckCircle className="h-4 w-4 text-green-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{moduleStats?.loaded_modules || 0}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Failed</CardTitle>
                <AlertTriangle className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{moduleStats?.failed_modules || 0}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">System Health</CardTitle>
                {getStatusIcon(moduleStats?.system_health || "unknown")}
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold capitalize">{moduleStats?.system_health || "Unknown"}</div>
              </CardContent>
            </Card>
          </div>

          {/* Modules List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium">Module Overview</h3>
              <div className="flex space-x-2">
                <Button onClick={refreshModules} variant="outline" size="sm">
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh
                </Button>
              </div>
            </div>

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
          </div>
        </TabsContent>

      </Tabs>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <SettingsPageContent />
    </ProtectedRoute>
  );
}