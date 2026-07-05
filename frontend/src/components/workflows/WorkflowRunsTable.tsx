"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import { ExternalLink, Loader2, RefreshCcw, RotateCcw } from "lucide-react"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { StatusBadge, type StatusBadgeStatus } from "@/components/ui/status-badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  WorkflowOperationsRow,
  WorkflowRunStatus,
  WorkflowRunSummary,
  workflowApi,
  workflowRunApi,
} from "@/lib/api-client"

const statusOptions: Array<{ value: "all" | WorkflowRunStatus; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "paused", label: "Paused" },
  { value: "skipped", label: "Skipped" },
]

export function WorkflowRunsTable() {
  const { toast } = useToast()
  const [runs, setRuns] = useState<WorkflowRunSummary[]>([])
  const [workflows, setWorkflows] = useState<WorkflowOperationsRow[]>([])
  const [workflowId, setWorkflowId] = useState("all")
  const [status, setStatus] = useState<"all" | WorkflowRunStatus>("all")
  const [isLoading, setIsLoading] = useState(true)
  const [actionId, setActionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadRuns = useCallback(async () => {
    setError(null)
    try {
      const [runsResponse, operationsResponse] = await Promise.all([
        workflowApi.getRecentRuns({
          workflow_id: workflowId === "all" ? undefined : workflowId,
          status: status === "all" ? undefined : status,
          limit: 50,
        }),
        workflowApi.getOperations(),
      ])
      setRuns(runsResponse.runs)
      setWorkflows(operationsResponse.operations.workflows)
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }, [status, workflowId])

  useEffect(() => {
    loadRuns()
  }, [loadRuns])

  const workflowOptions = useMemo(
    () => workflows.map((workflow) => ({ id: workflow.id, name: workflow.name })),
    [workflows]
  )

  async function retryRun(run: WorkflowRunSummary) {
    setActionId(run.id)
    setError(null)
    try {
      await workflowRunApi.retryRun(run.id, "Retried from workflow runs tab")
      await loadRuns()
      toast({
        title: "Workflow run queued",
        description: `${run.workflow_name || "Workflow"} retry created`,
      })
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Retry failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setActionId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-72 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="grid gap-2 sm:grid-cols-2">
          <Select value={workflowId} onValueChange={setWorkflowId}>
            <SelectTrigger className="w-full sm:w-64">
              <SelectValue placeholder="Workflow" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All workflows</SelectItem>
              {workflowOptions.map((workflow) => (
                <SelectItem key={workflow.id} value={workflow.id}>
                  {workflow.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={status}
            onValueChange={(value) => setStatus(value as "all" | WorkflowRunStatus)}
          >
            <SelectTrigger className="w-full sm:w-56">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={loadRuns}
          disabled={actionId !== null}
          className="w-fit"
          title="Refresh runs"
        >
          <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="rounded-md border border-danger-border bg-danger-soft p-3 text-sm text-danger-soft-foreground">
          {error}
        </div>
      ) : null}

      {runs.length === 0 ? (
        <div className="rounded-md border border-dashed bg-card p-6 text-sm text-muted-foreground">
          No workflow runs match the current filters.
        </div>
      ) : (
        <div className="rounded-md border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="min-w-64">Workflow</TableHead>
                <TableHead className="w-36">Status</TableHead>
                <TableHead className="min-w-40">Started</TableHead>
                <TableHead className="w-32 text-right">Duration</TableHead>
                <TableHead className="w-32 text-right">Cost</TableHead>
                <TableHead className="w-28 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => (
                <TableRow key={run.id}>
                  <TableCell>
                    <div className="min-w-0 space-y-1">
                      <p className="break-words text-sm font-semibold">
                        {run.workflow_name || run.workflow_id}
                      </p>
                      <p className="break-all text-xs text-muted-foreground">
                        {run.id}
                      </p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={runTone(run.status)}>
                      {labelize(run.status)}
                    </StatusBadge>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1 text-sm">
                      <p>{formatDate(run.started_at || run.queued_at)}</p>
                      <p className="text-xs text-muted-foreground">
                        {labelize(run.trigger_type)}
                      </p>
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {formatDuration(run.duration_ms)}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {formatCents(run.actual_cost_cents)}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      {run.status === "failed" ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => retryRun(run)}
                          disabled={actionId !== null}
                          title="Retry run"
                        >
                          {actionId === run.id ? (
                            <Loader2
                              className="h-4 w-4 animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <RotateCcw className="h-4 w-4" aria-hidden="true" />
                          )}
                          <span className="sr-only">Retry run</span>
                        </Button>
                      ) : null}
                      <Button
                        asChild
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        title="Open run"
                      >
                        <Link href={`/workflows/runs/${run.id}`}>
                          <ExternalLink className="h-4 w-4" aria-hidden="true" />
                          <span className="sr-only">Open run</span>
                        </Link>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}

function runTone(status: WorkflowRunStatus): StatusBadgeStatus {
  if (status === "succeeded") return "success"
  if (status === "failed" || status === "cancelled") return "danger"
  if (status === "queued" || status === "paused") return "warning"
  if (status === "running") return "info"
  return "neutral"
}

function labelize(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatDate(value?: string | null): string {
  if (!value) return "Not started"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not started"
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function formatDuration(value?: number | null): string {
  if (!value) return "-"
  if (value < 1000) return `${value} ms`
  return `${Math.round(value / 1000)} s`
}

function formatCents(value?: number | null): string {
  if (value === null || value === undefined) return "$0.00"
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
  }).format(value / 100)
}

function errorMessage(error: any): string {
  return (
    error?.details?.detail?.message ||
    error?.details?.detail ||
    error?.details?.error ||
    error?.message ||
    "Workflow request failed"
  )
}
