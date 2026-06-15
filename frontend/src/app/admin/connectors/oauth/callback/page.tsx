"use client"

import { useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Loader2 } from "lucide-react"
import { Suspense } from "react"
import { Skeleton } from "@/components/ui/skeleton"

function OAuthCallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const connectorId = searchParams.get("connector_id")
    const error = searchParams.get("error")

    // Redirect after 2 seconds
    const timer = setTimeout(() => {
      if (connectorId) {
        // Success - redirect with success params
        router.push(`/admin/connectors?oauth_success=true&connector_id=${connectorId}`)
      } else if (error) {
        // Error - redirect with error info
        router.push(`/admin/connectors?oauth_error=true&error=${encodeURIComponent(error)}`)
      } else {
        // No params - just redirect to connectors page
        router.push("/admin/connectors")
      }
    }, 2000)

    return () => clearTimeout(timer)
  }, [router, searchParams])

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-12 w-12 text-muted-foreground mb-4 animate-spin" />
          <h3 className="text-lg font-semibold mb-2">Completing Setup</h3>
          <p className="text-muted-foreground text-center">
            Processing your connector authorization. Redirecting you shortly...
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

// Wrapper with Suspense boundary for useSearchParams
export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[400px]">
          <Card className="w-full max-w-md">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Skeleton className="h-12 w-12 rounded-full mb-4" />
              <Skeleton className="h-6 w-48 mb-2" />
              <Skeleton className="h-4 w-64" />
            </CardContent>
          </Card>
        </div>
      }
    >
      <OAuthCallbackContent />
    </Suspense>
  )
}
