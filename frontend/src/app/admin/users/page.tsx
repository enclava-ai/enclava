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
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import {
  UserPlus,
  Search,
  Filter,
  MoreHorizontal,
  Users,
  UserCheck,
  UserX,
  Shield,
  Edit,
  Trash2,
  Lock,
  Unlock,
  Key
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
}

interface Role {
  id: number;
  name: string;
  display_name: string;
  level: string;
  description?: string;
  is_active: boolean;
}

interface CreateUserForm {
  email: string;
  username: string;
  password: string;
  full_name: string;
  role_id: number | null;
  is_active: boolean;
  is_verified: boolean;
}

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

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    skip: 0,
    limit: 20,
    total: 0
  });

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modals
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [passwordForm, setPasswordForm] = useState({
    new_password: "",
    confirm_password: "",
    force_change_on_login: true,
  });

  // Forms
  const [createForm, setCreateForm] = useState<CreateUserForm>({
    email: "",
    username: "",
    password: "",
    full_name: "",
    role_id: null,
    is_active: true,
    is_verified: false
  });

  useEffect(() => {
    fetchData();
  }, [pagination.skip, pagination.limit, searchTerm, roleFilter, statusFilter]);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch users
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

      // Fetch roles
      const rolesResponse = await apiClient.get("/api-internal/v1/user-management/roles");
      // Backend returns array directly, not wrapped in { roles: [...] }
      setRoles(Array.isArray(rolesResponse) ? rolesResponse : (rolesResponse.roles || []));

    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to fetch data"));
    } finally {
      setLoading(false);
    }
  };

  const createUser = async () => {
    try {
      await apiClient.post("/api-internal/v1/user-management/users", createForm);
      toast.success("User created successfully");
      setShowCreateDialog(false);
      setCreateForm({
        email: "",
        username: "",
        password: "",
        full_name: "",
        role_id: null,
        is_active: true,
        is_verified: false
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

  const assignRole = async (userId: number, roleId: number) => {
    try {
      await apiClient.post(`/api-internal/v1/user-management/users/${userId}/assign-role`, {
        role_id: roleId
      });
      toast.success("Role assigned successfully");
      fetchData();
    } catch (error: any) {
      toast.error(getErrorMessage(error, "Failed to assign role"));
    }
  };

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
            Manage users, roles, and permissions
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <UserPlus className="mr-2 h-4 w-4" />
              Create User
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
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
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  placeholder="user@example.com"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={createForm.username}
                  onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                  placeholder="username"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  placeholder="••••••••"
                />
                <p className="text-sm text-muted-foreground">
                  Must be at least 8 characters long
                </p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="full_name">Full Name</Label>
                <Input
                  id="full_name"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                  placeholder="John Doe"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="role">Role</Label>
                <Select
                  value={createForm.role_id?.toString() || "none"}
                  onValueChange={(value) => setCreateForm({ ...createForm, role_id: value !== "none" ? parseInt(value) : null })}
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
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={createUser}>Create User</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Edit User Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>
              Update user information. Leave password blank to keep current password.
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
                      setSelectedUser({ ...selectedUser, role, role_id: role?.id });
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
                  className="rounded border-gray-300"
                />
                <Label htmlFor="edit-is-active">Active</Label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-is-verified"
                  checked={selectedUser.is_verified}
                  onChange={(e) => setSelectedUser({ ...selectedUser, is_verified: e.target.checked })}
                  className="rounded border-gray-300"
                />
                <Label htmlFor="edit-is-verified">Verified</Label>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
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

                // Only include role_id if it was explicitly set (including 0 for "none")
                if (selectedUser.role_id !== undefined) {
                  updates.role_id = selectedUser.role_id;
                } else if (selectedUser.role) {
                  updates.role_id = selectedUser.role.id;
                }

                updateUser(selectedUser.id, updates);
                setShowEditDialog(false);
              }
            }}>
              Save Changes
            </Button>
          </div>
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
                className="rounded border-gray-300"
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

      {/* Filters */}
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
                <TableHead>Created</TableHead>
                <TableHead>Last Login</TableHead>
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
                    {new Date(user.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    {user.last_login ? (
                      new Date(user.last_login).toLocaleDateString()
                    ) : (
                      <span className="text-sm text-muted-foreground">Never</span>
                    )}
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
                          setShowEditDialog(true);
                        }}>
                          <Edit className="mr-2 h-4 w-4" />
                          Edit
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
                          className="text-red-600"
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
    </div>
  );
}