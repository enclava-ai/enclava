"use client"

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Coins,
  FileJson,
  Loader2,
  Timer,
  XCircle,
} from "lucide-react"

import {
  WorkflowArtifactSummary,
  WorkflowEventSummary,
  WorkflowRedactedPayload,
  WorkflowRunDetail,
  WorkflowRunStatus,
  WorkflowStepRunDetail,
  WorkflowStepRunStatus,
} from "@/lib/api-client"
import { StatusBadge, StatusBadgeStatus } from "@/components/ui/status-badge"
import { cn } from "@/lib/utils"

interface WorkflowRunTimelineProps {
  run: WorkflowRunDetail
}

export function WorkflowRunTimeline({ run }: WorkflowRunTimelineProps) {
  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Duration" value={formatDuration(run.duration_ms)} icon={Timer} />
        <Metric
          label="Budget"
          value={formatCents(run.budget_limit_cents)}
          icon={Coins}
        />
        <Metric
          label="Estimated"
          value={formatCents(run.estimated_cost_cents)}
          icon={Coins}
        />
        <Metric label="Actual" value={formatCents(run.actual_cost_cents)} icon={Coins} />
      </section>

      {run.error ? (
        <section className="rounded-lg border border-danger-border bg-danger-soft p-4 text-sm text-danger-soft-foreground">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p className="break-words">{run.error}</p>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border bg-card">
        <div className="flex items-center justify-between gap-3 border-b p-4">
          <h2 className="text-base font-semibold">Steps</h2>
          <StatusBadge status={runTone(run.status)}>{run.status}</StatusBadge>
        </div>
        <div className="divide-y">
          {run.steps.length ? (
            run.steps.map((step, index) => (
              <StepRow
                key={step.id}
                step={step}
                isLast={index === run.steps.length - 1}
              />
            ))
          ) : (
            <p className="p-4 text-sm text-muted-foreground">No steps have run.</p>
          )}
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <PayloadPanel title="Input" payload={run.input_data} />
        <PayloadPanel title="Output" payload={run.output_data} />
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <EventList events={run.events} />
        <ArtifactList artifacts={run.artifacts} />
      </section>
    </div>
  )
}

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: typeof Timer
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{label}</span>
      </div>
      <p className="mt-2 break-words text-lg font-semibold">{value}</p>
    </div>
  )
}

