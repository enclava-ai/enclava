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
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)
  const router = useRouter()

  useEffect(() => {
    setIsMounted(true)
    
    // Check for existing session on mount (client-side only)
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("token")
      if (token) {
        // In a real app, validate the token with the backend
        // For now, just set a demo user - also handle both email domains
        setUser({
          id: "1",
          email: "admin@example.com",
          name: "Admin User",
          role: "admin"
        })
        // Ensure we have a fresh token
        localStorage.setItem("token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzU2MDEzNjk5fQ.qcpQfqO8E-0qQpla1nMwHUGF0Th25GLpmqGW5LO2I70")
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
        
        setUser(demoUser)
        if (typeof window !== "undefined") {
          // Use the actual JWT token for API calls
          localStorage.setItem("token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzU2MDEzNjk5fQ.qcpQfqO8E-0qQpla1nMwHUGF0Th25GLpmqGW5LO2I70")
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
    if (typeof window !== "undefined") {
      localStorage.removeItem("token")
      localStorage.removeItem("user")
    }
    router.push("/login")
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
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
        login: async () => {},
        logout: () => {},
        isLoading: true
      }
    }
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}