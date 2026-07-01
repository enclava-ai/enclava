"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  RefreshCw,
  Filter,
  Download,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  BarChart3,
  Search,
  Calendar,
  User,
  Key,
  DollarSign,
  Database,
  History,
  Clock,
  Activity,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";

// Type definitions based on backend schemas
interface AuditLogResponse {
  id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  changes: Record<string, { old: any; new: any }>;
  actor_type: string;
  actor_user_id: number | null;
  actor_description: string | null;
  reason: string | null;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  related_api_key_id: number | null;
  related_budget_id: number | null;
  related_user_id: number | null;
  created_at: string;
}

interface AuditTrailResponse {
  entries: AuditLogResponse[];
  total: number;
  entity_type: string | null;
  entity_id: string | null;
}

interface AuditLogSummary {
  total_entries: number;
  entries_by_entity_type: Record<string, number>;
  entries_by_action: Record<string, number>;
  entries_by_actor_type: Record<string, number>;
  period_start: string | null;
  period_end: string | null;
}

export default function AdminAuditPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([]);
  const [summary, setSummary] = useState<AuditLogSummary | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  // Filter states
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>("all");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [actorTypeFilter, setActorTypeFilter] = useState<string>("all");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [actorUserId, setActorUserId] = useState<string>("");

  // Entity-specific search states
  const [apiKeyId, setApiKeyId] = useState<string>("");
  const [budgetId, setBudgetId] = useState<string>("");
  const [userId, setUserId] = useState<string>("");
  const [pricingProvider, setPricingProvider] = useState<string>("");
  const [pricingModel, setPricingModel] = useState<string>("");
  const [entityAuditTrail, setEntityAuditTrail] = useState<AuditTrailResponse | null>(null);

  // Pagination
  const [offset, setOffset] = useState(0);
  const [limit] = useState(100);

  useEffect(() => {
    fetchAllLogs();
    fetchSummary();
  }, []);

  const fetchAllLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const logs = await apiClient.get<AuditLogResponse[]>(
        `/api-internal/v1/admin/billing-audit/recent?limit=100`
      );
      setAuditLogs(logs);
    } catch (err) {
      setError("Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const summaryData = await apiClient.get<AuditLogSummary>(
        `/api-internal/v1/admin/billing-audit/summary`
      );
      setSummary(summaryData);
    } catch (err) {
      setError("Failed to load summary");
    }
  };

  const fetchFilteredLogs = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (entityTypeFilter !== "all") params.append("entity_type", entityTypeFilter);
      if (actionFilter !== "all") params.append("action", actionFilter);
      if (actorTypeFilter !== "all") params.append("actor_type", actorTypeFilter);
      if (actorUserId) params.append("actor_user_id", actorUserId);
      if (startDate) params.append("start_date", new Date(startDate).toISOString());
      if (endDate) params.append("end_date", new Date(endDate).toISOString());
      params.append("limit", limit.toString());
      params.append("offset", offset.toString());

      const logs = await apiClient.get<AuditLogResponse[]>(
        `/api-internal/v1/admin/billing-audit/search?${params.toString()}`
      );
      setAuditLogs(logs);
    } catch (err) {
      setError("Failed to search audit logs");
    } finally {
      setLoading(false);
    }
  };

  const fetchApiKeyAudit = async () => {
    if (!apiKeyId) return;
    try {
      setLoading(true);
      setError(null);
      const trail = await apiClient.get<AuditTrailResponse>(
        `/api-internal/v1/admin/billing-audit/api-key/${apiKeyId}?limit=100`
      );
      setEntityAuditTrail(trail);
      setAuditLogs(trail.entries);
    } catch (err) {
      setError(`Failed to load audit trail for API key ${apiKeyId}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchBudgetAudit = async () => {
    if (!budgetId) return;
    try {
      setLoading(true);
      setError(null);
      const trail = await apiClient.get<AuditTrailResponse>(
        `/api-internal/v1/admin/billing-audit/budget/${budgetId}?limit=100`
      );
      setEntityAuditTrail(trail);
      setAuditLogs(trail.entries);
    } catch (err) {
      setError(`Failed to load audit trail for budget ${budgetId}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserAudit = async () => {
    if (!userId) return;
    try {
      setLoading(true);
      setError(null);
      const trail = await apiClient.get<AuditTrailResponse>(
        `/api-internal/v1/admin/billing-audit/user/${userId}?limit=100`
      );
      setEntityAuditTrail(trail);
      setAuditLogs(trail.entries);
    } catch (err) {
      setError(`Failed to load audit trail for user ${userId}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchPricingAudit = async () => {
    if (!pricingProvider || !pricingModel) return;
    try {
      setLoading(true);
      setError(null);
      const trail = await apiClient.get<AuditTrailResponse>(
        `/api-internal/v1/admin/billing-audit/pricing/${pricingProvider}/${encodeURIComponent(pricingModel)}?limit=100`
      );
      setEntityAuditTrail(trail);
      setAuditLogs(trail.entries);
    } catch (err) {
      setError(`Failed to load audit trail for pricing ${pricingProvider}/${pricingModel}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(auditLogs, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-logs-${new Date().toISOString()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const toggleRowExpansion = (id: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const getEntityTypeIcon = (type: string) => {
    switch (type) {
      case "api_key":
        return <Key className="h-4 w-4" />;
      case "budget":
        return <DollarSign className="h-4 w-4" />;
      case "pricing":
        return <BarChart3 className="h-4 w-4" />;
      case "usage_record":
        return <Database className="h-4 w-4" />;
      default:
        return <Database className="h-4 w-4" />;
    }
  };

  const getEntityTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      api_key: "bg-muted text-muted-foreground border-border",
      budget: "bg-muted text-muted-foreground border-border",
      pricing: "bg-muted text-muted-foreground border-border",
      usage_record: "bg-muted text-muted-foreground border-border",
    };
    return (
      <Badge variant="outline" className={colors[type] || ""}>
        {type}
      </Badge>
    );
  };

  const getActionBadge = (action: string) => {
    const colors: Record<string, string> = {
      create: "bg-success-soft text-success-soft-foreground border-success-border",
      update: "bg-info-soft text-info-soft-foreground border-info-border",
      delete: "bg-danger-soft text-danger-soft-foreground border-danger-border",
      soft_delete: "bg-danger-soft text-danger-soft-foreground border-danger-border",
      restore: "bg-success-soft text-success-soft-foreground border-success-border",
      regenerate: "bg-warning-soft text-warning-soft-foreground border-warning-border",
      activate: "bg-success-soft text-success-soft-foreground border-success-border",
      deactivate: "bg-muted text-muted-foreground border-border",
      exceeded: "bg-danger-soft text-danger-soft-foreground border-danger-border",
      warning_triggered: "bg-warning-soft text-warning-soft-foreground border-warning-border",
      sync_create: "bg-success-soft text-success-soft-foreground border-success-border",
      sync_update: "bg-info-soft text-info-soft-foreground border-info-border",
      manual_override: "bg-muted text-muted-foreground border-border",
    };
    return (
      <Badge variant="outline" className={colors[action] || ""}>
        {action}
      </Badge>
    );
  };

  const getActorTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      user: "bg-muted text-muted-foreground border-border",
      system: "bg-muted text-muted-foreground border-border",
      api_sync: "bg-muted text-muted-foreground border-border",
    };
    return (
      <Badge variant="outline" className={colors[type] || ""}>
        {type}
      </Badge>
    );
  };

  const formatDateTime = (dateStr: string) => {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(dateStr));
  };

  const renderChangesDiff = (changes: Record<string, { old: any; new: any }>) => {
    return (
      <div className="space-y-2 p-4 bg-muted rounded-lg font-mono text-sm">
        {Object.entries(changes).map(([field, { old, new: newVal }]) => (
          <div key={field} className="space-y-1">
            <div className="font-semibold text-foreground">{field}:</div>
            <div className="pl-4 space-y-1">
              {old !== null && (
                <div className="text-danger">
                  <span className="opacity-50">- </span>
                  {JSON.stringify(old)}
                </div>
              )}
              <div className="text-success">
                <span className="opacity-50">+ </span>
                {JSON.stringify(newVal)}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderChangesSummary = (changes: Record<string, { old: any; new: any }>) => {
    const fields = Object.keys(changes);
    if (fields.length === 0) return <span className="text-muted-foreground">No changes</span>;
    if (fields.length === 1) return <span className="font-medium">{fields[0]}</span>;
    return (
      <span className="text-muted-foreground">
        {fields.length} fields: {fields.slice(0, 3).join(", ")}
        {fields.length > 3 && "..."}
      </span>
    );
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("en-US").format(value);
  };

  if (loading && !auditLogs.length) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading audit logs...</span>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Billing Audit Logs</h1>
          <p className="text-muted-foreground mt-1">
            Comprehensive audit trail for all billing-related changes
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="icon" onClick={fetchAllLogs} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button variant="outline" onClick={handleExport} disabled={auditLogs.length === 0}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
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

      <Tabs defaultValue="all-logs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all-logs">All Logs</TabsTrigger>
          <TabsTrigger value="by-api-key">By API Key</TabsTrigger>
          <TabsTrigger value="by-budget">By Budget</TabsTrigger>
          <TabsTrigger value="by-user">By User</TabsTrigger>
          <TabsTrigger value="by-pricing">By Pricing</TabsTrigger>
          <TabsTrigger value="statistics">Statistics</TabsTrigger>
        </TabsList>

        {/* All Logs Tab */}
        <TabsContent value="all-logs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Advanced Filters</CardTitle>
              <CardDescription>Filter audit logs by entity type, action, actor, and date range</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Entity Type</Label>
                  <Select value={entityTypeFilter} onValueChange={setEntityTypeFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All entity types" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="api_key">API Key</SelectItem>
                      <SelectItem value="budget">Budget</SelectItem>
                      <SelectItem value="pricing">Pricing</SelectItem>
                      <SelectItem value="usage_record">Usage Record</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Action Type</Label>
                  <Select value={actionFilter} onValueChange={setActionFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All actions" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Actions</SelectItem>
                      <SelectItem value="create">Create</SelectItem>
                      <SelectItem value="update">Update</SelectItem>
                      <SelectItem value="delete">Delete</SelectItem>
                      <SelectItem value="soft_delete">Soft Delete</SelectItem>
                      <SelectItem value="restore">Restore</SelectItem>
                      <SelectItem value="regenerate">Regenerate</SelectItem>
                      <SelectItem value="exceeded">Budget Exceeded</SelectItem>
                      <SelectItem value="sync_update">Sync Update</SelectItem>
                      <SelectItem value="manual_override">Manual Override</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Actor Type</Label>
                  <Select value={actorTypeFilter} onValueChange={setActorTypeFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All actors" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Actors</SelectItem>
                      <SelectItem value="user">User</SelectItem>
                      <SelectItem value="system">System</SelectItem>
                      <SelectItem value="api_sync">API Sync</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Actor User ID</Label>
                  <Input
                    type="number"
                    placeholder="Filter by user ID"
                    value={actorUserId}
                    onChange={(e) => setActorUserId(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Start Date</Label>
                  <Input
                    type="datetime-local"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label>End Date</Label>
                  <Input
                    type="datetime-local"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex space-x-2">
                <Button onClick={fetchFilteredLogs} disabled={loading}>
                  <Filter className="h-4 w-4 mr-2" />
                  Apply Filters
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setEntityTypeFilter("all");
                    setActionFilter("all");
                    setActorTypeFilter("all");
                    setActorUserId("");
                    setStartDate("");
                    setEndDate("");
                    fetchAllLogs();
                  }}
                >
                  Clear Filters
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Audit Logs</CardTitle>
              <CardDescription>
                Showing {auditLogs.length} entries
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]"></TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Changes</TableHead>
                    <TableHead>Actor</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLogs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        No audit logs found
                      </TableCell>
                    </TableRow>
                  ) : (
                    auditLogs.map((log) => (
                      <Collapsible key={log.id} asChild>
                        <>
                          <TableRow>
                            <TableCell>
                              <CollapsibleTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => toggleRowExpansion(log.id)}
                                >
                                  {expandedRows.has(log.id) ? (
                                    <ChevronDown className="h-4 w-4" />
                                  ) : (
                                    <ChevronRight className="h-4 w-4" />
                                  )}
                                </Button>
                              </CollapsibleTrigger>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              <div className="flex items-center space-x-2">
                                <Clock className="h-3 w-3" />
                                <span>{formatDateTime(log.created_at)}</span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <div className="flex items-center space-x-2">
                                  {getEntityTypeIcon(log.entity_type)}
                                  {getEntityTypeBadge(log.entity_type)}
                                </div>
                                <div className="font-mono text-xs text-muted-foreground">
                                  ID: {log.entity_id}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>{getActionBadge(log.action)}</TableCell>
                            <TableCell className="text-sm">
                              {renderChangesSummary(log.changes)}
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                {getActorTypeBadge(log.actor_type)}
                                {log.actor_user_id && (
                                  <div className="flex items-center space-x-1 text-xs text-muted-foreground">
                                    <User className="h-3 w-3" />
                                    <span>User {log.actor_user_id}</span>
                                  </div>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                          <CollapsibleContent asChild>
                            <TableRow>
                              <TableCell colSpan={6} className="bg-muted/50">
                                <div className="space-y-4 p-4">
                                  <div>
                                    <h4 className="font-semibold mb-2">Changes Details</h4>
                                    {renderChangesDiff(log.changes)}
                                  </div>

                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                    {log.reason && (
                                      <div>
                                        <span className="font-semibold">Reason: </span>
                                        <span>{log.reason}</span>
                                      </div>
                                    )}
                                    {log.actor_description && (
                                      <div>
                                        <span className="font-semibold">Actor Description: </span>
                                        <span>{log.actor_description}</span>
                                      </div>
                                    )}
                                    {log.ip_address && (
                                      <div>
                                        <span className="font-semibold">IP Address: </span>
                                        <span className="font-mono">{log.ip_address}</span>
                                      </div>
                                    )}
                                    {log.request_id && (
                                      <div>
                                        <span className="font-semibold">Request ID: </span>
                                        <span className="font-mono text-xs">{log.request_id}</span>
                                      </div>
                                    )}
                                    {log.related_api_key_id && (
                                      <div>
                                        <span className="font-semibold">Related API Key: </span>
                                        <span>{log.related_api_key_id}</span>
                                      </div>
                                    )}
                                    {log.related_budget_id && (
                                      <div>
                                        <span className="font-semibold">Related Budget: </span>
                                        <span>{log.related_budget_id}</span>
                                      </div>
                                    )}
                                    {log.related_user_id && (
                                      <div>
                                        <span className="font-semibold">Related User: </span>
                                        <span>{log.related_user_id}</span>
                                      </div>
                                    )}
                                    {log.user_agent && (
                                      <div className="col-span-2">
                                        <span className="font-semibold">User Agent: </span>
                                        <span className="text-xs text-muted-foreground break-all">
                                          {log.user_agent}
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </TableCell>
                            </TableRow>
                          </CollapsibleContent>
                        </>
                      </Collapsible>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* By API Key Tab */}
        <TabsContent value="by-api-key" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>API Key Audit Trail</CardTitle>
              <CardDescription>View all audit entries related to a specific API key</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <div className="flex-1">
                  <Input
                    type="number"
                    placeholder="Enter API Key ID"
                    value={apiKeyId}
                    onChange={(e) => setApiKeyId(e.target.value)}
                  />
                </div>
                <Button onClick={fetchApiKeyAudit} disabled={!apiKeyId || loading}>
                  <Search className="h-4 w-4 mr-2" />
                  Search
                </Button>
              </div>

              {entityAuditTrail && (
                <div className="text-sm text-muted-foreground">
                  Found {entityAuditTrail.total} entries for API Key {entityAuditTrail.entity_id}
                </div>
              )}

              {auditLogs.length > 0 && (
                <div className="space-y-4">
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border"></div>
                    {auditLogs.map((log, index) => (
                      <div key={log.id} className="relative pl-10 pb-8">
                        <div className="absolute left-2.5 top-2 h-3 w-3 rounded-full bg-primary border-2 border-background"></div>
                        <Card>
                          <CardContent className="pt-4">
                            <div className="flex items-start justify-between">
                              <div className="space-y-2 flex-1">
                                <div className="flex items-center space-x-2">
                                  {getActionBadge(log.action)}
                                  <span className="text-sm text-muted-foreground">
                                    {formatDateTime(log.created_at)}
                                  </span>
                                </div>
                                <div className="text-sm">
                                  <span className="font-semibold">Changes: </span>
                                  {renderChangesSummary(log.changes)}
                                </div>
                                {log.reason && (
                                  <div className="text-sm">
                                    <span className="font-semibold">Reason: </span>
                                    {log.reason}
                                  </div>
                                )}
                                <div className="flex items-center space-x-2">
                                  {getActorTypeBadge(log.actor_type)}
                                  {log.actor_user_id && (
                                    <span className="text-xs text-muted-foreground">
                                      User {log.actor_user_id}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <Collapsible>
                              <CollapsibleTrigger asChild>
                                <Button variant="ghost" size="sm" className="mt-2">
                                  <ChevronRight className="h-4 w-4 mr-1" />
                                  View Details
                                </Button>
                              </CollapsibleTrigger>
                              <CollapsibleContent className="mt-4">
                                {renderChangesDiff(log.changes)}
                              </CollapsibleContent>
                            </Collapsible>
                          </CardContent>
                        </Card>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* By Budget Tab */}
        <TabsContent value="by-budget" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Budget Audit Trail</CardTitle>
              <CardDescription>View all audit entries related to a specific budget</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <div className="flex-1">
                  <Input
                    type="number"
                    placeholder="Enter Budget ID"
                    value={budgetId}
                    onChange={(e) => setBudgetId(e.target.value)}
                  />
                </div>
                <Button onClick={fetchBudgetAudit} disabled={!budgetId || loading}>
                  <Search className="h-4 w-4 mr-2" />
                  Search
                </Button>
              </div>

              {entityAuditTrail && (
                <div className="text-sm text-muted-foreground">
                  Found {entityAuditTrail.total} entries for Budget {entityAuditTrail.entity_id}
                </div>
              )}

              {auditLogs.length > 0 && (
                <div className="space-y-4">
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border"></div>
                    {auditLogs.map((log) => (
                      <div key={log.id} className="relative pl-10 pb-8">
                        <div className="absolute left-2.5 top-2 h-3 w-3 rounded-full bg-primary border-2 border-background"></div>
                        <Card>
                          <CardContent className="pt-4">
                            <div className="flex items-start justify-between">
                              <div className="space-y-2 flex-1">
                                <div className="flex items-center space-x-2">
                                  {getActionBadge(log.action)}
                                  <span className="text-sm text-muted-foreground">
                                    {formatDateTime(log.created_at)}
                                  </span>
                                </div>
                                <div className="text-sm">
                                  <span className="font-semibold">Changes: </span>
                                  {renderChangesSummary(log.changes)}
                                </div>
                                {log.reason && (
                                  <div className="text-sm">
                                    <span className="font-semibold">Reason: </span>
                                    {log.reason}
                                  </div>
                                )}
                                <div className="flex items-center space-x-2">
                                  {getActorTypeBadge(log.actor_type)}
                                  {log.actor_user_id && (
                                    <span className="text-xs text-muted-foreground">
                                      User {log.actor_user_id}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <Collapsible>
                              <CollapsibleTrigger asChild>
                                <Button variant="ghost" size="sm" className="mt-2">
                                  <ChevronRight className="h-4 w-4 mr-1" />
                                  View Details
                                </Button>
                              </CollapsibleTrigger>
                              <CollapsibleContent className="mt-4">
                                {renderChangesDiff(log.changes)}
                              </CollapsibleContent>
                            </Collapsible>
                          </CardContent>
                        </Card>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* By User Tab */}
        <TabsContent value="by-user" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>User Audit Trail</CardTitle>
              <CardDescription>
                View all audit entries where the user is the actor or owner
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <div className="flex-1">
                  <Input
                    type="number"
                    placeholder="Enter User ID"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                  />
                </div>
                <Button onClick={fetchUserAudit} disabled={!userId || loading}>
                  <Search className="h-4 w-4 mr-2" />
                  Search
                </Button>
              </div>

              {entityAuditTrail && (
                <div className="text-sm text-muted-foreground">
                  Found {entityAuditTrail.total} entries for User {userId}
                </div>
              )}

              {auditLogs.length > 0 && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Changes</TableHead>
                      <TableHead>Role</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditLogs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDateTime(log.created_at)}
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            {getEntityTypeBadge(log.entity_type)}
                            <div className="font-mono text-xs text-muted-foreground">
                              {log.entity_id}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>{getActionBadge(log.action)}</TableCell>
                        <TableCell className="text-sm">
                          {renderChangesSummary(log.changes)}
                        </TableCell>
                        <TableCell>
                          {log.actor_user_id?.toString() === userId ? (
                            <Badge variant="outline" className="bg-info-soft text-info-soft-foreground border-info-border">
                              Actor
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="bg-muted text-muted-foreground border-border">
                              Owner
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* By Pricing Tab */}
        <TabsContent value="by-pricing" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Pricing Audit Trail</CardTitle>
              <CardDescription>View pricing change history for a specific model</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Input
                    placeholder="e.g., privatemode"
                    value={pricingProvider}
                    onChange={(e) => setPricingProvider(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Model</Label>
                  <Input
                    placeholder="e.g., meta-llama/llama-3.1-70b-instruct"
                    value={pricingModel}
                    onChange={(e) => setPricingModel(e.target.value)}
                  />
                </div>
              </div>

              <Button
                onClick={fetchPricingAudit}
                disabled={!pricingProvider || !pricingModel || loading}
              >
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>

              {entityAuditTrail && (
                <div className="text-sm text-muted-foreground">
                  Found {entityAuditTrail.total} entries for {entityAuditTrail.entity_id}
                </div>
              )}

              {auditLogs.length > 0 && (
                <div className="space-y-4">
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border"></div>
                    {auditLogs.map((log) => (
                      <div key={log.id} className="relative pl-10 pb-8">
                        <div className="absolute left-2.5 top-2 h-3 w-3 rounded-full bg-primary border-2 border-background"></div>
                        <Card>
                          <CardContent className="pt-4">
                            <div className="space-y-2">
                              <div className="flex items-center space-x-2">
                                {getActionBadge(log.action)}
                                <span className="text-sm text-muted-foreground">
                                  {formatDateTime(log.created_at)}
                                </span>
                              </div>
                              {renderChangesDiff(log.changes)}
                              {log.reason && (
                                <div className="text-sm">
                                  <span className="font-semibold">Reason: </span>
                                  {log.reason}
                                </div>
                              )}
                              <div className="flex items-center space-x-2">
                                {getActorTypeBadge(log.actor_type)}
                                {log.actor_description && (
                                  <span className="text-xs text-muted-foreground">
                                    {log.actor_description}
                                  </span>
                                )}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Statistics Tab */}
        <TabsContent value="statistics" className="space-y-4">
          {summary ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <StatCard
                  title="Total Audit Entries"
                  value={formatNumber(summary.total_entries)}
                  icon={<Database className="h-4 w-4" />}
                />
                <StatCard
                  title="Entity Types"
                  value={Object.keys(summary.entries_by_entity_type).length.toString()}
                  icon={<BarChart3 className="h-4 w-4" />}
                />
                <StatCard
                  title="Action Types"
                  value={Object.keys(summary.entries_by_action).length.toString()}
                  icon={<Activity className="h-4 w-4" />}
                />
                <StatCard
                  title="Actor Types"
                  value={Object.keys(summary.entries_by_actor_type).length.toString()}
                  icon={<User className="h-4 w-4" />}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Entries by Entity Type</CardTitle>
                    <CardDescription>Distribution of audit entries by entity type</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {Object.entries(summary.entries_by_entity_type)
                        .sort(([, a], [, b]) => b - a)
                        .map(([type, count]) => (
                          <div key={type} className="space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2">
                                {getEntityTypeIcon(type)}
                                <span className="font-medium">{type}</span>
                              </div>
                              <span className="text-sm font-bold">{formatNumber(count)}</span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary"
                                style={{
                                  width: `${(count / summary.total_entries) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Entries by Action Type</CardTitle>
                    <CardDescription>Distribution of audit entries by action</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {Object.entries(summary.entries_by_action)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 10)
                        .map(([action, count]) => (
                          <div key={action} className="space-y-2">
                            <div className="flex items-center justify-between">
                              {getActionBadge(action)}
                              <span className="text-sm font-bold">{formatNumber(count)}</span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-info"
                                style={{
                                  width: `${(count / summary.total_entries) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Entries by Actor Type</CardTitle>
                    <CardDescription>Distribution of audit entries by actor</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {Object.entries(summary.entries_by_actor_type)
                        .sort(([, a], [, b]) => b - a)
                        .map(([actor, count]) => (
                          <div key={actor} className="space-y-2">
                            <div className="flex items-center justify-between">
                              {getActorTypeBadge(actor)}
                              <span className="text-sm font-bold">{formatNumber(count)}</span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary"
                                style={{
                                  width: `${(count / summary.total_entries) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {(summary.period_start || summary.period_end) && (
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                      <Calendar className="h-4 w-4" />
                      <span>
                        Period:{" "}
                        {summary.period_start
                          ? new Date(summary.period_start).toLocaleDateString()
                          : "All time"}{" "}
                        -{" "}
                        {summary.period_end
                          ? new Date(summary.period_end).toLocaleDateString()
                          : "Present"}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin" />
              <span className="ml-2">Loading statistics...</span>
            </div>
          )}
        </TabsContent>
      </Tabs>
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
