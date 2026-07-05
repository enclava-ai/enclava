"use client"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowBuilder } from "@/components/workflows/WorkflowBuilder"

export default function NewWorkflowPage() {
  return (
    <ProtectedRoute>
      <WorkflowBuilder mode="create" />
    </ProtectedRoute>
  )
}
