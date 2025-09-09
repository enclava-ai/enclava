"use client"

import { createContext, useContext, useState, useEffect, ReactNode } from "react"
import { useRouter } from "next/navigation"
import { tokenManager } from "@/lib/token-manager"

interface User {
  id: string
  email: string
  name: string
  role: string
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  // Initialize auth state and listen to token manager events
  useEffect(() => {
    const initAuth = async () => {
      // Check if we have valid tokens
      if (tokenManager.isAuthenticated()) {
        // Try to get user info
        await fetchUserInfo()
      }
      setIsLoading(false)
    }

    // Set up event listeners
    const handleTokensUpdated = () => {
      // Tokens were updated (refreshed), update user if needed
      if (!user) {
        fetchUserInfo()
      }
    }

    const handleTokensCleared = () => {
      // Tokens were cleared, clear user
      setUser(null)
    }

    const handleSessionExpired = (reason: string) => {
      console.log('Session expired:', reason)
      setUser(null)
      // TokenManager and API client will handle redirect
    }

    const handleLogout = () => {
      setUser(null)
      router.push('/login')
    }

    // Register event listeners
    tokenManager.on('tokensUpdated', handleTokensUpdated)
    tokenManager.on('tokensCleared', handleTokensCleared)
    tokenManager.on('sessionExpired', handleSessionExpired)
    tokenManager.on('logout', handleLogout)

    // Initialize
    initAuth()

    // Cleanup
    return () => {
      tokenManager.off('tokensUpdated', handleTokensUpdated)
      tokenManager.off('tokensCleared', handleTokensCleared)
      tokenManager.off('sessionExpired', handleSessionExpired)
      tokenManager.off('logout', handleLogout)
    }
  }, [])

  const fetchUserInfo = async () => {
    try {
      const token = await tokenManager.getAccessToken()
      if (!token) return

      const response = await fetch('/api-internal/v1/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (response.ok) {
        const userData = await response.json()
        const user = {
          id: userData.id || userData.sub,
          email: userData.email,
          name: userData.name || userData.email,
          role: userData.role || 'user',
        }
        setUser(user)
        
        // Store user info for offline access
        if (typeof window !== 'undefined') {
          localStorage.setItem('user', JSON.stringify(user))
        }
      }
    } catch (error) {
      console.error('Failed to fetch user info:', error)
    }
  }

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    
    try {
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
      
      // Store tokens in TokenManager
      tokenManager.setTokens(
        data.access_token,
        data.refresh_token,
        data.expires_in
      )
      
      // Fetch user info
      await fetchUserInfo()
      
      // Navigate to dashboard
      router.push('/dashboard')
      
    } catch (error) {
      console.error('Login error:', error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    tokenManager.logout()
    // Token manager will emit 'logout' event which we handle above
  }

  return (
    <AuthContext.Provider 
      value={{ 
        user, 
        isAuthenticated: tokenManager.isAuthenticated(),
        login, 
        logout, 
        isLoading
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