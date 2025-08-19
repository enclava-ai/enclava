"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Shield, 
  Search, 
  Download, 
  Filter,
  RefreshCw,
  Calendar,
  User,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface AuditLog {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  user_id: string;
  username: string;
  ip_address: string;
  user_agent: string;
  success: boolean;
  error_message: string | null;
  metadata: Record<string, any>;
  created_at: string;
}

interface AuditStats {
  total_logs: number;
  success_rate: number;
  failed_actions: number;
  unique_users: number;
  top_actions: {
    action: string;
    count: number;
  }[];
  recent_failures: number;
}

interface AuditFilters {
  action?: string;
  resource_type?: string;
  user_id?: string;
  success?: boolean;
  start_date?: string;
  end_date?: string;
  ip_address?: string;
  search?: string;
}

export default function AuditPage() {
  const { toast } = useToast();
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [filters, setFilters] = useState<AuditFilters>({});
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchAuditData();
  }, [currentPage, pageSize, filters]);

  const fetchAuditData = async () => {
    try {
      setLoading(true);

      // Build query parameters
      const params = new URLSearchParams({
        page: currentPage.toString(),
        size: pageSize.toString(),
        ...Object.fromEntries(
          Object.entries(filters).filter(([_, value]) => value !== undefined && value !== "")
        ),
      });

      const [logsResponse, statsResponse] = await Promise.all([
        fetch(`/api/v1/audit?${params}`),
        fetch("/api/v1/audit/stats")
      ]);

      if (logsResponse.ok) {
        const logsData = await logsResponse.json();
        setAuditLogs(logsData.logs || []);
        setTotalCount(logsData.total || 0);
        setTotalPages(Math.ceil((logsData.total || 0) / pageSize));
      }

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error("Failed to fetch audit data:", error);
      toast({
        title: "Error",
        description: "Failed to fetch audit logs",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setFilters(prev => ({
      ...prev,
      search: searchQuery || undefined
    }));
    setCurrentPage(1);
  };

  const handleFilterChange = (key: keyof AuditFilters, value: string | boolean | undefined) => {
    setFilters(prev => ({
      ...prev,
      [key]: value === "all" ? undefined : value
    }));
    setCurrentPage(1);
  };

  const clearFilters = () => {
    setFilters({});
    setSearchQuery("");
    setCurrentPage(1);
  };

  const handleExport = async () => {
    try {
      setExporting(true);

      const params = new URLSearchParams({
        format: "csv",
        ...Object.fromEntries(
          Object.entries(filters).filter(([_, value]) => value !== undefined && value !== "")
        ),
      });

      const response = await fetch(`/api/v1/audit/export?${params}`);

      if (!response.ok) {
        throw new Error("Failed to export audit logs");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast({
        title: "Export Successful",
        description: "Audit logs have been exported successfully",
      });
    } catch (error) {
      console.error("Failed to export audit logs:", error);
      toast({
        title: "Export Failed",
        description: error instanceof Error ? error.message : "Failed to export audit logs",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  const getActionIcon = (action: string) => {
    if (action.includes("login") || action.includes("auth")) {
      return <User className="h-4 w-4" />;
    }
    if (action.includes("create") || action.includes("add")) {
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    }
    if (action.includes("delete") || action.includes("remove")) {
      return <XCircle className="h-4 w-4 text-red-500" />;
    }
    return <Activity className="h-4 w-4" />;
  };

  const getStatusBadge = (success: boolean) => {
    return success ? (
      <Badge variant="default" className="bg-green-500">Success</Badge>
    ) : (
      <Badge variant="destructive">Failed</Badge>
    );
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading && currentPage === 1) {
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
          <h1 className="text-3xl font-bold">Audit Logs</h1>
          <p className="text-muted-foreground">
            Monitor system activities and security events
          </p>
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="mr-2 h-4 w-4" />
            Filters
          </Button>
          <Button
            variant="outline"
            onClick={fetchAuditData}
            disabled={loading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            onClick={handleExport}
            disabled={exporting}
          >
            <Download className="mr-2 h-4 w-4" />
            {exporting ? "Exporting..." : "Export"}
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Logs</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_logs?.toLocaleString() || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.unique_users || 0} unique users
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(stats?.success_rate || 0).toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">
              Overall success rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed Actions</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats?.failed_actions || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.recent_failures || 0} in last 24h
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Top Action</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {stats?.top_actions?.[0]?.action || "N/A"}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats?.top_actions?.[0]?.count || 0} occurrences
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Search className="mr-2 h-5 w-5" />
            Search & Filter
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Search Bar */}
            <div className="flex space-x-2">
              <Input
                placeholder="Search logs by action, user, IP address, or resource..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleSearch()}
                className="flex-1"
              />
              <Button onClick={handleSearch}>
                <Search className="h-4 w-4" />
              </Button>
            </div>

            {/* Advanced Filters */}
            {showFilters && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-4 border-t">
                <div className="space-y-2">
                  <Label>Action</Label>
                  <Select
                    value={filters.action || "all"}
                    onValueChange={(value) => handleFilterChange("action", value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All actions" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All actions</SelectItem>
                      <SelectItem value="login">Login</SelectItem>
                      <SelectItem value="logout">Logout</SelectItem>
                      <SelectItem value="create">Create</SelectItem>
                      <SelectItem value="update">Update</SelectItem>
                      <SelectItem value="delete">Delete</SelectItem>
                      <SelectItem value="api_call">API Call</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Resource Type</Label>
                  <Select
                    value={filters.resource_type || "all"}
                    onValueChange={(value) => handleFilterChange("resource_type", value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All resources" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All resources</SelectItem>
                      <SelectItem value="user">Users</SelectItem>
                      <SelectItem value="api_key">API Keys</SelectItem>
                      <SelectItem value="budget">Budgets</SelectItem>
                      <SelectItem value="module">Modules</SelectItem>
                      <SelectItem value="setting">Settings</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select
                    value={filters.success?.toString() || "all"}
                    onValueChange={(value) => handleFilterChange("success", value === "all" ? undefined : value === "true")}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="true">Success</SelectItem>
                      <SelectItem value="false">Failed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Date Range</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Input
                      type="date"
                      value={filters.start_date || ""}
                      onChange={(e) => handleFilterChange("start_date", e.target.value)}
                      placeholder="Start date"
                    />
                    <Input
                      type="date"
                      value={filters.end_date || ""}
                      onChange={(e) => handleFilterChange("end_date", e.target.value)}
                      placeholder="End date"
                    />
                  </div>
                </div>

                <div className="col-span-full flex justify-end space-x-2">
                  <Button variant="outline" onClick={clearFilters}>
                    Clear Filters
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Audit Logs Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Audit Events</CardTitle>
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <span>Showing {((currentPage - 1) * pageSize) + 1}-{Math.min(currentPage * pageSize, totalCount)} of {totalCount}</span>
              <Select value={pageSize.toString()} onValueChange={(value) => setPageSize(parseInt(value))}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
              <span>per page</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {auditLogs.length === 0 ? (
              <div className="text-center py-8">
                <Shield className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No audit logs found</h3>
                <p className="text-muted-foreground">
                  {Object.keys(filters).length > 0 || searchQuery
                    ? "Try adjusting your search criteria or filters"
                    : "No audit events have been recorded yet"
                  }
                </p>
              </div>
            ) : (
              auditLogs.map((log) => (
                <Card key={log.id} className="border-l-4 border-l-transparent data-[success=false]:border-l-red-500">
                  <CardContent className="py-4">
                    <div className="grid grid-cols-1 lg:grid-cols-6 gap-4">
                      <div className="lg:col-span-2">
                        <div className="flex items-center space-x-2 mb-2">
                          {getActionIcon(log.action)}
                          <span className="font-medium">{log.action}</span>
                          {getStatusBadge(log.success)}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {log.resource_type} • {log.resource_id}
                        </p>
                      </div>

                      <div>
                        <span className="text-sm font-medium">User</span>
                        <p className="text-sm text-muted-foreground">{log.username}</p>
                      </div>

                      <div>
                        <span className="text-sm font-medium">IP Address</span>
                        <p className="text-sm text-muted-foreground font-mono">{log.ip_address}</p>
                      </div>

                      <div>
                        <span className="text-sm font-medium">Timestamp</span>
                        <p className="text-sm text-muted-foreground">{formatDateTime(log.created_at)}</p>
                      </div>

                      <div className="flex justify-end">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            const details = {
                              ...log,
                              metadata: JSON.stringify(log.metadata, null, 2)
                            };
                            // Would open a detail modal in a real implementation
                            console.log("Audit log details:", details);
                          }}
                        >
                          <Eye className="mr-2 h-3 w-3" />
                          Details
                        </Button>
                      </div>
                    </div>

                    {!log.success && log.error_message && (
                      <Alert className="mt-3 border-red-200">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>
                          <strong>Error:</strong> {log.error_message}
                        </AlertDescription>
                      </Alert>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <Button
                variant="outline"
                onClick={() => setCurrentPage(page => Math.max(1, page - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                Previous
              </Button>
              
              <div className="flex items-center space-x-2">
                <span className="text-sm text-muted-foreground">
                  Page {currentPage} of {totalPages}
                </span>
              </div>

              <Button
                variant="outline"
                onClick={() => setCurrentPage(page => Math.min(totalPages, page + 1))}
                disabled={currentPage === totalPages}
              >
                Next
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}