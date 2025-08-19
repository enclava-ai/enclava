"use client"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { SignalConfig } from "@/components/modules/SignalConfig"

export default function SignalPage() {
  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8">
        <SignalConfig />
      </div>
    </ProtectedRoute>
  )
}