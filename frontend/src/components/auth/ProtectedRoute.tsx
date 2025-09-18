"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/providers/auth-provider"

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth()
  const router = useRouter()
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
  }, [])

  useEffect(() => {
    if (isClient && !isLoading && !user) {
      router.push("/login")
    }
  }, [user, isLoading, router, isClient])

  // During SSR and initial client render, always show loading
  // This ensures consistent rendering between server and client
  if (!isClient || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
      </div>
    )
  }

  // If user is not authenticated after client hydration, don't render anything
  // (redirect is handled by useEffect)
  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
      </div>
    )
  }

  // User is authenticated, render the protected content
  return <>{children}</>
}