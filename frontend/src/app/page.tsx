"use client"

import { useAuth } from "@/contexts/AuthContext"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

// Force dynamic rendering for authentication
export const dynamic = 'force-dynamic'
import { Button } from "@/components/ui/button"
import { Shield, ExternalLink } from "lucide-react"

export default function HomePage() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && user) {
      router.push("/dashboard")
    }
  }, [user, isLoading, router])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
      </div>
    )
  }

  if (user) {
    return null // Will redirect to dashboard
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-empire-dark to-empire-darker">
      {/* Header */}
      <header className="border-b border-empire-gold/20">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-empire-gold rounded-lg flex items-center justify-center">
                <Shield className="w-5 h-5 text-empire-dark" />
              </div>
              <span className="text-xl font-bold text-empire-gold">Enclava</span>
            </div>
            <nav className="flex items-center space-x-6">
              <Button 
                variant="ghost" 
                onClick={() => router.push("/login")}
                className="text-empire-gold/60 hover:text-empire-gold"
              >
                Login
              </Button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center py-20">
        <div className="container mx-auto px-4 text-center">
          <div className="max-w-2xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-bold mb-6 text-empire-gold">
              Enclava AI Platform
            </h1>
            <p className="text-xl text-empire-gold/60 mb-12">
            Making Private AI practical
            </p>
            
            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
              <Button 
                size="lg" 
                onClick={() => router.push("/login")}
                className="bg-empire-gold text-empire-dark hover:bg-empire-gold/90"
              >
                Get Started
              </Button>
            </div>

            {/* Links */}
            <div className="flex flex-col sm:flex-row gap-6 justify-center text-empire-gold/60">
              <a 
                href="https://enclava.ai" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 hover:text-empire-gold transition-colors"
              >
                <span>Company Website</span>
                <ExternalLink className="w-4 h-4" />
              </a>
              <a 
                href="https://docs.enclava.ai" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 hover:text-empire-gold transition-colors"
              >
                <span>Documentation</span>
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>
      </main>

      {/* Simple Footer */}
      <footer className="border-t border-empire-gold/20 py-8">
        <div className="container mx-auto px-4 text-center">
          <div className="flex items-center justify-center space-x-2 mb-4">
            <div className="w-6 h-6 bg-empire-gold rounded flex items-center justify-center">
              <Shield className="w-4 h-4 text-empire-dark" />
            </div>
            <span className="font-semibold text-empire-gold">Enclava</span>
          </div>
          <p className="text-sm text-empire-gold/60">
            &copy; 2024 Enclava. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}