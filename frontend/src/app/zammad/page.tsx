"use client"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { ZammadConfig } from "@/components/modules/ZammadConfig"

export default function ZammadPage() {
  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8">
        <ZammadConfig />
      </div>
    </ProtectedRoute>
  )
}