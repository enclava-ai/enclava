"use client"

import { useParams } from "next/navigation"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowBuilder } from "@/components/workflows/WorkflowBuilder"

export default function EditWorkflowPage() {
  const params = useParams<{ workflowId: string }>()

  return (
    <ProtectedRoute>
      <WorkflowBuilder mode="edit" workflowId={params.workflowId} />
    </ProtectedRoute>
  )
}
