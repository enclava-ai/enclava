"use client"

import { createContext, useContext, useState, useEffect, ReactNode } from "react"
import { useRouter } from "next/navigation"

interface User {
  id: string
  email: string
  name: string
  role: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  // Initialize state with values from localStorage if available (synchronous)
  const getInitialAuth = () => {
    if (typeof window !== "undefined") {
      const storedToken = localStorage.getItem("token")
      if (storedToken) {
        // Ensure we have the correct token
        const freshToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzU2NjE4Mzk2fQ.DFZOtAzJbpF_PcKhj2DWRDXUvTKFss-8lEt5H3ST2r0"
        localStorage.setItem("token", freshToken)
        return {
          user: {
            id: "1",
            email: "admin@example.com",
            name: "Admin User",
            role: "admin"
          },
          token: freshToken
        }
      }
    }
    return { user: null, token: null }
  }

  const initialAuth = getInitialAuth()
  const [user, setUser] = useState<User | null>(initialAuth.user)
  const [token, setToken] = useState<string | null>(initialAuth.token)
  const [isLoading, setIsLoading] = useState(false) // Not loading if we already have auth
  const router = useRouter()

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    
    try {
      // Demo authentication - in real app, this would call the backend
      if ((email === "admin@example.com" || email === "admin@localhost") && password === "admin123") {
        const demoUser = {
          id: "1",
          email: email,
          name: "Admin User",
          role: "admin"
        }
        
        const authToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzU2NjE4Mzk2fQ.DFZOtAzJbpF_PcKhj2DWRDXUvTKFss-8lEt5H3ST2r0"
        
        // Store in localStorage first to ensure it's immediately available
        if (typeof window !== "undefined") {
          // Use the actual JWT token for API calls
          localStorage.setItem("token", authToken)
          localStorage.setItem("user", JSON.stringify(demoUser))
        }
        
        // Then update state
        setUser(demoUser)
        setToken(authToken)
        
        // Wait a tick to ensure state has propagated
        await new Promise(resolve => setTimeout(resolve, 50))
      } else {
        throw new Error("Invalid credentials")
      }
    } catch (error) {
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    setUser(null)
    setToken(null)
    if (typeof window !== "undefined") {
      localStorage.removeItem("token")
      localStorage.removeItem("user")
    }
    router.push("/login")
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    // During SSR/SSG, return default values instead of throwing
    if (typeof window === "undefined") {
      return {
        user: null,
        token: null,
        login: async () => {},
        logout: () => {},
        isLoading: true
      }
    }
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}