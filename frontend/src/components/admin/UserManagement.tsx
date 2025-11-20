"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { useToast } from "@/hooks/use-toast"
import {
  Search,
  Plus,
  MoreHorizontal,
  Edit,
  Trash2,
  Key,
  Eye,
  Shield,
  AlertCircle,
  CheckCircle,
  Clock,
  Users,
} from "lucide-react"

interface User {
  id: number
  email: string
  username: string
  full_name?: string
  role_id?: number
  role?: {
    id: number
    name: string
    display_name: string
    level: string
  }
  is_active: boolean
  is_verified: boolean
  account_locked: boolean
  force_password_change: boolean
  created_at: string
  updated_at: string
  last_login?: string
}

interface Role {
  id: number
  name: string
  display_name: string
  description?: string
  level: string
  is_active: boolean
}

interface UserFormData {
  email: string
  username: string
  password: string
  full_name: string
  role_id: number | null
  is_active: boolean
  force_password_change: boolean
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")
  const [roleFilter, setRoleFilter] = useState<string>("all")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showPasswordDialog, setShowPasswordDialog] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [formData, setFormData] = useState<UserFormData>({
    email: "",
    username: "",
    password: "",
    full_name: "",
    role_id: null,
    is_active: true,
    force_password_change: false,
  })
  const [passwordData, setPasswordData] = useState({
    new_password: "",
    force_change_on_login: true,
  })

  const { toast } = useToast()

  useEffect(() => {
    fetchUsers()
    fetchRoles()
  }, [])

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const response = await fetch("/api-internal/v1/admin/user-management/users", {
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
      })

      if (!response.ok) {
        throw new Error("Failed to fetch users")
      }

      const data = await response.json()
      setUsers(data.users || [])
    } catch (error) {
      console.error("Error fetching users:", error)
      toast({
        title: "Error",
        description: "Failed to fetch users",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const fetchRoles = async () => {
    try {
      const response = await fetch("/api-internal/v1/admin/user-management/roles", {
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
      })

      if (!response.ok) {
        throw new Error("Failed to fetch roles")
      }

      const data = await response.json()
      setRoles(data)
    } catch (error) {
      console.error("Error fetching roles:", error)
      toast({
        title: "Error",
        description: "Failed to fetch roles",
        variant: "destructive",
      })
    }
  }

  const handleCreateUser = async () => {
    try {
      const response = await fetch("/api-internal/v1/admin/user-management/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(formData),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to create user")
      }

      toast({
        title: "Success",
        description: "User created successfully",
      })

      setShowCreateDialog(false)
      resetForm()
      fetchUsers()
    } catch (error) {
      console.error("Error creating user:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create user",
        variant: "destructive",
      })
    }
  }

  const handleUpdateUser = async () => {
    if (!selectedUser) return

    try {
      const { password, ...updateData } = formData
      const response = await fetch(`/api-internal/v1/admin/user-management/users/${selectedUser.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(updateData),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to update user")
      }

      toast({
        title: "Success",
        description: "User updated successfully",
      })

      setShowEditDialog(false)
      setSelectedUser(null)
      resetForm()
      fetchUsers()
    } catch (error) {
      console.error("Error updating user:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to update user",
        variant: "destructive",
      })
    }
  }

  const handlePasswordReset = async () => {
    if (!selectedUser) return

    try {
      const response = await fetch(`/api-internal/v1/admin/user-management/users/${selectedUser.id}/password-reset`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(passwordData),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to reset password")
      }

      toast({
        title: "Success",
        description: "Password reset successfully",
      })

      setShowPasswordDialog(false)
      setSelectedUser(null)
      setPasswordData({ new_password: "", force_change_on_login: true })
      fetchUsers()
    } catch (error) {
      console.error("Error resetting password:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to reset password",
        variant: "destructive",
      })
    }
  }

  const handleDeleteUser = async (user: User) => {
    if (!confirm(`Are you sure you want to deactivate user ${user.email}?`)) {
      return
    }

    try {
      const response = await fetch(`/api-internal/v1/admin/user-management/users/${user.id}`, {
        method: "DELETE",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to delete user")
      }

      toast({
        title: "Success",
        description: "User deactivated successfully",
      })

      fetchUsers()
    } catch (error) {
      console.error("Error deleting user:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete user",
        variant: "destructive",
      })
    }
  }

  const resetForm = () => {
    setFormData({
      email: "",
      username: "",
      password: "",
      full_name: "",
      role_id: null,
      is_active: true,
      force_password_change: false,
    })
  }

  const openEditDialog = (user: User) => {
    setSelectedUser(user)
    setFormData({
      email: user.email,
      username: user.username,
      password: "",
      full_name: user.full_name || "",
      role_id: user.role_id || null,
      is_active: user.is_active,
      force_password_change: user.force_password_change,
    })
    setShowEditDialog(true)
  }

  const openPasswordDialog = (user: User) => {
    setSelectedUser(user)
    setShowPasswordDialog(true)
  }

  const filteredUsers = users.filter((user) => {
    const matchesSearch =
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (user.full_name && user.full_name.toLowerCase().includes(searchTerm.toLowerCase()))

    const matchesRole = roleFilter === "all" || user.role?.name === roleFilter
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && user.is_active) ||
      (statusFilter === "inactive" && !user.is_active) ||
      (statusFilter === "locked" && user.account_locked)

    return matchesSearch && matchesRole && matchesStatus
  })

  const getUserStatusBadge = (user: User) => {
    if (user.account_locked) {
      return <Badge variant="destructive">Locked</Badge>
    }
    if (!user.is_active) {
      return <Badge variant="secondary">Inactive</Badge>
    }
    if (!user.is_verified) {
      return <Badge variant="outline">Unverified</Badge>
    }
    return <Badge variant="default">Active</Badge>
  }

  const formatLastLogin = (lastLogin?: string) => {
    if (!lastLogin) return "Never"
    return new Date(lastLogin).toLocaleDateString()
  }

  return (
    <div className="space-y-6">
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
              <Plus className="mr-2 h-4 w-4" />
              Create User
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Create New User</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="user@example.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder="username"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="full_name">Full Name</Label>
                <Input
                  id="full_name"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="John Doe"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Password (min 8 characters)"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
                <Select
                  value={formData.role_id?.toString()}
                  onValueChange={(value) => setFormData({ ...formData, role_id: parseInt(value) })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a role" />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map((role) => (
                      <SelectItem key={role.id} value={role.id.toString()}>
                        {role.display_name} ({role.level})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="is_active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: !!checked })}
                />
                <Label htmlFor="is_active">Active user</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="force_password_change"
                  checked={formData.force_password_change}
                  onCheckedChange={(checked) => setFormData({ ...formData, force_password_change: !!checked })}
                />
                <Label htmlFor="force_password_change">Force password change on first login</Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateUser}>Create User</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{users.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {users.filter(u => u.is_active).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Locked</CardTitle>
            <Shield className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {users.filter(u => u.account_locked).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Need Password Change</CardTitle>
            <AlertCircle className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {users.filter(u => u.force_password_change).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4 items-center">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search users..."
                  className="pl-8"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
            <Select value={roleFilter} onValueChange={setRoleFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                {roles.map((role) => (
                  <SelectItem key={role.id} value={role.name}>
                    {role.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
                <SelectItem value="locked">Locked</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    <div className="flex items-center justify-center">
                      <Clock className="mr-2 h-4 w-4 animate-spin" />
                      Loading users...
                    </div>
                  </TableCell>
                </TableRow>
              ) : filteredUsers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    No users found
                  </TableCell>
                </TableRow>
              ) : (
                filteredUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{user.email}</div>
                        <div className="text-sm text-muted-foreground">
                          @{user.username}
                          {user.full_name && ` • ${user.full_name}`}
                        </div>
                        {user.force_password_change && (
                          <Badge variant="outline" className="mt-1 text-xs">
                            Password Change Required
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {user.role ? (
                        <Badge variant="secondary">
                          {user.role.display_name}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">No role</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {getUserStatusBadge(user)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatLastLogin(user.last_login)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
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
                          <DropdownMenuItem onClick={() => openEditDialog(user)}>
                            <Edit className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => openPasswordDialog(user)}>
                            <Key className="mr-2 h-4 w-4" />
                            Reset Password
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleDeleteUser(user)}>
                            <Trash2 className="mr-2 h-4 w-4" />
                            Deactivate
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit User Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit_email">Email</Label>
                <Input
                  id="edit_email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit_username">Username</Label>
                <Input
                  id="edit_username"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_full_name">Full Name</Label>
              <Input
                id="edit_full_name"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_role">Role</Label>
              <Select
                value={formData.role_id?.toString() || ""}
                onValueChange={(value) => setFormData({ ...formData, role_id: value ? parseInt(value) : null })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">No role</SelectItem>
                  {roles.map((role) => (
                    <SelectItem key={role.id} value={role.id.toString()}>
                      {role.display_name} ({role.level})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: !!checked })}
              />
              <Label htmlFor="edit_is_active">Active user</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_force_password_change"
                checked={formData.force_password_change}
                onCheckedChange={(checked) => setFormData({ ...formData, force_password_change: !!checked })}
              />
              <Label htmlFor="edit_force_password_change">Force password change on next login</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateUser}>Update User</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Password Reset Dialog */}
      <Dialog open={showPasswordDialog} onOpenChange={setShowPasswordDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="new_password">New Password</Label>
              <Input
                id="new_password"
                type="password"
                value={passwordData.new_password}
                onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                placeholder="Enter new password"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="force_change"
                checked={passwordData.force_change_on_login}
                onCheckedChange={(checked) => setPasswordData({ ...passwordData, force_change_on_login: !!checked })}
              />
              <Label htmlFor="force_change">Force user to change password on next login</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPasswordDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handlePasswordReset}>Reset Password</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}