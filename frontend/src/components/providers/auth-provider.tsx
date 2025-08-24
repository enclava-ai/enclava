"use client"

import * as React from "react"
import { createContext, useContext, useEffect, useState } from "react"
import { apiClient } from "@/lib/api-client"

interface User {
  id: string
  username: string
  email: string
  role: string
  permissions: string[]
  created_at: string
  updated_at: string
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  register: (username: string, email: string, password: string) => Promise<void>
  refreshToken: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check for existing token on mount
    const token = localStorage.getItem("access_token")
    if (token) {
      // Validate token and get user info
      validateToken(token)
    } else {
      setIsLoading(false)
    }
  }, [])

  const validateToken = async (token: string) => {
    try {
      // Temporarily set token in localStorage for apiClient to use
      const previousToken = localStorage.getItem('token')
      localStorage.setItem('token', token)
      
      const userData = await apiClient.get("/api-internal/v1/auth/me")
      setUser(userData)
      
      // Restore previous token if different
      if (previousToken && previousToken !== token) {
        localStorage.setItem('token', previousToken)
      }
    } catch (error) {
      console.error("Token validation failed:", error)
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (username: string, password: string) => {
    try {
      const data = await apiClient.post("/api-internal/v1/auth/login", { username, password })
      
      // Store tokens
      localStorage.setItem("access_token", data.access_token)
      localStorage.setItem("refresh_token", data.refresh_token)
      localStorage.setItem("token", data.access_token) // Also set token for apiClient
      
      // Get user info
      await validateToken(data.access_token)
    } catch (error) {
      throw error
    }
  }

  const register = async (username: string, email: string, password: string) => {
    try {
      const data = await apiClient.post("/api-internal/v1/auth/register", { username, email, password })
      
      // Store tokens
      localStorage.setItem("access_token", data.access_token)
      localStorage.setItem("refresh_token", data.refresh_token)
      localStorage.setItem("token", data.access_token) // Also set token for apiClient
      
      // Get user info
      await validateToken(data.access_token)
    } catch (error) {
      throw error
    }
  }

  const logout = () => {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
    localStorage.removeItem("token") // Also clear token for apiClient
    setUser(null)
  }

  const refreshToken = async () => {
    try {
      const refresh_token = localStorage.getItem("refresh_token")
      if (!refresh_token) {
        throw new Error("No refresh token available")
      }

      const data = await apiClient.post("/api-internal/v1/auth/refresh", { refresh_token })
      localStorage.setItem("access_token", data.access_token)
      localStorage.setItem("token", data.access_token) // Also set token for apiClient
      
      return data.access_token
    } catch (error) {
      // Refresh failed, logout user
      logout()
      throw error
    }
  }

  const value: AuthContextType = {
    user,
    isLoading,
    login,
    logout,
    register,
    refreshToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}