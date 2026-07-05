"use client"

import { AlertTriangle, CheckCircle2, Info } from "lucide-react"

import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { WorkflowValidationErrorItem } from "@/lib/api-client"
import { cn } from "@/lib/utils"

interface WorkflowValidationSummaryProps {
  errors: WorkflowValidationErrorItem[]
  hasValidated: boolean
  onFocusPath?: (path: string, error: WorkflowValidationErrorItem) => void
  className?: string
}

export function WorkflowValidationSummary({
  errors,
  hasValidated,
  onFocusPath,
  className,
}: WorkflowValidationSummaryProps) {
  const blocking = errors.filter((error) => error.severity !== "warning")
  const warnings = errors.filter((error) => error.severity === "warning")

  if (!hasValidated) {
    return (
      <div className={cn("rounded-md border bg-card p-3", className)}>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Validation has not run.</span>
        </div>
      </div>
    )
  }

  if (errors.length === 0) {
    return (
      <div className={cn("rounded-md border border-success-border bg-success-soft p-3", className)}>
        <div className="flex items-center gap-2 text-sm text-success-soft-foreground">
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Ready to publish.</span>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("rounded-md border bg-card p-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning-soft-foreground" aria-hidden="true" />
        <p className="text-sm font-semibold">Validation</p>
        {blocking.length > 0 ? (
          <StatusBadge status="danger">{blocking.length} errors</StatusBadge>
        ) : null}
        {warnings.length > 0 ? (
          <StatusBadge status="warning">{warnings.length} warnings</StatusBadge>
        ) : null}
      </div>
      <div className="mt-3 space-y-2">
        {errors.map((error, index) => (
          <button
            key={`${error.path}-${index}`}
            type="button"
            onClick={() => onFocusPath?.(error.path, error)}
            className="block w-full rounded-md border bg-background p-2 text-left transition-colors hover:bg-accent"
          >
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={error.severity === "warning" ? "warning" : "danger"} showIcon={false}>
                {error.severity === "warning" ? "Warning" : "Error"}
              </StatusBadge>
              <span className="text-xs font-medium text-muted-foreground">
                {formatPath(error)}
              </span>
            </div>
            <p className="mt-1 break-words text-sm text-foreground">{error.message}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

function formatPath(error: WorkflowValidationErrorItem): string {
  if (error.step_key) return `Step "${error.step_key}"`
  if (error.path.startsWith("trigger")) return "Trigger"
  if (error.path.startsWith("runtime")) return "Runtime"
  return error.path || "Definition"
}
