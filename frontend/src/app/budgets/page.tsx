"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogFooter
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { 
  DollarSign, 
  Plus, 
  Edit, 
  Trash2,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Calendar,
  Clock
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api-client";

interface Budget {
  id: string;
  name: string;
  description: string;
  budget_type: "user" | "api_key" | "global";
  target_id: string;
  limit_amount: number;
  period: "daily" | "weekly" | "monthly";
  alert_threshold: number;
  hard_limit: boolean;
  is_active: boolean;
  current_usage: number;
  period_start: string;
  period_end: string;
  created_at: string;
  last_alert_sent: string | null;
  usage_history: {
    date: string;
    amount: number;
  }[];
}

interface BudgetStats {
  total_budgets: number;
  active_budgets: number;
  over_threshold: number;
  total_spending: number;
  monthly_spending: number;
  savings_percentage: number;
}

interface NewBudgetData {
  name: string;
  description: string;
  budget_type: "user" | "api_key" | "global";
  target_id: string;
  limit_amount: number;
  period: "daily" | "weekly" | "monthly";
  alert_threshold: number;
  hard_limit: boolean;
}

export default function BudgetsPage() {
  const { toast } = useToast();
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [stats, setStats] = useState<BudgetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingBudget, setEditingBudget] = useState<Budget | null>(null);

  const [newBudgetData, setNewBudgetData] = useState<NewBudgetData>({
    name: "",
    description: "",
    budget_type: "user",
    target_id: "",
    limit_amount: 100,
    period: "monthly",
    alert_threshold: 80,
    hard_limit: false,
  });

  useEffect(() => {
    fetchBudgetData();
  }, []);

  const fetchBudgetData = async () => {
    try {
      setLoading(true);

      const [budgetsData, statsData] = await Promise.allSettled([
        apiClient.get("/api-internal/v1/budgets"),
        apiClient.get("/api-internal/v1/budgets/stats")
      ]);

      if (budgetsData.status === 'fulfilled') {
        setBudgets(budgetsData.value.budgets || []);
      }

      if (statsData.status === 'fulfilled') {
        setStats(statsData.value);
      }
    } catch (error) {
      console.error("Failed to fetch budget data:", error);
      toast({
        title: "Error",
        description: "Failed to fetch budget data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBudget = async () => {
    try {
      setActionLoading("create");

      await apiClient.post("/api-internal/v1/budgets", newBudgetData);

      toast({
        title: "Budget Created",
        description: "Budget configuration has been created successfully",
      });

      setShowCreateDialog(false);
      setNewBudgetData({
        name: "",
        description: "",
        budget_type: "user",
        target_id: "",
        limit_amount: 100,
        period: "monthly",
        alert_threshold: 80,
        hard_limit: false,
      });

      await fetchBudgetData();
    } catch (error) {
      console.error("Failed to create budget:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create budget",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdateBudget = async (budgetId: string, updates: Partial<Budget>) => {
    try {
      setActionLoading(`update-${budgetId}`);

      await apiClient.put(`/api-internal/v1/budgets/${budgetId}`, updates);

      toast({
        title: "Budget Updated",
        description: "Budget configuration has been updated successfully",
      });

      setEditingBudget(null);
      await fetchBudgetData();
    } catch (error) {
      console.error("Failed to update budget:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to update budget",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleBudget = async (budgetId: string, active: boolean) => {
    await handleUpdateBudget(budgetId, { is_active: active });
  };

  const handleDeleteBudget = async (budgetId: string) => {
    if (!confirm("Are you sure you want to delete this budget? This action cannot be undone.")) {
      return;
    }

    try {
      setActionLoading(`delete-${budgetId}`);

      await apiClient.delete(`/api-internal/v1/budgets/${budgetId}`);

      toast({
        title: "Budget Deleted",
        description: "Budget configuration has been deleted successfully",
      });

      await fetchBudgetData();
    } catch (error) {
      console.error("Failed to delete budget:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete budget",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const calculateUsagePercentage = (current: number, limit: number) => {
    return Math.min((current / limit) * 100, 100);
  };

  const getUsageStatus = (current: number, limit: number, threshold: number) => {
    const percentage = calculateUsagePercentage(current, limit);
    if (percentage >= 100) return "exceeded";
    if (percentage >= threshold) return "warning";
    return "normal";
  };

  const getStatusBadge = (budget: Budget) => {
    if (!budget.is_active) {
      return <Badge variant="secondary">Disabled</Badge>;
    }

    const status = getUsageStatus(budget.current_usage, budget.limit_amount, budget.alert_threshold);
    switch (status) {
      case "exceeded":
        return <Badge variant="destructive">Exceeded</Badge>;
      case "warning":
        return <Badge className="bg-yellow-500">Warning</Badge>;
      default:
        return <Badge variant="default">Active</Badge>;
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatPeriod = (period: string) => {
    return period.charAt(0).toUpperCase() + period.slice(1);
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
          <h1 className="text-3xl font-bold">Budget Management</h1>
          <p className="text-muted-foreground">
            Monitor spending and manage budget configurations
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Budget
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New Budget</DialogTitle>
              <DialogDescription>
                Set up a new budget configuration with spending limits and alerts
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Budget Name</Label>
                  <Input
                    id="name"
                    value={newBudgetData.name}
                    onChange={(e) => setNewBudgetData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Budget Name"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="budget-type">Budget Type</Label>
                  <Select 
                    value={newBudgetData.budget_type} 
                    onValueChange={(value: "user" | "api_key" | "global") => 
                      setNewBudgetData(prev => ({ ...prev, budget_type: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">User Budget</SelectItem>
                      <SelectItem value="api_key">API Key Budget</SelectItem>
                      <SelectItem value="global">Global Budget</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={newBudgetData.description}
                  onChange={(e) => setNewBudgetData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Budget Description"
                  rows={3}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="target-id">Target ID</Label>
                  <Input
                    id="target-id"
                    value={newBudgetData.target_id}
                    onChange={(e) => setNewBudgetData(prev => ({ ...prev, target_id: e.target.value }))}
                    placeholder="User ID, API Key ID, or 'global'"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="period">Period</Label>
                  <Select 
                    value={newBudgetData.period} 
                    onValueChange={(value: "daily" | "weekly" | "monthly") => 
                      setNewBudgetData(prev => ({ ...prev, period: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select period" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="monthly">Monthly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="limit-amount">Budget Limit ($)</Label>
                  <Input
                    id="limit-amount"
                    type="number"
                    step="0.01"
                    value={newBudgetData.limit_amount}
                    onChange={(e) => setNewBudgetData(prev => ({ ...prev, limit_amount: parseFloat(e.target.value) }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="alert-threshold">Alert Threshold (%)</Label>
                  <Input
                    id="alert-threshold"
                    type="number"
                    min="0"
                    max="100"
                    value={newBudgetData.alert_threshold}
                    onChange={(e) => setNewBudgetData(prev => ({ ...prev, alert_threshold: parseInt(e.target.value) }))}
                  />
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="hard-limit"
                  checked={newBudgetData.hard_limit}
                  onCheckedChange={(checked) => setNewBudgetData(prev => ({ ...prev, hard_limit: checked }))}
                />
                <Label htmlFor="hard-limit">Enforce hard limit (stop spending when exceeded)</Label>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowCreateDialog(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateBudget}
                disabled={!newBudgetData.name || actionLoading === "create"}
              >
                {actionLoading === "create" ? "Creating..." : "Create Budget"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Budgets</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_budgets || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.active_budgets || 0} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Over Threshold</CardTitle>
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats?.over_threshold || 0}</div>
            <p className="text-xs text-muted-foreground">
              Budgets exceeding alert threshold
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Spending</CardTitle>
            <TrendingUp className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(stats?.total_spending || 0)}</div>
            <p className="text-xs text-muted-foreground">
              All time spending
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">This Month</CardTitle>
            <Calendar className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(stats?.monthly_spending || 0)}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.savings_percentage || 0}% vs last month
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Budgets List */}
      <div className="space-y-4">
        {budgets.length === 0 ? (
          <Card>
            <CardContent className="py-8">
              <div className="text-center">
                <DollarSign className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No budgets configured</h3>
                <p className="text-muted-foreground mb-4">
                  Create your first budget to start tracking spending
                </p>
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Budget
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          budgets.map((budget) => {
            const usagePercentage = calculateUsagePercentage(budget.current_usage, budget.limit_amount);
            const status = getUsageStatus(budget.current_usage, budget.limit_amount, budget.alert_threshold);
            
            return (
              <Card key={budget.id} className={status === "exceeded" ? "border-red-500" : status === "warning" ? "border-yellow-500" : ""}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center space-x-2">
                        <DollarSign className="h-5 w-5" />
                        <span>{budget.name}</span>
                        {getStatusBadge(budget)}
                      </CardTitle>
                      <CardDescription>{budget.description}</CardDescription>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={budget.is_active}
                        onCheckedChange={(checked) => handleToggleBudget(budget.id, checked)}
                        disabled={actionLoading === `update-${budget.id}`}
                      />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* Usage Progress */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Usage: {formatCurrency(budget.current_usage)} / {formatCurrency(budget.limit_amount)}</span>
                        <span>{usagePercentage.toFixed(1)}%</span>
                      </div>
                      <Progress 
                        value={usagePercentage} 
                        className={`h-2 ${status === "exceeded" ? "bg-red-100" : status === "warning" ? "bg-yellow-100" : ""}`}
                      />
                    </div>

                    {/* Budget Details */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="font-medium">Type:</span>
                        <p className="text-muted-foreground capitalize">{budget.budget_type}</p>
                      </div>
                      <div>
                        <span className="font-medium">Period:</span>
                        <p className="text-muted-foreground">{formatPeriod(budget.period)}</p>
                      </div>
                      <div>
                        <span className="font-medium">Alert at:</span>
                        <p className="text-muted-foreground">{budget.alert_threshold}%</p>
                      </div>
                      <div>
                        <span className="font-medium">Hard Limit:</span>
                        <p className="text-muted-foreground">{budget.hard_limit ? "Yes" : "No"}</p>
                      </div>
                    </div>

                    {/* Period Information */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="font-medium">Period Start:</span>
                        <p className="text-muted-foreground">{new Date(budget.period_start).toLocaleDateString()}</p>
                      </div>
                      <div>
                        <span className="font-medium">Period End:</span>
                        <p className="text-muted-foreground">{new Date(budget.period_end).toLocaleDateString()}</p>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center space-x-2 pt-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingBudget(budget)}
                      >
                        <Edit className="mr-2 h-3 w-3" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteBudget(budget.id)}
                        disabled={actionLoading === `delete-${budget.id}`}
                      >
                        <Trash2 className="mr-2 h-3 w-3" />
                        {actionLoading === `delete-${budget.id}` ? "Deleting..." : "Delete"}
                      </Button>
                    </div>

                    {/* Warning Messages */}
                    {status === "exceeded" && (
                      <Alert className="border-red-500">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>
                          This budget has exceeded its limit. {budget.hard_limit && "Spending has been blocked."}
                        </AlertDescription>
                      </Alert>
                    )}
                    
                    {status === "warning" && (
                      <Alert className="border-yellow-500">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>
                          This budget has exceeded {budget.alert_threshold}% of its limit.
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}