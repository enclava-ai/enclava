"use client"

import { useCallback, useEffect, useState } from "react"
import { FileText, Loader2, RefreshCcw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { StatusBadge } from "@/components/ui/status-badge"
import { WorkflowTemplateSummary, workflowApi } from "@/lib/api-client"

export function WorkflowTemplatesPanel() {
  const [templates, setTemplates] = useState<WorkflowTemplateSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTemplates = useCallback(async () => {
    setError(null)
    try {
      const response = await workflowApi.getTemplates()
      setTemplates(response.templates)
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTemplates()
  }, [loadTemplates])

  if (isLoading) {
    return (
      <div className="flex min-h-72 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <section className="space-y-3">
      <div className="flex justify-end">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={loadTemplates}
          className="w-fit"
          title="Refresh templates"
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

      {templates.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No templates"
          description="Workflow templates will appear here when available."
          className="bg-card"
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {templates.map((template) => (
            <article
              key={template.id}
              className="min-h-44 rounded-md border bg-card p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="break-words text-sm font-semibold">
                    {template.name}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {template.description}
                  </p>
                </div>
                <StatusBadge status="neutral" showIcon={false}>
                  {labelize(template.trigger_type)}
                </StatusBadge>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>{template.step_count} steps</span>
                {template.tags.slice(0, 3).map((tag) => (
                  <span key={tag} className="rounded-sm bg-muted px-1.5 py-0.5">
                    {tag}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function labelize(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
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