function StepRow({
  step,
  isLast,
}: {
  step: WorkflowStepRunDetail
  isLast: boolean
}) {
  const Icon = stepIcon(step.status)
  return (
    <div className="grid grid-cols-[2rem_1fr] gap-3 p-4">
      <div className="relative flex justify-center">
        {!isLast ? (
          <span className="absolute top-7 h-[calc(100%+1rem)] border-l border-border" />
        ) : null}
        <span
          className={cn(
            "relative z-10 flex h-8 w-8 items-center justify-center rounded-md border bg-background",
            step.status === "running" ? "animate-pulse" : ""
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="min-w-0 break-words text-sm font-semibold">
            {step.step_key}
          </h3>
          <StatusBadge status={stepTone(step.status)}>{step.status}</StatusBadge>
          <span className="text-xs text-muted-foreground">Attempt {step.attempt}</span>
        </div>
        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
          <span className="break-words">{step.step_type}</span>
          <span>{formatDate(step.started_at)}</span>
          <span>{formatDuration(step.duration_ms)}</span>
        </div>
        {step.error ? (
          <p className="rounded-md border border-danger-border bg-danger-soft p-2 text-xs text-danger-soft-foreground">
            {step.error}
          </p>
        ) : null}
        {step.artifacts.length ? (
          <div className="flex flex-wrap gap-2">
            {step.artifacts.map((artifact) => (
              <span
                key={artifact.id}
                className="inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 text-xs"
              >
                <FileJson className="h-3 w-3 shrink-0" aria-hidden="true" />
                <span className="truncate">{artifact.name}</span>
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function PayloadPanel({
  title,
  payload,
}: {
  title: string
  payload: WorkflowRedactedPayload
}) {
  return (
    <section className="rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-3 border-b p-4">
        <h2 className="text-base font-semibold">{title}</h2>
        {payload.redacted ? (
          <StatusBadge status="warning" showIcon={false}>
            {payload.policy}
          </StatusBadge>
        ) : (
          <StatusBadge status="neutral" showIcon={false}>
            visible
          </StatusBadge>
        )}
      </div>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words p-4 text-xs leading-5">
        {formatPayload(payload)}
      </pre>
    </section>
  )
}

function EventList({ events }: { events: WorkflowEventSummary[] }) {
  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b p-4">
        <h2 className="text-base font-semibold">Events</h2>
      </div>
      <div className="max-h-[28rem] overflow-auto divide-y">
        {events.length ? (
          events.map((event) => (
            <EventRow key={event.id} event={event} />
          ))
        ) : (
          <p className="p-4 text-sm text-muted-foreground">No events recorded.</p>
        )}
      </div>
    </section>
  )
}

function EventRow({ event }: { event: WorkflowEventSummary }) {
  return (
    <div className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={eventTone(event.severity)} showIcon={false}>
          {event.severity}
        </StatusBadge>
        <span className="break-words text-sm font-medium">{event.message}</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span>{event.event_type}</span>
        <span>{formatDate(event.created_at)}</span>
      </div>
    </div>
  )
}

function ArtifactList({ artifacts }: { artifacts: WorkflowArtifactSummary[] }) {
  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b p-4">
        <h2 className="text-base font-semibold">Artifacts</h2>
      </div>
      <div className="max-h-[28rem] overflow-auto divide-y">
        {artifacts.length ? (
          artifacts.map((artifact) => (
            <div key={artifact.id} className="space-y-2 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <FileJson className="h-4 w-4" aria-hidden="true" />
                <span className="break-words text-sm font-medium">
                  {artifact.name}
                </span>
                <StatusBadge status="neutral" showIcon={false}>
                  {artifact.artifact_type}
                </StatusBadge>
              </div>
              <p className="text-xs text-muted-foreground">
                {formatDate(artifact.created_at)}
              </p>
              {artifact.data ? (
                <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-background p-3 text-xs leading-5">
                  {formatPayload(artifact.data)}
                </pre>
              ) : null}
            </div>
          ))
        ) : (
          <p className="p-4 text-sm text-muted-foreground">No artifacts recorded.</p>
        )}
      </div>
    </section>
  )
}

function runTone(status: WorkflowRunStatus): StatusBadgeStatus {
  if (status === "succeeded") return "success"
  if (status === "running") return "info"
  if (status === "queued" || status === "paused") return "warning"
  if (status === "failed" || status === "cancelled") return "danger"
  return "neutral"
}

function stepTone(status: WorkflowStepRunStatus): StatusBadgeStatus {
  if (status === "succeeded") return "success"
  if (status === "running") return "info"
  if (status === "pending" || status === "retrying") return "warning"
  if (status === "failed" || status === "cancelled") return "danger"
  return "neutral"
}

function eventTone(severity: string): StatusBadgeStatus {
  if (severity === "error" || severity === "critical") return "danger"
  if (severity === "warning") return "warning"
  if (severity === "info") return "info"
  return "neutral"
}

function stepIcon(status: WorkflowStepRunStatus) {
  if (status === "succeeded") return CheckCircle2
  if (status === "running") return Loader2
  if (status === "failed") return XCircle
  if (status === "cancelled") return Ban
  if (status === "skipped") return CircleDashed
  if (status === "retrying") return Clock3
  return CircleDashed
}

function formatPayload(payload: WorkflowRedactedPayload): string {
  if (payload.value === null || payload.value === undefined) {
    return payload.redacted ? "Redacted" : "No payload"
  }
  return JSON.stringify(payload.value, null, 2)
}

function formatDate(value?: string | null): string {
  if (!value) return "Not set"
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function formatDuration(value?: number | null): string {
  if (value === null || value === undefined) return "Not set"
  if (value < 1000) return `${value} ms`
  const seconds = Math.round(value / 1000)
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  return `${minutes} m ${remaining} s`
}

function formatCents(value?: number | null): string {
  if (value === null || value === undefined) return "Not set"
  return `$${(value / 100).toFixed(2)}`
}
