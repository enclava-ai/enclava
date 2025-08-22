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
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)
  const router = useRouter()

  useEffect(() => {
    setIsMounted(true)
    
    // Check for existing session on mount (client-side only)
    if (typeof window !== "undefined") {
      const storedToken = localStorage.getItem("token")
      if (storedToken) {
        // In a real app, validate the token with the backend
        // For now, just set a demo user - also handle both email domains
        setUser({
          id: "1",
          email: "admin@example.com",
          name: "Admin User",
          role: "admin"
        })
        setToken(storedToken)
        // Ensure we have a fresh token with extended expiration
        const freshToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg3Mzg5NjM3fQ.DKAx-rpNvrlRxb0YG1C63QWDvH63pIAsi8QniFvDXmc"
        localStorage.setItem("token", freshToken)
        setToken(freshToken)
      }
    }
    setIsLoading(false)
  }, [])

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
        
        const authToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg3Mzg5NjM3fQ.DKAx-rpNvrlRxb0YG1C63QWDvH63pIAsi8QniFvDXmc"
        
        setUser(demoUser)
        setToken(authToken)
        if (typeof window !== "undefined") {
          // Use the actual JWT token for API calls
          localStorage.setItem("token", authToken)
          localStorage.setItem("user", JSON.stringify(demoUser))
        }
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