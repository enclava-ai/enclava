"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Activity,
  CalendarClock,
  CircleDollarSign,
  Pencil,
  ExternalLink,
  Loader2,
  Play,
  RefreshCcw,
  Search,
  TimerReset,
  Workflow,
} from "lucide-react"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
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
  WorkflowHealthState,
  WorkflowAdminMetricsResponse,
  WorkflowOperationsResponse,
  WorkflowOperationsRow,
  WorkflowRunStatus,
  workflowApi,
} from "@/lib/api-client"
import { cn } from "@/lib/utils"

type FilterKey = "all" | WorkflowHealthState

const filterOptions: Array<{ key: FilterKey; label: string }> = [
  { key: "all", label: "All" },
  { key: "running", label: "Running" },
  { key: "failed", label: "Failed" },
  { key: "missed", label: "Missed" },
  { key: "disabled", label: "Disabled" },
  { key: "no_schedule", label: "Manual" },
]

const templateSeeds = [
  {
    title: "Nightly RAG Summary",
    meta: "Schedule, RAG, agent summary",
  },
  {
    title: "Connector Intake Triage",
    meta: "Connector sync, extraction, notification",
  },
  {
    title: "Weekly Extraction Report",
    meta: "Extraction batch, budget guard, artifact",
  },
]

