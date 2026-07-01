"use client"

import * as React from "react"
import { AlertTriangle, CheckCircle2, Circle, Info, XCircle } from "lucide-react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const statusBadgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold leading-5",
  {
    variants: {
      status: {
        success: "border-success-border bg-success-soft text-success-soft-foreground",
        warning: "border-warning-border bg-warning-soft text-warning-soft-foreground",
        danger: "border-danger-border bg-danger-soft text-danger-soft-foreground",
        info: "border-info-border bg-info-soft text-info-soft-foreground",
        neutral: "border-border bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      status: "neutral",
    },
  }
)

const statusIcons = {
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  info: Info,
  neutral: Circle,
} as const

export type StatusBadgeStatus = keyof typeof statusIcons

const statusAliases: Record<string, StatusBadgeStatus> = {
  active: "success",
  completed: "success",
  create: "success",
  healthy: "success",
  ok: "success",
  online: "success",
  restore: "success",
  running: "success",
  success: "success",
  synced: "success",
  degraded: "warning",
  pending: "warning",
  standby: "warning",
  warning: "warning",
  delete: "danger",
  error: "danger",
  exceeded: "danger",
  failed: "danger",
  revoked: "danger",
  update: "info",
  info: "info",
  sync: "info",
  disabled: "neutral",
  inactive: "neutral",
  neutral: "neutral",
}

export function statusForValue(value?: string | null): StatusBadgeStatus {
  if (!value) return "neutral"
  return statusAliases[value.toLowerCase()] ?? "neutral"
}

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadgeVariants> {
  showIcon?: boolean
}

function StatusBadge({
  status = "neutral",
  showIcon = true,
  className,
  children,
  ...props
}: StatusBadgeProps) {
  const resolvedStatus = status ?? "neutral"
  const Icon = statusIcons[resolvedStatus]

  return (
    <span
      className={cn(statusBadgeVariants({ status: resolvedStatus }), className)}
      {...props}
    >
      {showIcon ? <Icon className="h-3 w-3 shrink-0" aria-hidden="true" /> : null}
      <span>{children}</span>
    </span>
  )
}

export { StatusBadge, statusBadgeVariants }
