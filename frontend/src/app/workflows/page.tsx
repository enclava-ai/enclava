"use client"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowOperationsConsole } from "@/components/workflows/WorkflowOperationsConsole"

export default function WorkflowsPage() {
  return (
    <ProtectedRoute>
      <WorkflowOperationsConsole />
    </ProtectedRoute>
  )
}
