"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { toast } from "sonner";
import {
  UserPlus,
  Search,
  MoreHorizontal,
  Users,
  Shield,
  ShieldPlus,
  Edit,
  Trash2,
  Lock,
  Unlock,
  Key,
  DollarSign,
  FileText,
  Wrench,
  Settings,
  Plus,
  Copy,
  RefreshCw,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";

// User interfaces
interface User {
  id: number;
  email: string;
  username: string;
  full_name?: string;
  is_active: boolean;
  is_verified: boolean;
  account_locked: boolean;
  role?: {
    id: number;
    name: string;
    display_name: string;
    level: string;
  };
  role_id?: number;
  created_at: string;
  last_login?: string;
  failed_login_attempts: number;
  budget_limit?: number;
  budget_spent?: number;
}

interface Role {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  level: string;
  permissions: {
    granted: string[];
    denied: string[];
  };
  can_manage_users: boolean;
  can_manage_budgets: boolean;
  can_view_reports: boolean;
  can_manage_tools: boolean;
  inherits_from: string[];
  is_active: boolean;
  is_system_role: boolean;
  created_at: string;
  updated_at: string;
}

interface RoleStats {
  total_roles: number;
  active_roles: number;
  system_roles: number;
  roles_by_level: { [key: string]: number };
}

interface CreateUserForm {
  email: string;
  username: string;
  password: string;
  full_name: string;
  role_id: number | null;
  is_active: boolean;
  is_verified: boolean;
  budget_limit_cents?: number;
}

interface CreateRoleForm {
  name: string;
  display_name: string;
  description: string;
  level: string;
  can_manage_users: boolean;
  can_manage_budgets: boolean;
  can_view_reports: boolean;
  can_manage_tools: boolean;
  is_active: boolean;
}

// API Key interfaces
interface ApiKey {
  id: string;
  name: string;
  description: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  total_requests: number;
  total_tokens: number;
  total_cost_cents: number;
  created_at: string;
  budget_id?: number;
  budget_limit?: number;
  budget_type?: "total" | "monthly";
  is_unlimited: boolean;
  allowed_models: string[];
  allowed_agents: string[];
}

interface NewApiKeyData {
  name: string;
  description: string;
  scopes: string[];
  expires_at: string | null;
  is_unlimited: boolean;
  budget_limit_cents?: number;
  budget_type?: "total" | "monthly";
  allowed_models: string[];
  allowed_agents: string[];
}

const PERMISSION_OPTIONS = [
  { value: "chat.completions", label: "LLM Chat Completions" },
  { value: "embeddings.create", label: "LLM Embeddings" },
  { value: "models.list", label: "List Models" },
];

function getErrorMessage(error: any, defaultMessage: string = "An error occurred"): string {
  if (error.details?.details && Array.isArray(error.details.details)) {
    const validationErrors = error.details.details
      .map((err: any) => err.message)
      .join(", ");
    return validationErrors;
  } else if (error.details?.message) {
    return error.details.message;
  } else if (error.message) {
    return error.message;
  }
  return defaultMessage;
}

const roleLevels = [
  { value: "read_only", label: "Read Only", description: "Can only view own data" },
  { value: "user", label: "User", description: "Standard user with full access to own resources" },
  { value: "admin", label: "Administrator", description: "Can manage users and view reports" },
  { value: "super_admin", label: "Super Administrator", description: "Full system access" }
];

export default function UserManagement() {
  const [activeTab, setActiveTab] = useState("users");

  // User state
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    skip: 0,
    limit: 20,
    total: 0
  });
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Role stats
  const [roleStats, setRoleStats] = useState<RoleStats | null>(null);

  // User modals
  const [showCreateUserDialog, setShowCreateUserDialog] = useState(false);
  const [showEditUserDialog, setShowEditUserDialog] = useState(false);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [showBudgetDialog, setShowBudgetDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [passwordForm, setPasswordForm] = useState({
    new_password: "",
    confirm_password: "",
    force_change_on_login: true,
  });
  const [budgetForm, setBudgetForm] = useState({
    budget_limit_cents: 0,
  });

  // Role modals
  const [showCreateRoleDialog, setShowCreateRoleDialog] = useState(false);
  const [showEditRoleDialog, setShowEditRoleDialog] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [showCreateApiKeyDialog, setShowCreateApiKeyDialog] = useState(false);
  const [showEditApiKeyDialog, setShowEditApiKeyDialog] = useState<string | null>(null);
  const [showRegenerateDialog, setShowRegenerateDialog] = useState<string | null>(null);
  const [newKeyVisible, setNewKeyVisible] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [editKeyData, setEditKeyData] = useState<Partial<ApiKey>>({});
  const [availableModels, setAvailableModels] = useState<any[]>([]);
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);

  const [newApiKeyData, setNewApiKeyData] = useState<NewApiKeyData>({
    name: "",
    description: "",
    scopes: [],
    expires_at: null,
    is_unlimited: false,
    budget_limit_cents: 1000,
    budget_type: "monthly",
    allowed_models: [],
    allowed_agents: [],
  });

  // Forms
  const [createUserForm, setCreateUserForm] = useState<CreateUserForm>({
    email: "",
    username: "",
    password: "",
    full_name: "",
    role_id: null,
    is_active: true,
    is_verified: false,
    budget_limit_cents: undefined
  });

  const [createRoleForm, setCreateRoleForm] = useState<CreateRoleForm>({
    name: "",
    display_name: "",
    description: "",
    level: "user",
    can_manage_users: false,
    can_manage_budgets: false,
    can_view_reports: false,
    can_manage_tools: false,
    is_active: true
  });

  const [editRoleForm, setEditRoleForm] = useState<CreateRoleForm>({
    name: "",
    display_name: "",
    description: "",
    level: "user",
    can_manage_users: false,
    can_manage_budgets: false,
    can_view_reports: false,
    can_manage_tools: false,
    is_active: true
  });

  useEffect(() => {
    fetchData();
  }, [pagination.skip, pagination.limit, searchTerm, roleFilter, statusFilter]);

  useEffect(() => {
    if (activeTab === "apikeys") {
      fetchApiKeys();
      fetchAvailableModels();
      fetchAvailableAgents();
    }
  }, [activeTab]);

  const fetchData = async () => {
    try {
      setLoading(true);

      const params = new URLSearchParams({
        skip: pagination.skip.toString(),
        limit: pagination.limit.toString(),
        ...(searchTerm && { search: searchTerm }),
        ...(roleFilter && roleFilter !== "all" && { role_id: roleFilter }),
        ...(statusFilter && statusFilter !== "all" && { is_active: statusFilter })
      });

      const usersResponse = await apiClient.get(`/api-internal/v1/user-management/users?${params}`);
      setUsers(usersResponse.users || []);
      setPagination(prev => ({ ...prev, total: usersResponse.total || 0 }));

      const rolesResponse = await apiClient.get("/api-internal/v1/user-management/roles");
      setRoles(Array.isArray(rolesResponse) ? rolesResponse : (rolesResponse.roles || []));

      try {
        const statsResponse = await apiClient.get("/api-internal/v1/user-management/statistics");
        setRoleStats(statsResponse.roles || null);
      } catch {
        // Stats endpoint may not be available
      }

    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to fetch data"));
    } finally {
      setLoading(false);
    }
  };

  // API Keys functions
  const fetchApiKeys = async () => {
    try {
      setApiKeysLoading(true);
      const result = await apiClient.get("/api-internal/v1/api-keys/") as any;
      setApiKeys(result.api_keys || result.data || []);
    } catch (error) {
      toast.error("Failed to fetch API keys");
    } finally {
      setApiKeysLoading(false);
    }
  };

  const fetchAvailableModels = async () => {
    try {
      const result = await apiClient.get("/api-internal/v1/llm/models") as any;
      setAvailableModels(result.data || []);
    } catch {
      setAvailableModels([]);
    }
  };

  const fetchAvailableAgents = async () => {
    try {
      const result = await apiClient.get("/api-internal/v1/tool-calling/agent/configs") as any;
      setAvailableAgents(result.configs || []);
    } catch {
      setAvailableAgents([]);
    }
  };

  const handleCreateApiKey = async () => {
    try {
      setActionLoading("create");
      const data = await apiClient.post("/api-internal/v1/api-keys/", newApiKeyData) as any;

      toast.success("API key created successfully");
      setNewKeyVisible(data.secret_key);
      setShowCreateApiKeyDialog(false);
      setNewApiKeyData({
        name: "",
        description: "",
        scopes: [],
        expires_at: null,
        is_unlimited: false,
        budget_limit_cents: 1000,
        budget_type: "monthly",
        allowed_models: [],
        allowed_agents: [],
      });
      await fetchApiKeys();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to create API key"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleApiKey = async (keyId: string, active: boolean) => {
    try {
      setActionLoading(`toggle-${keyId}`);
      await apiClient.put(`/api-internal/v1/api-keys/${keyId}`, { is_active: active });
      toast.success(`API key ${active ? "enabled" : "disabled"}`);
      await fetchApiKeys();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to update API key"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleRegenerateApiKey = async (keyId: string) => {
    try {
      setActionLoading(`regenerate-${keyId}`);
      const data = await apiClient.post(`/api-internal/v1/api-keys/${keyId}/regenerate`) as any;
      toast.success("API key regenerated");
      setNewKeyVisible(data.secret_key);
      setShowRegenerateDialog(null);
      await fetchApiKeys();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to regenerate API key"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteApiKey = async (keyId: string) => {
    if (!confirm("Are you sure you want to delete this API key?")) return;

    try {
      setActionLoading(`delete-${keyId}`);
      await apiClient.delete(`/api-internal/v1/api-keys/${keyId}`);
      toast.success("API key deleted");
      await fetchApiKeys();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to delete API key"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleEditApiKey = async (keyId: string) => {
    try {
      setActionLoading(`edit-${keyId}`);
      await apiClient.put(`/api-internal/v1/api-keys/${keyId}`, {
        name: editKeyData.name,
        description: editKeyData.description,
        is_unlimited: editKeyData.is_unlimited,
        budget_limit_cents: editKeyData.is_unlimited ? null : editKeyData.budget_limit,
        budget_type: editKeyData.is_unlimited ? null : editKeyData.budget_type,
        expires_at: editKeyData.expires_at,
      });
      toast.success("API key updated");
      setShowEditApiKeyDialog(null);
      setEditKeyData({});
      await fetchApiKeys();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to update API key"));
    } finally {
      setActionLoading(null);
    }
  };

  const openEditApiKeyDialog = (apiKey: ApiKey) => {
    setEditKeyData({
      name: apiKey.name,
      description: apiKey.description,
      is_unlimited: apiKey.is_unlimited,
      budget_limit: apiKey.budget_limit,
      budget_type: apiKey.budget_type || "monthly",
      expires_at: apiKey.expires_at,
    });
    setShowEditApiKeyDialog(apiKey.id);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  // User operations
  const createUser = async () => {
    try {
      await apiClient.post("/api-internal/v1/user-management/users", createUserForm);
      toast.success("User created successfully");
      setShowCreateUserDialog(false);
      setCreateUserForm({
        email: "",
        username: "",
        password: "",
        full_name: "",
        role_id: null,
        is_active: true,
        is_verified: false,
        budget_limit_cents: undefined
      });
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to create user"));
    }
  };

  const updateUser = async (userId: number, updates: Partial<User>) => {
    try {
      await apiClient.put(`/api-internal/v1/user-management/users/${userId}`, updates);
      toast.success("User updated successfully");
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to update user"));
    }
  };

  const deleteUser = async (userId: number) => {
    if (!confirm("Are you sure you want to delete this user?")) return;

    try {
      await apiClient.delete(`/api-internal/v1/user-management/users/${userId}`);
      toast.success("User deleted successfully");
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to delete user"));
    }
  };

  const lockUser = async (userId: number) => {
    try {
      await apiClient.post(`/api-internal/v1/user-management/users/${userId}/lock`);
      toast.success("User account locked");
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to lock user"));
    }
  };

  const unlockUser = async (userId: number) => {
    try {
      await apiClient.post(`/api-internal/v1/user-management/users/${userId}/unlock`);
      toast.success("User account unlocked");
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to unlock user"));
    }
  };

  const resetPassword = async () => {
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error("Passwords do not match");
      return;
    }

    if (passwordForm.new_password.length < 8) {
      toast.error("Password must be at least 8 characters long");
      return;
    }

    if (!selectedUser) return;

    try {
      await apiClient.post(`/api-internal/v1/user-management/users/${selectedUser.id}/password-reset`, {
        new_password: passwordForm.new_password,
        force_change_on_login: passwordForm.force_change_on_login,
      });
      toast.success("Password reset successfully");
      setShowPasswordDialog(false);
      setPasswordForm({
        new_password: "",
        confirm_password: "",
        force_change_on_login: true,
      });
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to reset password"));
    }
  };

  const updateUserBudget = async () => {
    if (!selectedUser) return;

    try {
      await apiClient.put(`/api-internal/v1/user-management/users/${selectedUser.id}`, {
        budget_limit_cents: budgetForm.budget_limit_cents,
      });
      toast.success("User budget updated");
      setShowBudgetDialog(false);
      setBudgetForm({ budget_limit_cents: 0 });
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to update budget"));
    }
  };

  // Role operations
  const createRole = async () => {
    try {
      const roleData = {
        ...createRoleForm,
        permissions: { granted: [], denied: [] },
        inherits_from: []
      };

      await apiClient.post("/api-internal/v1/user-management/roles", roleData);
      toast.success("Role created successfully");
      setShowCreateRoleDialog(false);
      setCreateRoleForm({
        name: "",
        display_name: "",
        description: "",
        level: "user",
        can_manage_users: false,
        can_manage_budgets: false,
        can_view_reports: false,
        can_manage_tools: false,
        is_active: true
      });
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to create role"));
    }
  };

  const updateRole = async () => {
    if (!selectedRole) return;

    try {
      const roleData = {
        ...editRoleForm,
        permissions: selectedRole.permissions || { granted: [], denied: [] },
        inherits_from: selectedRole.inherits_from || []
      };

      await apiClient.put(`/api-internal/v1/user-management/roles/${selectedRole.id}`, roleData);
      toast.success("Role updated successfully");
      setShowEditRoleDialog(false);
      setSelectedRole(null);
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to update role"));
    }
  };

  const deleteRole = async (roleId: number) => {
    if (!confirm("Are you sure you want to delete this role?")) return;

    try {
      await apiClient.delete(`/api-internal/v1/user-management/roles/${roleId}`);
      toast.success("Role deleted successfully");
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to delete role"));
    }
  };

  // Badge helpers
  const getStatusBadge = (user: User) => {
    if (user.account_locked) {
      return <Badge variant="destructive">Locked</Badge>;
    }
    if (!user.is_active) {
      return <Badge variant="secondary">Inactive</Badge>;
    }
    if (!user.is_verified) {
      return <Badge variant="outline">Unverified</Badge>;
    }
    return <Badge variant="default">Active</Badge>;
  };

  const getRoleBadge = (role?: User['role']) => {
    if (!role) return <Badge variant="outline">No Role</Badge>;

    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      super_admin: "destructive",
      admin: "default",
      user: "secondary",
      read_only: "outline"
    };

    return <Badge variant={variants[role.name] || "outline"}>{role.display_name}</Badge>;
  };

  const getLevelBadge = (level: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      super_admin: "destructive",
      admin: "default",
      user: "secondary",
      read_only: "outline"
    };

    return <Badge variant={variants[level] || "outline"}>{level.replace("_", " ").toUpperCase()}</Badge>;
  };

  const getPermissionIcons = (role: Role) => {
    const icons = [];
    if (role.can_manage_users) icons.push(<Users key="users" className="h-4 w-4" title="Manage Users" />);
    if (role.can_manage_budgets) icons.push(<DollarSign key="budgets" className="h-4 w-4" title="Manage Budgets" />);
    if (role.can_view_reports) icons.push(<FileText key="reports" className="h-4 w-4" title="View Reports" />);
    if (role.can_manage_tools) icons.push(<Wrench key="tools" className="h-4 w-4" title="Manage Tools" />);

    return icons.length > 0 ? icons : [<span key="none" className="text-xs text-muted-foreground">None</span>];
  };

  const getApiKeyStatusBadge = (apiKey: ApiKey) => {
    if (!apiKey.is_active) {
      return <Badge variant="secondary">Disabled</Badge>;
    }
    if (apiKey.expires_at && new Date(apiKey.expires_at) < new Date()) {
      return <Badge variant="destructive">Expired</Badge>;
    }
    return <Badge variant="default">Active</Badge>;
  };

  const formatLastUsed = (lastUsed: string | null) => {
    if (!lastUsed) return "Never";
    return new Date(lastUsed).toLocaleString();
  };

  const nextPage = () => {
    setPagination(prev => ({
      ...prev,
      skip: prev.skip + prev.limit
    }));
  };

  const prevPage = () => {
    setPagination(prev => ({
      ...prev,
      skip: Math.max(0, prev.skip - prev.limit)
    }));
  };

  if (loading && users.length === 0) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">User Management</h1>
          <p className="text-muted-foreground">
            Manage users, roles, and API keys
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="users" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Users
          </TabsTrigger>
          <TabsTrigger value="roles" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Roles
          </TabsTrigger>
          <TabsTrigger value="apikeys" className="flex items-center gap-2">
            <Key className="h-4 w-4" />
            API Keys
          </TabsTrigger>
        </TabsList>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-6">
          {/* Create User Button */}
          <div className="flex justify-end">
            <Dialog open={showCreateUserDialog} onOpenChange={setShowCreateUserDialog}>
              <DialogTrigger asChild>
                <Button>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Create User
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>Create New User</DialogTitle>
                  <DialogDescription>
                    Add a new user to the platform
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={createUserForm.email}
                      onChange={(e) => setCreateUserForm({ ...createUserForm, email: e.target.value })}
                      placeholder="user@example.com"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      value={createUserForm.username}
                      onChange={(e) => setCreateUserForm({ ...createUserForm, username: e.target.value })}
                      placeholder="username"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      value={createUserForm.password}
                      onChange={(e) => setCreateUserForm({ ...createUserForm, password: e.target.value })}
                      placeholder="********"
                    />
                    <p className="text-sm text-muted-foreground">
                      Must be at least 8 characters long
                    </p>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="full_name">Full Name</Label>
                    <Input
                      id="full_name"
                      value={createUserForm.full_name}
                      onChange={(e) => setCreateUserForm({ ...createUserForm, full_name: e.target.value })}
                      placeholder="John Doe"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="role">Role</Label>
                    <Select
                      value={createUserForm.role_id?.toString() || "none"}
                      onValueChange={(value) => setCreateUserForm({ ...createUserForm, role_id: value !== "none" ? parseInt(value) : null })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select role" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No Role</SelectItem>
                        {roles.map((role) => (
                          <SelectItem key={role.id} value={role.id.toString()}>
                            {role.display_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="budget">Budget Limit ($)</Label>
                    <Input
                      id="budget"
                      type="number"
                      step="0.01"
                      min="0"
                      value={(createUserForm.budget_limit_cents || 0) / 100}
                      onChange={(e) => setCreateUserForm({
                        ...createUserForm,
                        budget_limit_cents: Math.round(parseFloat(e.target.value || "0") * 100)
                      })}
                      placeholder="0.00 (unlimited)"
                    />
                    <p className="text-sm text-muted-foreground">
                      Leave at 0 for unlimited budget
                    </p>
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCreateUserDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={createUser}>Create User</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* User Filters */}
          <Card>
            <CardContent className="p-6">
              <div className="flex gap-4 items-center">
                <div className="flex-1 relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search users..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-8"
                  />
                </div>
                <Select value={roleFilter} onValueChange={setRoleFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="All Roles" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Roles</SelectItem>
                    {roles.map((role) => (
                      <SelectItem key={role.id} value={role.id.toString()}>
                        {role.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="All Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="true">Active</SelectItem>
                    <SelectItem value="false">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Users Table */}
          <Card>
            <CardContent className="p-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Budget</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{user.full_name || user.username}</p>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        {getRoleBadge(user.role)}
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(user)}
                      </TableCell>
                      <TableCell>
                        {user.budget_limit ? (
                          <div>
                            <p className="text-sm">${(user.budget_limit / 100).toFixed(2)}</p>
                            {user.budget_spent !== undefined && (
                              <p className="text-xs text-muted-foreground">
                                Used: ${(user.budget_spent / 100).toFixed(2)}
                              </p>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm text-muted-foreground">Unlimited</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {new Date(user.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem onClick={() => {
                              setSelectedUser({ ...user, role_id: user.role?.id });
                              setShowEditUserDialog(true);
                            }}>
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => {
                              setSelectedUser(user);
                              setBudgetForm({ budget_limit_cents: user.budget_limit || 0 });
                              setShowBudgetDialog(true);
                            }}>
                              <DollarSign className="mr-2 h-4 w-4" />
                              Set Budget
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => {
                              setSelectedUser(user);
                              setPasswordForm({
                                new_password: "",
                                confirm_password: "",
                                force_change_on_login: true,
                              });
                              setShowPasswordDialog(true);
                            }}>
                              <Key className="mr-2 h-4 w-4" />
                              Reset Password
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {user.account_locked ? (
                              <DropdownMenuItem onClick={() => unlockUser(user.id)}>
                                <Unlock className="mr-2 h-4 w-4" />
                                Unlock Account
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => lockUser(user.id)}>
                                <Lock className="mr-2 h-4 w-4" />
                                Lock Account
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => deleteUser(user.id)}
                              className="text-danger"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  Showing {pagination.skip + 1} to {Math.min(pagination.skip + pagination.limit, pagination.total)} of {pagination.total} users
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.skip === 0}
                    onClick={prevPage}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.skip + pagination.limit >= pagination.total}
                    onClick={nextPage}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Roles Tab */}
        <TabsContent value="roles" className="space-y-6">
          {/* Create Role Button */}
          <div className="flex justify-end">
            <Dialog open={showCreateRoleDialog} onOpenChange={setShowCreateRoleDialog}>
              <DialogTrigger asChild>
                <Button>
                  <ShieldPlus className="mr-2 h-4 w-4" />
                  Create Role
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>Create New Role</DialogTitle>
                  <DialogDescription>
                    Define a new role with specific permissions
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="role-name">Role Name</Label>
                    <Input
                      id="role-name"
                      value={createRoleForm.name}
                      onChange={(e) => setCreateRoleForm({ ...createRoleForm, name: e.target.value })}
                      placeholder="developer_role"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="role-display-name">Display Name</Label>
                    <Input
                      id="role-display-name"
                      value={createRoleForm.display_name}
                      onChange={(e) => setCreateRoleForm({ ...createRoleForm, display_name: e.target.value })}
                      placeholder="Developer"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="role-description">Description</Label>
                    <Textarea
                      id="role-description"
                      value={createRoleForm.description}
                      onChange={(e) => setCreateRoleForm({ ...createRoleForm, description: e.target.value })}
                      placeholder="Role description..."
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="role-level">Level</Label>
                    <Select
                      value={createRoleForm.level}
                      onValueChange={(value) => setCreateRoleForm({ ...createRoleForm, level: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select level" />
                      </SelectTrigger>
                      <SelectContent>
                        {roleLevels.map((level) => (
                          <SelectItem key={level.value} value={level.value}>
                            {level.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-3">
                    <Label>Permissions</Label>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="create-manage-users"
                          checked={createRoleForm.can_manage_users}
                          onCheckedChange={(checked) =>
                            setCreateRoleForm({ ...createRoleForm, can_manage_users: checked as boolean })
                          }
                        />
                        <Label htmlFor="create-manage-users" className="text-sm">Can manage users</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="create-manage-budgets"
                          checked={createRoleForm.can_manage_budgets}
                          onCheckedChange={(checked) =>
                            setCreateRoleForm({ ...createRoleForm, can_manage_budgets: checked as boolean })
                          }
                        />
                        <Label htmlFor="create-manage-budgets" className="text-sm">Can manage budgets</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="create-view-reports"
                          checked={createRoleForm.can_view_reports}
                          onCheckedChange={(checked) =>
                            setCreateRoleForm({ ...createRoleForm, can_view_reports: checked as boolean })
                          }
                        />
                        <Label htmlFor="create-view-reports" className="text-sm">Can view reports</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="create-manage-tools"
                          checked={createRoleForm.can_manage_tools}
                          onCheckedChange={(checked) =>
                            setCreateRoleForm({ ...createRoleForm, can_manage_tools: checked as boolean })
                          }
                        />
                        <Label htmlFor="create-manage-tools" className="text-sm">Can manage tools</Label>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCreateRoleDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={createRole}>Create Role</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* Statistics Cards */}
          {roleStats && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Total Roles</CardTitle>
                  <Shield className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{roleStats.total_roles}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Active Roles</CardTitle>
                  <Settings className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{roleStats.active_roles}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">System Roles</CardTitle>
                  <Shield className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{roleStats.system_roles}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Custom Roles</CardTitle>
                  <ShieldPlus className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{roleStats.total_roles - roleStats.system_roles}</div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Roles Table */}
          <Card>
            <CardContent className="p-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Role</TableHead>
                    <TableHead>Level</TableHead>
                    <TableHead>Permissions</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {roles.map((role) => (
                    <TableRow key={role.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{role.display_name}</p>
                          <p className="text-sm text-muted-foreground">{role.name}</p>
                          {role.description && (
                            <p className="text-xs text-muted-foreground mt-1">{role.description}</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {getLevelBadge(role.level)}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {getPermissionIcons(role)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {role.is_active ? (
                            <Badge variant="default">Active</Badge>
                          ) : (
                            <Badge variant="secondary">Inactive</Badge>
                          )}
                          {role.is_system_role && (
                            <Badge variant="outline">System</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {new Date(role.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            {!role.is_system_role && (
                              <>
                                <DropdownMenuItem onClick={() => {
                                  setSelectedRole(role);
                                  setEditRoleForm({
                                    name: role.name,
                                    display_name: role.display_name,
                                    description: role.description || "",
                                    level: role.level,
                                    can_manage_users: role.can_manage_users,
                                    can_manage_budgets: role.can_manage_budgets,
                                    can_view_reports: role.can_view_reports,
                                    can_manage_tools: role.can_manage_tools,
                                    is_active: role.is_active
                                  });
                                  setShowEditRoleDialog(true);
                                }}>
                                  <Edit className="mr-2 h-4 w-4" />
                                  Edit
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => deleteRole(role.id)}
                                  className="text-danger"
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Delete
                                </DropdownMenuItem>
                              </>
                            )}
                            {role.is_system_role && (
                              <DropdownMenuItem disabled>
                                System roles cannot be modified
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* API Keys Tab */}
        <TabsContent value="apikeys" className="space-y-6">
          {/* Create API Key Button */}
          <div className="flex justify-end">
            <Dialog open={showCreateApiKeyDialog} onOpenChange={setShowCreateApiKeyDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Create API Key
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Create New API Key</DialogTitle>
                  <DialogDescription>
                    Create a new API key with specific permissions and budget
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="api-name">Name</Label>
                      <Input
                        id="api-name"
                        value={newApiKeyData.name}
                        onChange={(e) => setNewApiKeyData(prev => ({ ...prev, name: e.target.value }))}
                        placeholder="API Key Name"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="api-expires">Expires At (Optional)</Label>
                      <Input
                        id="api-expires"
                        type="datetime-local"
                        value={newApiKeyData.expires_at || ""}
                        onChange={(e) => setNewApiKeyData(prev => ({ ...prev, expires_at: e.target.value || null }))}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="api-description">Description</Label>
                    <Textarea
                      id="api-description"
                      value={newApiKeyData.description}
                      onChange={(e) => setNewApiKeyData(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="API Key Description"
                      rows={2}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Permissions</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {PERMISSION_OPTIONS.map((permission) => (
                        <div key={permission.value} className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            id={permission.value}
                            checked={newApiKeyData.scopes.includes(permission.value)}
                            onChange={(e) => {
                              const checked = e.target.checked;
                              setNewApiKeyData(prev => ({
                                ...prev,
                                scopes: checked
                                  ? [...prev.scopes, permission.value]
                                  : prev.scopes.filter(p => p !== permission.value)
                              }));
                            }}
                            className="rounded"
                          />
                          <Label htmlFor={permission.value} className="text-sm">
                            {permission.label}
                          </Label>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Budget Configuration */}
                  <div className="space-y-4">
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="api-budget-enabled"
                        checked={newApiKeyData.is_unlimited}
                        onChange={(e) => setNewApiKeyData(prev => ({ ...prev, is_unlimited: e.target.checked }))}
                        className="rounded"
                      />
                      <Label htmlFor="api-budget-enabled">Set budget limit</Label>
                    </div>

                    {newApiKeyData.is_unlimited && (
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="api-budget-type">Budget Type</Label>
                          <Select
                            value={newApiKeyData.budget_type}
                            onValueChange={(value: "total" | "monthly") => setNewApiKeyData(prev => ({ ...prev, budget_type: value }))}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select budget type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="total">Total Budget</SelectItem>
                              <SelectItem value="monthly">Monthly Budget</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="api-budget-limit">Budget Limit ($)</Label>
                          <Input
                            id="api-budget-limit"
                            type="number"
                            step="0.01"
                            min="0"
                            value={(newApiKeyData.budget_limit_cents || 0) / 100}
                            onChange={(e) => setNewApiKeyData(prev => ({
                              ...prev,
                              budget_limit_cents: Math.round(parseFloat(e.target.value || "0") * 100)
                            }))}
                            placeholder="0.00"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowCreateApiKeyDialog(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateApiKey}
                    disabled={!newApiKeyData.name || actionLoading === "create"}
                  >
                    {actionLoading === "create" ? "Creating..." : "Create API Key"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* New Key Display */}
          {newKeyVisible && (
            <Alert className="mb-6">
              <Key className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-2">
                  <p className="font-medium">Your new API key has been created:</p>
                  <div className="flex items-center space-x-2 p-2 bg-muted rounded">
                    <code className="flex-1 text-sm">{newKeyVisible}</code>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(newKeyVisible)}
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Make sure to copy this key now. You won't be able to see it again.
                  </p>
                  <Button size="sm" onClick={() => setNewKeyVisible(null)}>
                    I've saved the key
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* API Keys List */}
          {apiKeysLoading ? (
            <div className="flex items-center justify-center min-h-[200px]">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : apiKeys.length === 0 ? (
            <Card>
              <CardContent className="py-8">
                <div className="text-center">
                  <Key className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">No API keys found</h3>
                  <p className="text-muted-foreground mb-4">
                    Create your first API key to start using the platform
                  </p>
                  <Button onClick={() => setShowCreateApiKeyDialog(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create API Key
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {apiKeys.map((apiKey) => (
                <Card key={apiKey.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center space-x-2">
                          <Key className="h-5 w-5" />
                          <span>{apiKey.name}</span>
                          {getApiKeyStatusBadge(apiKey)}
                        </CardTitle>
                        <CardDescription>{apiKey.description}</CardDescription>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={apiKey.is_active}
                          onCheckedChange={(checked) => handleToggleApiKey(apiKey.id, checked)}
                          disabled={actionLoading === `toggle-${apiKey.id}`}
                        />
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
                      <div>
                        <span className="text-sm font-medium">Key Prefix:</span>
                        <p className="text-sm text-muted-foreground font-mono">{apiKey.key_prefix}...</p>
                      </div>
                      <div>
                        <span className="text-sm font-medium">Requests:</span>
                        <p className="text-sm text-muted-foreground">{apiKey.total_requests}</p>
                      </div>
                      <div>
                        <span className="text-sm font-medium">Tokens:</span>
                        <p className="text-sm text-muted-foreground">{apiKey.total_tokens}</p>
                      </div>
                      <div>
                        <span className="text-sm font-medium">Cost:</span>
                        <p className="text-sm text-muted-foreground">${(apiKey.total_cost_cents / 100).toFixed(2)}</p>
                      </div>
                      <div>
                        <span className="text-sm font-medium">Last Used:</span>
                        <p className="text-sm text-muted-foreground">{formatLastUsed(apiKey.last_used_at)}</p>
                      </div>
                    </div>

                    {/* Budget Information */}
                    <div className="space-y-2 mb-4">
                      <span className="text-sm font-medium">Budget:</span>
                      <div className="flex items-center gap-2">
                        {apiKey.is_unlimited ? (
                          <Badge variant="secondary">Unlimited</Badge>
                        ) : apiKey.budget_limit ? (
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">
                              {apiKey.budget_type === "monthly" ? "Monthly" : "Total"}: ${(apiKey.budget_limit / 100).toFixed(2)}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              (${((apiKey.budget_limit - apiKey.total_cost_cents) / 100).toFixed(2)} remaining)
                            </span>
                          </div>
                        ) : (
                          <Badge variant="outline">No budget set</Badge>
                        )}
                      </div>
                    </div>

                    <div className="space-y-2 mb-4">
                      <span className="text-sm font-medium">Scopes:</span>
                      <div className="flex flex-wrap gap-1">
                        {apiKey.scopes.map((scope) => (
                          <Badge key={scope} variant="outline" className="text-xs">
                            {scope}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openEditApiKeyDialog(apiKey)}
                        disabled={actionLoading === `edit-${apiKey.id}`}
                      >
                        <Edit className="mr-2 h-3 w-3" />
                        Edit
                      </Button>

                      <Dialog
                        open={showRegenerateDialog === apiKey.id}
                        onOpenChange={(open) => setShowRegenerateDialog(open ? apiKey.id : null)}
                      >
                        <DialogTrigger asChild>
                          <Button size="sm" variant="outline">
                            <RefreshCw className="mr-2 h-3 w-3" />
                            Regenerate
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Regenerate API Key</DialogTitle>
                            <DialogDescription>
                              This will generate a new API key and invalidate the current one.
                            </DialogDescription>
                          </DialogHeader>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setShowRegenerateDialog(null)}>
                              Cancel
                            </Button>
                            <Button
                              variant="destructive"
                              onClick={() => handleRegenerateApiKey(apiKey.id)}
                              disabled={actionLoading === `regenerate-${apiKey.id}`}
                            >
                              {actionLoading === `regenerate-${apiKey.id}` ? "Regenerating..." : "Regenerate"}
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteApiKey(apiKey.id)}
                        disabled={actionLoading === `delete-${apiKey.id}`}
                      >
                        <Trash2 className="mr-2 h-3 w-3" />
                        {actionLoading === `delete-${apiKey.id}` ? "Deleting..." : "Delete"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Edit User Dialog */}
      <Dialog open={showEditUserDialog} onOpenChange={setShowEditUserDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>
              Update user information
            </DialogDescription>
          </DialogHeader>
          {selectedUser && (
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-email">Email</Label>
                <Input
                  id="edit-email"
                  type="email"
                  defaultValue={selectedUser.email}
                  onChange={(e) => setSelectedUser({ ...selectedUser, email: e.target.value })}
                  placeholder="user@example.com"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-username">Username</Label>
                <Input
                  id="edit-username"
                  defaultValue={selectedUser.username}
                  onChange={(e) => setSelectedUser({ ...selectedUser, username: e.target.value })}
                  placeholder="username"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-full-name">Full Name</Label>
                <Input
                  id="edit-full-name"
                  defaultValue={selectedUser.full_name || ""}
                  onChange={(e) => setSelectedUser({ ...selectedUser, full_name: e.target.value })}
                  placeholder="John Doe"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-role">Role</Label>
                <Select
                  key={`role-select-${selectedUser.id}`}
                  value={selectedUser.role_id?.toString() || selectedUser.role?.id?.toString() || "none"}
                  onValueChange={(value) => {
                    if (value === "none") {
                      setSelectedUser({ ...selectedUser, role: undefined, role_id: 0 });
                    } else {
                      const role = roles.find(r => r.id.toString() === value);
                      if (role) {
                        setSelectedUser({ ...selectedUser, role: { id: role.id, name: role.name, display_name: role.display_name, level: role.level }, role_id: role.id });
                      }
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No Role</SelectItem>
                    {roles.map((role) => (
                      <SelectItem key={role.id} value={role.id.toString()}>
                        {role.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-is-active"
                  checked={selectedUser.is_active}
                  onChange={(e) => setSelectedUser({ ...selectedUser, is_active: e.target.checked })}
                  className="rounded border-border"
                />
                <Label htmlFor="edit-is-active">Active</Label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-is-verified"
                  checked={selectedUser.is_verified}
                  onChange={(e) => setSelectedUser({ ...selectedUser, is_verified: e.target.checked })}
                  className="rounded border-border"
                />
                <Label htmlFor="edit-is-verified">Verified</Label>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowEditUserDialog(false)}>
              Cancel
            </Button>
            <Button onClick={() => {
              if (selectedUser) {
                const updates: any = {
                  email: selectedUser.email,
                  username: selectedUser.username,
                  full_name: selectedUser.full_name,
                  is_active: selectedUser.is_active,
                  is_verified: selectedUser.is_verified,
                };

                if (selectedUser.role_id !== undefined) {
                  updates.role_id = selectedUser.role_id;
                } else if (selectedUser.role) {
                  updates.role_id = selectedUser.role.id;
                }

                updateUser(selectedUser.id, updates);
                setShowEditUserDialog(false);
              }
            }}>
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Budget Dialog */}
      <Dialog open={showBudgetDialog} onOpenChange={setShowBudgetDialog}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Set User Budget</DialogTitle>
            <DialogDescription>
              Set the budget limit for {selectedUser?.username}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="budget-limit">Budget Limit ($)</Label>
              <Input
                id="budget-limit"
                type="number"
                step="0.01"
                min="0"
                value={budgetForm.budget_limit_cents / 100}
                onChange={(e) => setBudgetForm({
                  budget_limit_cents: Math.round(parseFloat(e.target.value || "0") * 100)
                })}
                placeholder="0.00"
              />
              <p className="text-sm text-muted-foreground">
                Set to 0 for unlimited budget
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowBudgetDialog(false)}>
              Cancel
            </Button>
            <Button onClick={updateUserBudget}>
              Save Budget
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Role Dialog */}
      <Dialog open={showEditRoleDialog} onOpenChange={setShowEditRoleDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit Role</DialogTitle>
            <DialogDescription>
              Update role settings and permissions
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-role-name">Role Name</Label>
              <Input
                id="edit-role-name"
                value={editRoleForm.name}
                onChange={(e) => setEditRoleForm({ ...editRoleForm, name: e.target.value })}
                placeholder="developer_role"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-role-display-name">Display Name</Label>
              <Input
                id="edit-role-display-name"
                value={editRoleForm.display_name}
                onChange={(e) => setEditRoleForm({ ...editRoleForm, display_name: e.target.value })}
                placeholder="Developer"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-role-description">Description</Label>
              <Textarea
                id="edit-role-description"
                value={editRoleForm.description}
                onChange={(e) => setEditRoleForm({ ...editRoleForm, description: e.target.value })}
                placeholder="Role description..."
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-role-level">Level</Label>
              <Select
                value={editRoleForm.level}
                onValueChange={(value) => setEditRoleForm({ ...editRoleForm, level: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select level" />
                </SelectTrigger>
                <SelectContent>
                  {roleLevels.map((level) => (
                    <SelectItem key={level.value} value={level.value}>
                      {level.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-3">
              <Label>Permissions</Label>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="edit-manage-users"
                    checked={editRoleForm.can_manage_users}
                    onCheckedChange={(checked) =>
                      setEditRoleForm({ ...editRoleForm, can_manage_users: checked as boolean })
                    }
                  />
                  <Label htmlFor="edit-manage-users" className="text-sm">Can manage users</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="edit-manage-budgets"
                    checked={editRoleForm.can_manage_budgets}
                    onCheckedChange={(checked) =>
                      setEditRoleForm({ ...editRoleForm, can_manage_budgets: checked as boolean })
                    }
                  />
                  <Label htmlFor="edit-manage-budgets" className="text-sm">Can manage budgets</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="edit-view-reports"
                    checked={editRoleForm.can_view_reports}
                    onCheckedChange={(checked) =>
                      setEditRoleForm({ ...editRoleForm, can_view_reports: checked as boolean })
                    }
                  />
                  <Label htmlFor="edit-view-reports" className="text-sm">Can view reports</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="edit-manage-tools"
                    checked={editRoleForm.can_manage_tools}
                    onCheckedChange={(checked) =>
                      setEditRoleForm({ ...editRoleForm, can_manage_tools: checked as boolean })
                    }
                  />
                  <Label htmlFor="edit-manage-tools" className="text-sm">Can manage tools</Label>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit-role-active"
                checked={editRoleForm.is_active}
                onCheckedChange={(checked) =>
                  setEditRoleForm({ ...editRoleForm, is_active: checked as boolean })
                }
              />
              <Label htmlFor="edit-role-active" className="text-sm">Active</Label>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowEditRoleDialog(false)}>
              Cancel
            </Button>
            <Button onClick={updateRole}>Save Changes</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit API Key Dialog */}
      <Dialog open={!!showEditApiKeyDialog} onOpenChange={(open) => !open && setShowEditApiKeyDialog(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit API Key</DialogTitle>
            <DialogDescription>
              Update API key settings and budget
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-api-name">Name</Label>
                <Input
                  id="edit-api-name"
                  value={editKeyData.name || ""}
                  onChange={(e) => setEditKeyData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="API Key Name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-api-description">Description</Label>
                <Input
                  id="edit-api-description"
                  value={editKeyData.description || ""}
                  onChange={(e) => setEditKeyData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="API Key Description"
                />
              </div>
            </div>

            {/* Budget Configuration */}
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-api-budget-enabled"
                  checked={editKeyData.is_unlimited || false}
                  onChange={(e) => setEditKeyData(prev => ({ ...prev, is_unlimited: e.target.checked }))}
                  className="rounded"
                />
                <Label htmlFor="edit-api-budget-enabled">Set budget limit</Label>
              </div>

              {editKeyData.is_unlimited && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="edit-api-budget-type">Budget Type</Label>
                    <Select
                      value={editKeyData.budget_type}
                      onValueChange={(value: "total" | "monthly") => setEditKeyData(prev => ({ ...prev, budget_type: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select budget type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="total">Total Budget</SelectItem>
                        <SelectItem value="monthly">Monthly Budget</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="edit-api-budget-limit">Budget Limit ($)</Label>
                    <Input
                      id="edit-api-budget-limit"
                      type="number"
                      step="0.01"
                      min="0"
                      value={(editKeyData.budget_limit || 0) / 100}
                      onChange={(e) => setEditKeyData(prev => ({
                        ...prev,
                        budget_limit: Math.round(parseFloat(e.target.value || "0") * 100)
                      }))}
                      placeholder="0.00"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Expiration */}
            <div className="space-y-2">
              <Label htmlFor="edit-api-expires-at">Expiration Date (Optional)</Label>
              <Input
                id="edit-api-expires-at"
                type="date"
                value={editKeyData.expires_at?.split('T')[0] || ""}
                onChange={(e) => setEditKeyData(prev => ({ ...prev, expires_at: e.target.value ? `${e.target.value}T23:59:59Z` : null }))}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditApiKeyDialog(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => showEditApiKeyDialog && handleEditApiKey(showEditApiKeyDialog)}
              disabled={!editKeyData.name || actionLoading === `edit-${showEditApiKeyDialog}`}
            >
              {actionLoading === `edit-${showEditApiKeyDialog}` ? "Updating..." : "Update API Key"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Password Reset Dialog */}
      <Dialog open={showPasswordDialog} onOpenChange={setShowPasswordDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
            <DialogDescription>
              Set a new password for {selectedUser?.username}. The password must be at least 8 characters long.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={passwordForm.new_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                placeholder="Enter new password"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="confirm-password">Confirm Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={passwordForm.confirm_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                placeholder="Confirm new password"
              />
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="force-change"
                checked={passwordForm.force_change_on_login}
                onChange={(e) => setPasswordForm({ ...passwordForm, force_change_on_login: e.target.checked })}
                className="rounded border-border"
              />
              <Label htmlFor="force-change" className="text-sm font-normal">
                Force password change on next login
              </Label>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowPasswordDialog(false)}>
              Cancel
            </Button>
            <Button onClick={resetPassword}>
              Reset Password
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
