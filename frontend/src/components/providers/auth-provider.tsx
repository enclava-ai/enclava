"use client"

import * as React from "react"
import { createContext, useContext, useEffect, useState } from "react"
import { apiClient } from "@/lib/api-client"
import { tokenManager } from "@/lib/token-manager"

interface User {
  id: string
  username: string
  email: string
  name?: string
  role: string
  permissions: string[]
  created_at: string
  updated_at: string
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
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
    const token = tokenManager.getAccessToken()
    if (token) {
      // Validate token and get user info
      validateToken(token)
    } else {
      setIsLoading(false)
    }
  }, [])

  const validateToken = async (token: string) => {
    try {
      const userData = await apiClient.get("/api-internal/v1/auth/me")
      setUser(userData)
    } catch (error) {
      tokenManager.clearTokens()
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string, password: string) => {
    try {
      const data = await apiClient.post("/api-internal/v1/auth/login", { email, password })
      
      // Store tokens using tokenManager
      tokenManager.setTokens(data.access_token, data.refresh_token)
      
      // Get user info
      await validateToken(data.access_token)
    } catch (error) {
      throw error
    }
  }

  const register = async (username: string, email: string, password: string) => {
    try {
      const data = await apiClient.post("/api-internal/v1/auth/register", { username, email, password })
      
      // Store tokens using tokenManager
      tokenManager.setTokens(data.access_token, data.refresh_token)
      
      // Get user info
      await validateToken(data.access_token)
    } catch (error) {
      throw error
    }
  }

  const logout = () => {
    tokenManager.clearTokens()
    setUser(null)
  }

  const refreshToken = async () => {
    try {
      const refresh_token = tokenManager.getRefreshToken()
      if (!refresh_token) {
        throw new Error("No refresh token available")
      }

      const data = await apiClient.post("/api-internal/v1/auth/refresh", { refresh_token })
      tokenManager.setTokens(data.access_token, refresh_token)
      
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
    isAuthenticated: !!user,
    login,
    logout,
    register,
    refreshToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
