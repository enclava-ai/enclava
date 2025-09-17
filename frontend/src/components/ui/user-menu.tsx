"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/contexts/AuthContext"
import { useToast } from "@/hooks/use-toast"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { User, Settings, Lock, LogOut, ChevronDown } from "lucide-react"
import { useState } from "react"

// Helper function to get API URL with proper protocol
const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol.slice(0, -1) // Remove ':' from 'https:'
    const host = window.location.hostname
    return `${protocol}://${host}`
  }
  return `http://${process.env.NEXT_PUBLIC_BASE_URL || 'localhost'}`
}

export function UserMenu() {
  const { user, logout } = useAuth()
  const { toast } = useToast()
  const [isPasswordDialogOpen, setIsPasswordDialogOpen] = useState(false)
  const [passwordData, setPasswordData] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: ""
  })
  const [isChangingPassword, setIsChangingPassword] = useState(false)

  if (!user) {
    return null
  }

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      toast({
        title: "Error",
        description: "New passwords do not match",
        variant: "destructive"
      })
      return
    }

    if (passwordData.newPassword.length < 8) {
      toast({
        title: "Error", 
        description: "Password must be at least 8 characters long",
        variant: "destructive"
      })
      return
    }

    setIsChangingPassword(true)

    try {
      const token = await import('@/lib/token-manager').then(m => m.tokenManager.getAccessToken())
      if (!token) {
        throw new Error('Authentication required')
      }

      const response = await fetch(`${getApiUrl()}/api-internal/v1/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          current_password: passwordData.currentPassword,
          new_password: passwordData.newPassword
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to change password')
      }

      toast({
        title: "Success",
        description: "Password changed successfully"
      })

      setIsPasswordDialogOpen(false)
      setPasswordData({
        currentPassword: "",
        newPassword: "",
        confirmPassword: ""
      })

    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to change password",
        variant: "destructive"
      })
    } finally {
      setIsChangingPassword(false)
    }
  }

  return (
    <div className="flex items-center space-x-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="flex items-center space-x-2 h-8">
            <Badge variant="secondary" className="hidden sm:inline-flex">
              {user.email}
            </Badge>
            <div className="sm:hidden">
              <User className="h-4 w-4" />
            </div>
            <ChevronDown className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <div className="flex items-center justify-start space-x-2 p-2">
            <div className="flex flex-col space-y-1 leading-none">
              <p className="font-medium">{user.name}</p>
              <p className="w-[200px] truncate text-sm text-muted-foreground">
                {user.email}
              </p>
            </div>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setIsPasswordDialogOpen(true)}>
            <Lock className="mr-2 h-4 w-4" />
            Change Password
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-red-600">
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Password Change Dialog - Outside dropdown to avoid nesting issues */}
      <Dialog open={isPasswordDialogOpen} onOpenChange={setIsPasswordDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Change Password</DialogTitle>
            <DialogDescription>
              Enter your current password and choose a new secure password.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handlePasswordChange} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">Current Password</Label>
              <Input
                id="current-password"
                type="password"
                value={passwordData.currentPassword}
                onChange={(e) => setPasswordData(prev => ({
                  ...prev,
                  currentPassword: e.target.value
                }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={passwordData.newPassword}
                onChange={(e) => setPasswordData(prev => ({
                  ...prev,
                  newPassword: e.target.value
                }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm New Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={passwordData.confirmPassword}
                onChange={(e) => setPasswordData(prev => ({
                  ...prev,
                  confirmPassword: e.target.value
                }))}
                required
              />
            </div>
            <div className="flex justify-end space-x-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsPasswordDialogOpen(false)}
                disabled={isChangingPassword}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isChangingPassword}>
                {isChangingPassword ? "Changing..." : "Change Password"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}