"use client"

import { Suspense } from "react"
import { useParams } from "next/navigation"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowBuilder } from "@/components/workflows/WorkflowBuilder"

export default function EditWorkflowPage() {
  const params = useParams<{ workflowId: string }>()

  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <WorkflowBuilder mode="edit" workflowId={params.workflowId} />
      </Suspense>
    </ProtectedRoute>
  )
}
