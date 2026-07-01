"use client"

import * as React from "react"
import Link from "next/link"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: LucideIcon
  title: string
  description: string
  action?: React.ReactNode
  docsHref?: string
  docsLabel?: string
}

function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  docsHref,
  docsLabel = "Learn more",
  className,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className
      )}
      {...props}
    >
      {Icon ? (
        <Icon className="mb-3 h-8 w-8 text-muted-foreground" aria-hidden="true" />
      ) : null}
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        {description}
      </p>
      {action || docsHref ? (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {action}
          {docsHref ? (
            <Button variant="ghost" asChild>
              <Link href={docsHref}>{docsLabel}</Link>
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

export { EmptyState }
