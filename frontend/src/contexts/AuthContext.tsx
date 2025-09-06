"use client"

import { createContext, useContext, useState, useEffect, ReactNode, useRef } from "react"
import { useRouter } from "next/navigation"
import { 
  isTokenExpired, 
  refreshAccessToken, 
  storeTokens, 
  getStoredTokens, 
  clearTokens,
  setupTokenRefreshTimer,
  decodeToken
} from "@/lib/auth-utils"

interface User {
  id: string
  email: string
  name: string
  role: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  refreshToken: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
  refreshTokenIfNeeded: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = async () => {
      if (typeof window === "undefined") return

      // Don't try to refresh on auth-related pages
      const isAuthPage = window.location.pathname === '/login' || 
                        window.location.pathname === '/register' ||
                        window.location.pathname === '/forgot-password'

      const { accessToken, refreshToken: storedRefreshToken } = getStoredTokens()
      
      if (accessToken && storedRefreshToken) {
        // Check if token is expired
        if (isTokenExpired(accessToken)) {
          // Only try to refresh if not on auth pages
          if (!isAuthPage) {
            // Try to refresh the token
            const response = await refreshAccessToken(storedRefreshToken)
            if (response) {
              storeTokens(response.access_token, response.refresh_token)
              setToken(response.access_token)
              setRefreshToken(response.refresh_token)
              
              // Decode token to get user info
              const payload = decodeToken(response.access_token)
              if (payload) {
                const storedUser = localStorage.getItem("user")
                if (storedUser) {
                  setUser(JSON.parse(storedUser))
                }
              }
              
              // Setup refresh timer
              setupRefreshTimer(response.access_token, response.refresh_token)
            } else {
              // Refresh failed, clear everything
              clearTokens()
              setUser(null)
              setToken(null)
              setRefreshToken(null)
            }
          } else {
            // On auth pages with expired token, just clear it
            clearTokens()
            setUser(null)
            setToken(null)
            setRefreshToken(null)
          }
        } else {
          // Token is still valid
          setToken(accessToken)
          setRefreshToken(storedRefreshToken)
          
          const storedUser = localStorage.getItem("user")
          if (storedUser) {
            setUser(JSON.parse(storedUser))
          }
          
          // Setup refresh timer
          setupRefreshTimer(accessToken, storedRefreshToken)
        }
      }
      
      setIsLoading(false)
    }

    initAuth()
  }, [])

  // Setup token refresh timer
  const setupRefreshTimer = (accessToken: string, refreshTokenValue: string) => {
    // Clear existing timer
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
    }

    refreshTimerRef.current = setupTokenRefreshTimer(
      accessToken,
      refreshTokenValue,
      (newAccessToken) => {
        setToken(newAccessToken)
      },
      () => {
        // Refresh failed, logout user
        logout()
      }
    )
  }

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current)
      }
    }
  }, [])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    
    try {
      // Call real backend login endpoint
      const response = await fetch('/api-internal/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Invalid credentials')
      }

      const data = await response.json()
      
      // Store tokens
      storeTokens(data.access_token, data.refresh_token)
      
      // Decode token to get user info
      const payload = decodeToken(data.access_token)
      if (payload) {
        // Fetch user details
        const userResponse = await fetch('/api-internal/v1/auth/me', {
          headers: {
            'Authorization': `Bearer ${data.access_token}`,
          },
        })
        
        if (userResponse.ok) {
          const userData = await userResponse.json()
          const user = {
            id: userData.id || payload.sub,
            email: userData.email || payload.email || email,
            name: userData.name || userData.email || email,
            role: userData.role || 'user',
          }
          
          localStorage.setItem("user", JSON.stringify(user))
          setUser(user)
        }
      }
      
      setToken(data.access_token)
      setRefreshToken(data.refresh_token)
      
      // Setup refresh timer
      setupRefreshTimer(data.access_token, data.refresh_token)
      
    } catch (error) {
      console.error('Login error:', error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    // Clear refresh timer
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = null
    }
    
    // Clear state
    setUser(null)
    setToken(null)
    setRefreshToken(null)
    
    // Clear localStorage
    clearTokens()
    
    // Redirect to login
    router.push("/login")
  }

  const refreshTokenIfNeeded = async (): Promise<boolean> => {
    if (!token || !refreshToken) {
      return false
    }

    if (isTokenExpired(token)) {
      const response = await refreshAccessToken(refreshToken)
      if (response) {
        storeTokens(response.access_token, response.refresh_token)
        setToken(response.access_token)
        setRefreshToken(response.refresh_token)
        setupRefreshTimer(response.access_token, response.refresh_token)
        return true
      } else {
        logout()
        return false
      }
    }

    return true
  }

  return (
    <AuthContext.Provider 
      value={{ 
        user, 
        token, 
        refreshToken,
        login, 
        logout, 
        isLoading,
        refreshTokenIfNeeded
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}