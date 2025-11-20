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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import {
  Shield,
  ShieldPlus,
  MoreHorizontal,
  Edit,
  Trash2,
  Users,
  Settings,
  DollarSign,
  FileText,
  Wrench
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Helper function to extract error messages
function getErrorMessage(error: any, defaultMessage: string = "An error occurred"): string {
  if (error.details?.details && Array.isArray(error.details.details)) {
    // Extract validation error messages from details array
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

export default function RoleManagement() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [stats, setStats] = useState<RoleStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Modals
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);

  // Forms
  const [createForm, setCreateForm] = useState<CreateRoleForm>({
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

  const roleLevels = [
    { value: "read_only", label: "Read Only", description: "Can only view own data" },
    { value: "user", label: "User", description: "Standard user with full access to own resources" },
    { value: "admin", label: "Administrator", description: "Can manage users and view reports" },
    { value: "super_admin", label: "Super Administrator", description: "Full system access" }
  ];

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch roles
      const rolesResponse = await apiClient.get("/api-internal/v1/user-management/roles");
      setRoles(rolesResponse || []);

      // Fetch statistics
      const statsResponse = await apiClient.get("/api-internal/v1/user-management/statistics");
      setStats(statsResponse.roles || null);

    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to fetch data"));
    } finally {
      setLoading(false);
    }
  };

  const createRole = async () => {
    try {
      const roleData = {
        ...createForm,
        permissions: {
          granted: [],
          denied: []
        },
        inherits_from: []
      };

      await apiClient.post("/api-internal/v1/user-management/roles", roleData);
      toast.success("Role created successfully");
      setShowCreateDialog(false);
      setCreateForm({
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

  const updateRole = async (roleId: number, updates: Partial<Role>) => {
    try {
      await apiClient.put(`/api-internal/v1/user-management/roles/${roleId}`, updates);
      toast.success("Role updated successfully");
      setShowEditDialog(false);
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

  if (loading) {
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
          <h1 className="text-3xl font-bold">Role Management</h1>
          <p className="text-muted-foreground">
            Manage roles and permissions
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
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
                <Label htmlFor="name">Role Name</Label>
                <Input
                  id="name"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  placeholder="developer_role"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="display_name">Display Name</Label>
                <Input
                  id="display_name"
                  value={createForm.display_name}
                  onChange={(e) => setCreateForm({ ...createForm, display_name: e.target.value })}
                  placeholder="Developer"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  placeholder="Role description..."
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="level">Level</Label>
                <Select
                  value={createForm.level}
                  onValueChange={(value) => setCreateForm({ ...createForm, level: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select level" />
                  </SelectTrigger>
                  <SelectContent>
                    {roleLevels.map((level) => (
                      <SelectItem key={level.value} value={level.value}>
                        <div>
                          <div className="font-medium">{level.label}</div>
                          <div className="text-sm text-muted-foreground">{level.description}</div>
                        </div>
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
                      id="manage_users"
                      checked={createForm.can_manage_users}
                      onCheckedChange={(checked) =>
                        setCreateForm({ ...createForm, can_manage_users: checked as boolean })
                      }
                    />
                    <Label htmlFor="manage_users" className="text-sm">Can manage users</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="manage_budgets"
                      checked={createForm.can_manage_budgets}
                      onCheckedChange={(checked) =>
                        setCreateForm({ ...createForm, can_manage_budgets: checked as boolean })
                      }
                    />
                    <Label htmlFor="manage_budgets" className="text-sm">Can manage budgets</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="view_reports"
                      checked={createForm.can_view_reports}
                      onCheckedChange={(checked) =>
                        setCreateForm({ ...createForm, can_view_reports: checked as boolean })
                      }
                    />
                    <Label htmlFor="view_reports" className="text-sm">Can view reports</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="manage_tools"
                      checked={createForm.can_manage_tools}
                      onCheckedChange={(checked) =>
                        setCreateForm({ ...createForm, can_manage_tools: checked as boolean })
                      }
                    />
                    <Label htmlFor="manage_tools" className="text-sm">Can manage tools</Label>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={createRole}>Create Role</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Roles</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_roles}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Roles</CardTitle>
              <Settings className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.active_roles}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Roles</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.system_roles}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Custom Roles</CardTitle>
              <ShieldPlus className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_roles - stats.system_roles}</div>
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
                              setShowEditDialog(true);
                            }}>
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => deleteRole(role.id)}
                              className="text-red-600"
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
    </div>
  );
}