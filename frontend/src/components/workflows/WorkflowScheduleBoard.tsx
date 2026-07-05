"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import {
  CalendarClock,
  ExternalLink,
  Loader2,
  PauseCircle,
  Play,
  RefreshCcw,
} from "lucide-react"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge, type StatusBadgeStatus } from "@/components/ui/status-badge"
import { useConfirm } from "@/components/ui/confirm-dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  WorkflowHealthState,
  WorkflowScheduleBoardResponse,
  WorkflowSchedulePreviewItem,
  workflowApi,
} from "@/lib/api-client"

export function WorkflowScheduleBoard() {
  const { toast } = useToast()
  const requestConfirmation = useConfirm()
  const [board, setBoard] = useState<WorkflowScheduleBoardResponse | null>(null)
  const [previewByWorkflow, setPreviewByWorkflow] = useState<
    Record<string, WorkflowSchedulePreviewItem[]>
  >({})
  const [isLoading, setIsLoading] = useState(true)
  const [actionId, setActionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadBoard = useCallback(async () => {
    setError(null)
    try {
      const response = await workflowApi.getScheduleBoard()
      setBoard(response.schedule_board)
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBoard()
  }, [loadBoard])

  async function toggleSchedule(workflowId: string, name: string, enabled: boolean) {
    const confirmed = await requestConfirmation({
      title: enabled ? "Disable workflow" : "Enable workflow",
      description: enabled
        ? `Disable scheduled runs for ${name}.`
        : `Enable scheduled runs for ${name}.`,
      confirmText: enabled ? "Disable" : "Enable",
      destructive: enabled,
    })
    if (!confirmed) return

    setActionId(workflowId)
    setError(null)
    try {
      if (enabled) {
        await workflowApi.disableWorkflow(workflowId, "Disabled from schedule board")
      } else {
        await workflowApi.enableWorkflow(workflowId, "Enabled from schedule board")
      }
      await loadBoard()
      toast({
        title: enabled ? "Workflow disabled" : "Workflow enabled",
        description: name,
      })
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Schedule update failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setActionId(null)
    }
  }

  async function previewSchedule(workflowId: string) {
    setActionId(workflowId)
    setError(null)
    try {
      const response = await workflowApi.previewSchedule(workflowId, 5)
      setPreviewByWorkflow((current) => ({
        ...current,
        [workflowId]: response.preview.next_runs,
      }))
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Preview failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setActionId(null)
    }
  }

  async function runNow(workflowId: string, name: string) {
    setActionId(workflowId)
    setError(null)
    try {
      const response = await workflowApi.runNow(workflowId)
      await loadBoard()
      toast({
        title: "Workflow run started",
        description: `${name} created run ${shortId(response.run.id)}`,
      })
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Workflow run failed",
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

  const schedules = board?.schedules || []

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(board?.groups || []).map((group) => (
            <Card key={group.key} className="rounded-md">
              <CardContent className="p-4">
                <p className="text-xs font-medium uppercase text-muted-foreground">
                  {group.label}
                </p>
                <p className="mt-2 text-2xl font-semibold leading-none">
                  {group.runs.length}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={loadBoard}
          disabled={actionId !== null}
          className="w-fit"
          title="Refresh schedules"
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

      {schedules.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title="No schedules"
          description="Scheduled workflows will appear here after they are published."
          className="bg-card"
        />
      ) : (
        <div className="rounded-md border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="min-w-72">Workflow</TableHead>
                <TableHead className="w-36">Health</TableHead>
                <TableHead className="min-w-44">Next Run</TableHead>
                <TableHead className="min-w-64">Preview</TableHead>
                <TableHead className="w-32">Misfire</TableHead>
                <TableHead className="w-36 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {schedules.map((schedule) => {
                const preview =
                  previewByWorkflow[schedule.workflow_id] || schedule.preview
                const canRun =
                  schedule.status === "active" && schedule.trigger_enabled
                return (
                  <TableRow key={schedule.trigger_id}>
                    <TableCell>
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="break-words text-sm font-semibold">
                            {schedule.workflow_name}
                          </p>
                          <StatusBadge
                            status={schedule.trigger_enabled ? "success" : "neutral"}
                            showIcon={false}
                          >
                            {schedule.trigger_enabled ? "Enabled" : "Disabled"}
                          </StatusBadge>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span>{schedule.owner_label || "Unassigned"}</span>
                          {schedule.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="rounded-sm bg-muted px-1.5 py-0.5"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={healthTone(schedule.health)}>
                        {healthLabel(schedule.health)}
                      </StatusBadge>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1 text-sm">
                        <p>{formatDate(schedule.next_run_at)}</p>
                        <p className="text-xs text-muted-foreground">
                          {schedule.cron_expression || "No cron"}{" "}
                          {schedule.timezone || "UTC"}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {preview.slice(0, 3).map((item) => (
                          <span
                            key={`${schedule.workflow_id}-${item.run_at}`}
                            className="rounded-sm border px-2 py-1 text-xs text-muted-foreground"
                          >
                            {formatDate(item.run_at)}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {labelize(schedule.misfire_policy || "run_once")}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => previewSchedule(schedule.workflow_id)}
                          disabled={actionId !== null}
                          title="Preview schedule"
                        >
                          {actionId === schedule.workflow_id ? (
                            <Loader2
                              className="h-4 w-4 animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <CalendarClock className="h-4 w-4" aria-hidden="true" />
                          )}
                          <span className="sr-only">Preview schedule</span>
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() =>
                            toggleSchedule(
                              schedule.workflow_id,
                              schedule.workflow_name,
                              schedule.trigger_enabled
                            )
                          }
                          disabled={actionId !== null}
                          title={
                            schedule.trigger_enabled
                              ? "Disable workflow"
                              : "Enable workflow"
                          }
                        >
                          {schedule.trigger_enabled ? (
                            <PauseCircle className="h-4 w-4" aria-hidden="true" />
                          ) : (
                            <Play className="h-4 w-4" aria-hidden="true" />
                          )}
                          <span className="sr-only">
                            {schedule.trigger_enabled
                              ? "Disable workflow"
                              : "Enable workflow"}
                          </span>
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() =>
                            runNow(schedule.workflow_id, schedule.workflow_name)
                          }
                          disabled={actionId !== null || !canRun}
                          title="Run workflow now"
                        >
                          <Play className="h-4 w-4" aria-hidden="true" />
                          <span className="sr-only">Run workflow now</span>
                        </Button>
                        {schedule.latest_run ? (
                          <Button
                            asChild
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            title="Open latest run"
                          >
                            <Link href={`/workflows/runs/${schedule.latest_run.id}`}>
                              <ExternalLink
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                              <span className="sr-only">Open latest run</span>
                            </Link>
                          </Button>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}

function healthTone(health: WorkflowHealthState): StatusBadgeStatus {
  if (health === "healthy") return "success"
  if (health === "running") return "info"
  if (health === "failed") return "danger"
  if (health === "missed") return "warning"
  return "neutral"
}

function healthLabel(health: WorkflowHealthState): string {
  if (health === "no_schedule") return "Manual"
  return labelize(health)
}

function labelize(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatDate(value?: string | null): string {
  if (!value) return "Not scheduled"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not scheduled"
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function shortId(value: string): string {
  return value.length > 8 ? value.slice(0, 8) : value
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
