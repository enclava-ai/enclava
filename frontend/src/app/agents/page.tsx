"use client"

import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AgentConfigManager } from '@/components/agent/AgentConfigManager'

export default function AgentsPage() {
  return (
    <ProtectedRoute>
      <AgentsPageContent />
    </ProtectedRoute>
  )
}

function AgentsPageContent() {
  return (
    <div className="container mx-auto px-4 py-8">
      <AgentConfigManager />
    </div>
  )
}
