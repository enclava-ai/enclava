"use client"

import { useAuth } from "@/components/providers/auth-provider"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

// Force dynamic rendering for authentication
export const dynamic = 'force-dynamic'
import { Button } from "@/components/ui/button"
import { PageSkeleton } from "@/components/ui/skeletons"
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
      <div className="min-h-screen bg-background p-6">
        <PageSkeleton className="mx-auto max-w-4xl" />
      </div>
    )
  }

  if (user) {
    return null // Will redirect to dashboard
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center py-20">
        <div className="container mx-auto px-4 text-center">
          <div className="max-w-2xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-bold mb-6 text-foreground">
              Enclava AI Platform
            </h1>
            <p className="text-xl text-muted-foreground mb-12">
              Making Private AI practical
            </p>
            
            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
              <Button 
                size="lg" 
                onClick={() => router.push("/login")}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                Get Started
              </Button>
            </div>

            {/* Links */}
            <div className="flex flex-col sm:flex-row gap-6 justify-center text-muted-foreground">
              <a 
                href="https://enclava.ai" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 hover:text-foreground transition-colors"
              >
                <span>Company Website</span>
                <ExternalLink className="w-4 h-4" />
              </a>
              <a 
                href="https://docs.enclava.ai" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 hover:text-foreground transition-colors"
              >
                <span>Documentation</span>
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
