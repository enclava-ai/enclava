"use client"

import { Suspense } from "react"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowBuilder } from "@/components/workflows/WorkflowBuilder"

export default function NewWorkflowPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <WorkflowBuilder mode="create" />
      </Suspense>
    </ProtectedRoute>
  )
}
