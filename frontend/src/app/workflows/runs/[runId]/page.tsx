"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useCallback, useEffect, useState } from "react"
import {
  ArrowLeft,
  Loader2,
  Play,
  RefreshCcw,
  RotateCcw,
  XCircle,
} from "lucide-react"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowRunTimeline } from "@/components/workflows/WorkflowRunTimeline"
import { Button } from "@/components/ui/button"
import { PageSkeleton } from "@/components/ui/skeletons"
import { StatusBadge, StatusBadgeStatus } from "@/components/ui/status-badge"
import {
  WorkflowRunDetail,
  WorkflowRunStatus,
  workflowRunApi,
} from "@/lib/api-client"

export default function WorkflowRunPage() {
  return (
    <ProtectedRoute>
      <WorkflowRunPageContent />
    </ProtectedRoute>
  )
}

function WorkflowRunPageContent() {
  const params = useParams<{ runId: string }>()
  const runId = params.runId
  const [run, setRun] = useState<WorkflowRunDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [action, setAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadRun = useCallback(async () => {
    if (!runId) return
    setError(null)
    try {
      const response = await workflowRunApi.getRun(runId)
      setRun(response.run)
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }, [runId])

  useEffect(() => {
    loadRun()
  }, [loadRun])

  async function runAction(kind: "cancel" | "retry" | "execute") {
    if (!run) return
    setAction(kind)
    setError(null)
    try {
      const response =
        kind === "cancel"
          ? await workflowRunApi.cancelRun(run.id, "Cancelled from run detail")
          : kind === "retry"
            ? await workflowRunApi.retryRun(run.id, "Retried from run detail")
            : await workflowRunApi.executeRun(run.id)
      setRun(response.run)
      if (!response.success && response.error) {
        setError(response.error)
      }
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setAction(null)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background p-6">
        <PageSkeleton className="mx-auto max-w-6xl" />
      </div>
    )
  }

  if (!run) {
    return (
      <main className="min-h-screen bg-background">
        <div className="mx-auto max-w-6xl px-4 py-8">
          <div className="rounded-lg border bg-card p-6">
            <p className="text-sm text-muted-foreground">
              {error || "Workflow run not found."}
            </p>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <Button asChild variant="ghost" size="sm" className="w-fit px-2">
              <Link href="/dashboard">
                <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
                Back
              </Link>
            </Button>
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="break-words text-2xl font-semibold tracking-normal">
                  {run.workflow_name || "Workflow Run"}
                </h1>
                <StatusBadge status={runTone(run.status)}>{run.status}</StatusBadge>
              </div>
              <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                <span className="break-all">{run.id}</span>
                <span>Version {run.version_number ?? "n/a"}</span>
                <span>{formatDate(run.created_at)}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={loadRun}
              disabled={action !== null}
              title="Refresh run"
            >
              <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
              Refresh
            </Button>
            {canExecute(run.status) ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => runAction("execute")}
                disabled={action !== null}
                title="Execute run"
              >
                {action === "execute" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Play className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Execute
              </Button>
            ) : null}
            {canRetry(run.status) ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => runAction("retry")}
                disabled={action !== null}
                title="Retry run"
              >
                {action === "retry" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Retry
              </Button>
            ) : null}
            {canCancel(run.status) ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => runAction("cancel")}
                disabled={action !== null}
                title="Cancel run"
              >
                {action === "cancel" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <XCircle className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Cancel
              </Button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded-lg border border-warning-border bg-warning-soft p-4 text-sm text-warning-soft-foreground">
            {error}
          </div>
        ) : null}

        <WorkflowRunTimeline run={run} />
      </div>
    </main>
  )
}

function canExecute(status: WorkflowRunStatus): boolean {
  return status === "queued"
}

function canCancel(status: WorkflowRunStatus): boolean {
  return status === "queued" || status === "running" || status === "paused"
}

function canRetry(status: WorkflowRunStatus): boolean {
  return status === "failed" || status === "cancelled" || status === "skipped"
}

function runTone(status: WorkflowRunStatus): StatusBadgeStatus {
  if (status === "succeeded") return "success"
  if (status === "running") return "info"
  if (status === "queued" || status === "paused") return "warning"
  if (status === "failed" || status === "cancelled") return "danger"
  return "neutral"
}

function formatDate(value?: string | null): string {
  if (!value) return "Not set"
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function errorMessage(error: any): string {
  const detail = error?.details?.detail
  if (typeof detail === "string") return detail
  if (detail?.message) return detail.message
  return error?.message || "Workflow run request failed"
}