export function WorkflowOperationsConsole() {
  const { toast } = useToast()
  const [data, setData] = useState<WorkflowOperationsResponse | null>(null)
  const [adminMetrics, setAdminMetrics] = useState<WorkflowAdminMetricsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterKey>("all")
  const [query, setQuery] = useState("")
  const [runningId, setRunningId] = useState<string | null>(null)

  const loadOperations = useCallback(async () => {
    setError(null)
    try {
      const response = await workflowApi.getOperations()
      setData(response.operations)
      try {
        const metricsResponse = await workflowApi.getAdminMetrics()
        setAdminMetrics(metricsResponse.metrics)
      } catch {
        setAdminMetrics(null)
      }
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOperations()
  }, [loadOperations])

  const rows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return (data?.workflows || []).filter((row) => {
      const matchesFilter = filter === "all" || row.health === filter
      const haystack = [
        row.name,
        row.description,
        row.owner_label,
        row.status,
        row.health,
        row.trigger_type,
        ...(row.tags || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
      const matchesQuery =
        normalizedQuery.length === 0 || haystack.includes(normalizedQuery)
      return matchesFilter && matchesQuery
    })
  }, [data?.workflows, filter, query])

  async function runNow(row: WorkflowOperationsRow) {
    setRunningId(row.id)
    setError(null)
    try {
      const response = await workflowApi.runNow(row.id)
      await loadOperations()
      toast({
        title: "Workflow run started",
        description: `${row.name} created run ${shortId(response.run.id)}`,
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
      setRunningId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const totals = data?.totals || {
    total: 0,
    active: 0,
    disabled: 0,
    running: 0,
    failed: 0,
    missed: 0,
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <h1 className="break-words text-2xl font-semibold tracking-normal">
            Workflows
          </h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>{totals.total} total</span>
            <span>{totals.active} active</span>
            <span>{totals.running} running</span>
            <span>{totals.failed + totals.missed} need attention</span>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={loadOperations}
          disabled={runningId !== null}
          title="Refresh workflows"
          className="w-fit"
        >
          <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="Active"
          value={totals.active}
          icon={Activity}
          tone={totals.active > 0 ? "success" : "neutral"}
        />
        <MetricCard
          label="Running"
          value={totals.running}
          icon={Workflow}
          tone={totals.running > 0 ? "info" : "neutral"}
        />
        <MetricCard
          label="Failed"
          value={totals.failed}
          icon={TimerReset}
          tone={totals.failed > 0 ? "danger" : "neutral"}
        />
        <MetricCard
          label="Missed"
          value={totals.missed}
          icon={CalendarClock}
          tone={totals.missed > 0 ? "warning" : "neutral"}
        />
        <MetricCard
          label="Disabled"
          value={totals.disabled}
          icon={CircleDollarSign}
          tone="neutral"
        />
      </section>

      {adminMetrics ? <OperationalMetricsStrip metrics={adminMetrics} /> : null}

      <section className="space-y-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex max-w-full gap-1 overflow-x-auto rounded-md border bg-card p-1">
            {filterOptions.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setFilter(option.key)}
                className={cn(
                  "h-8 shrink-0 rounded-sm px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                  filter === option.key && "bg-accent-soft text-primary"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="relative w-full lg:max-w-xs">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter workflows"
              className="pl-9"
            />
          </div>
        </div>

        {error ? (
          <div className="rounded-md border border-danger-border bg-danger-soft p-3 text-sm text-danger-soft-foreground">
            {error}
          </div>
        ) : null}

        {data?.workflows.length === 0 ? (
          <EmptyState
            icon={Workflow}
            title="No workflows"
            description="Scheduled summaries, connector intake, and extraction reports will appear here."
            className="bg-card"
            action={
              <div className="grid w-full max-w-3xl gap-3 text-left sm:grid-cols-3">
                {templateSeeds.map((seed) => (
                  <div
                    key={seed.title}
                    className="min-h-24 rounded-md border bg-background p-3"
                  >
                    <p className="text-sm font-semibold text-foreground">
                      {seed.title}
                    </p>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                      {seed.meta}
                    </p>
                  </div>
                ))}
              </div>
            }
          />
        ) : (
          <WorkflowTable
            rows={rows}
            runningId={runningId}
            onRunNow={runNow}
          />
        )}
      </section>
    </div>
  )
}

function MetricCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string
  value: number
  icon: typeof Activity
  tone: StatusBadgeStatus
}) {
  return (
    <Card className="rounded-md">
      <CardContent className="flex items-center justify-between gap-3 p-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-2xl font-semibold leading-none">{value}</p>
        </div>
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-md border",
            tone === "success" && "border-success-border bg-success-soft",
            tone === "info" && "border-info-border bg-info-soft",
            tone === "warning" && "border-warning-border bg-warning-soft",
            tone === "danger" && "border-danger-border bg-danger-soft",
            tone === "neutral" && "border-border bg-muted"
          )}
        >
          <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        </span>
      </CardContent>
    </Card>
  )
}

function OperationalMetricsStrip({
  metrics,
}: {
  metrics: WorkflowAdminMetricsResponse
}) {
  const topWorkflow = metrics.top_workflows_by_cost[0]
  return (
    <section className="grid gap-3 rounded-md border bg-card p-3 md:grid-cols-5">
      <OperationalMetric
        label="Scheduler Lag"
        value={formatSeconds(metrics.scheduler_lag_seconds)}
        detail={`${metrics.queued_runs} queued`}
        tone={metrics.scheduler_lag_seconds > 300 ? "warning" : "neutral"}
        icon={CalendarClock}
      />
      <OperationalMetric
        label="Stale Locks"
        value={metrics.stale_lock_count}
        detail="expired running locks"
        tone={metrics.stale_lock_count > 0 ? "danger" : "neutral"}
        icon={TimerReset}
      />
      <OperationalMetric
        label="Long Running"
        value={metrics.long_running_count}
        detail={`${metrics.running_runs} running`}
        tone={metrics.long_running_count > 0 ? "warning" : "neutral"}
        icon={Workflow}
      />
      <OperationalMetric
        label="Failure Rate"
        value={formatPercent(metrics.failure_rate_24h)}
        detail={`${metrics.failed_runs_24h}/${metrics.total_runs_24h} in 24h`}
        tone={metrics.failure_rate_24h > 0 ? "danger" : "neutral"}
        icon={Activity}
      />
      <OperationalMetric
        label="Top Cost"
        value={topWorkflow ? formatCents(topWorkflow.actual_cost_cents) : "$0.00"}
        detail={topWorkflow?.workflow_name || "No workflow cost"}
        tone={topWorkflow && topWorkflow.actual_cost_cents > 0 ? "info" : "neutral"}
        icon={CircleDollarSign}
      />
    </section>
  )
}

function OperationalMetric({
  label,
  value,
  detail,
  tone,
  icon: Icon,
}: {
  label: string
  value: string | number
  detail: string
  tone: StatusBadgeStatus
  icon: typeof Activity
}) {
  return (
    <div className="flex min-h-20 items-center gap-3 rounded-sm bg-background p-3">
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-md border",
          tone === "info" && "border-info-border bg-info-soft",
          tone === "warning" && "border-warning-border bg-warning-soft",
          tone === "danger" && "border-danger-border bg-danger-soft",
          tone === "success" && "border-success-border bg-success-soft",
          tone === "neutral" && "border-border bg-muted"
        )}
      >
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase text-muted-foreground">
          {label}
        </p>
        <p className="mt-1 truncate text-lg font-semibold leading-tight">
          {value}
        </p>
        <p className="mt-1 truncate text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  )
}

function WorkflowTable({
  rows,
  runningId,
  onRunNow,
}: {
  rows: WorkflowOperationsRow[]
  runningId: string | null
  onRunNow: (row: WorkflowOperationsRow) => void
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed bg-card p-6 text-sm text-muted-foreground">
        No workflows match the current filters.
      </div>
    )
  }

  return (
    <div className="rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-72">Workflow</TableHead>
            <TableHead className="w-36">Health</TableHead>
            <TableHead className="min-w-44">Next Run</TableHead>
            <TableHead className="min-w-44">Latest Run</TableHead>
            <TableHead className="w-32 text-right">Failures</TableHead>
            <TableHead className="w-32 text-right">Cost</TableHead>
            <TableHead className="w-28 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words text-sm font-semibold text-foreground">
                      {row.name}
                    </p>
                    <StatusBadge status={statusTone(row.status)} showIcon={false}>
                      {labelize(row.status)}
                    </StatusBadge>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>{row.owner_label || "Unassigned"}</span>
                    <span>v{row.latest_version_number || "draft"}</span>
                    {row.tags.slice(0, 3).map((tag) => (
                      <span key={tag} className="rounded-sm bg-muted px-1.5 py-0.5">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <StatusBadge status={healthTone(row.health)}>
                  {healthLabel(row.health)}
                </StatusBadge>
              </TableCell>
              <TableCell>
                <div className="space-y-1 text-sm">
                  <p>{formatDate(row.next_run_at)}</p>
                  <p className="text-xs text-muted-foreground">
                    {triggerLabel(row)}
                  </p>
                </div>
              </TableCell>
              <TableCell>
                {row.latest_run ? (
                  <div className="space-y-1">
                    <StatusBadge status={runTone(row.latest_run.status)}>
                      {labelize(row.latest_run.status)}
                    </StatusBadge>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(row.latest_run.created_at)}
                    </p>
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">No runs</span>
                )}
              </TableCell>
              <TableCell className="text-right">
                <div className="text-sm font-medium">{row.failure_count}</div>
                <div className="text-xs text-muted-foreground">
                  {row.run_count} runs
                </div>
              </TableCell>
              <TableCell className="text-right">
                <div className="text-sm font-medium">
                  {formatCents(row.actual_cost_cents)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {row.budget_limit_cents ? formatCents(row.budget_limit_cents) : "No cap"}
                </div>
              </TableCell>
              <TableCell>
                <div className="flex justify-end gap-1">
                  <Button
                    asChild
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    title="Edit workflow"
                  >
                    <Link href={`/workflows/${row.id}/edit`}>
                      <Pencil className="h-4 w-4" aria-hidden="true" />
                      <span className="sr-only">Edit workflow</span>
                    </Link>
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onRunNow(row)}
                    disabled={
                      runningId !== null || row.status !== "active" || !row.is_active
                    }
                    title="Run workflow now"
                  >
                    {runningId === row.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Play className="h-4 w-4" aria-hidden="true" />
                    )}
                    <span className="sr-only">Run workflow now</span>
                  </Button>
                  {row.latest_run ? (
                    <Button
                      asChild
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Open latest run"
                    >
                      <Link href={`/workflows/runs/${row.latest_run.id}`}>
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open latest run</span>
                      </Link>
                    </Button>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function healthTone(health: WorkflowHealthState): StatusBadgeStatus {
  if (health === "healthy") return "success"
  if (health === "running") return "info"
  if (health === "failed") return "danger"
  if (health === "missed") return "warning"
  return "neutral"
}

function runTone(status: WorkflowRunStatus): StatusBadgeStatus {
  if (status === "succeeded") return "success"
  if (status === "failed" || status === "cancelled") return "danger"
  if (status === "queued" || status === "paused") return "warning"
  if (status === "running") return "info"
  return "neutral"
}

function statusTone(status: string): StatusBadgeStatus {
  if (status === "active") return "success"
  if (status === "draft") return "warning"
  if (status === "disabled") return "neutral"
  return "neutral"
}

function healthLabel(health: WorkflowHealthState): string {
  if (health === "no_schedule") return "Manual"
  return labelize(health)
}

function triggerLabel(row: WorkflowOperationsRow): string {
  if (row.trigger_type === "schedule" && row.cron_expression) {
    return `${row.cron_expression} ${row.timezone || "UTC"}`
  }
  if (row.trigger_type === "manual") {
    return "Manual"
  }
  return labelize(row.trigger_type)
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

function formatCents(value?: number | null): string {
  if (value === null || value === undefined) return "$0.00"
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
  }).format(value / 100)
}

function formatPercent(value: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value)
}

function formatSeconds(value: number): string {
  if (value < 60) return `${value}s`
  const minutes = Math.floor(value / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  return remainder > 0 ? `${hours}h ${remainder}m` : `${hours}h`
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
