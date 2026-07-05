"use client"

import { useEffect, useMemo, useState } from "react"
import {
  ArrowDown,
  ArrowUp,
  Plus,
  Repeat2,
  ShieldCheck,
  Trash2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { StatusBadge } from "@/components/ui/status-badge"
import {
  WorkflowStepCatalogEntry,
  WorkflowStepDefinition,
  WorkflowValidationErrorItem,
} from "@/lib/api-client"
import { cn } from "@/lib/utils"

interface WorkflowStepListProps {
  steps: WorkflowStepDefinition[]
  catalog: WorkflowStepCatalogEntry[]
  selectedStepKey: string
  validationErrors: WorkflowValidationErrorItem[]
  onSelectStep: (stepKey: string) => void
  onMoveStep: (stepKey: string, direction: "up" | "down") => void
  onRemoveStep: (stepKey: string) => void
  onAddStep: (stepType: string) => void
}

export function WorkflowStepList({
  steps,
  catalog,
  selectedStepKey,
  validationErrors,
  onSelectStep,
  onMoveStep,
  onRemoveStep,
  onAddStep,
}: WorkflowStepListProps) {
  const enabledCatalog = useMemo(
    () => catalog.filter((entry) => entry.enabled),
    [catalog]
  )
  const [stepType, setStepType] = useState("")

  useEffect(() => {
    if (!stepType && enabledCatalog[0]) {
      setStepType(enabledCatalog[0].type)
    }
  }, [enabledCatalog, stepType])

  const catalogByType = useMemo(() => {
    return new Map(catalog.map((entry) => [entry.type, entry]))
  }, [catalog])

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold">Steps</h2>
          <p className="text-xs text-muted-foreground">{steps.length} configured</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2">
          <Select value={stepType} onValueChange={setStepType}>
            <SelectTrigger className="w-56 max-w-full" aria-label="Step type">
              <SelectValue placeholder="Step type" />
            </SelectTrigger>
            <SelectContent>
              {enabledCatalog.map((entry) => (
                <SelectItem key={entry.type} value={entry.type}>
                  {entry.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="button"
            size="sm"
            onClick={() => onAddStep(stepType)}
            disabled={!stepType}
            title="Add step"
          >
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            Add
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        {steps.map((step, index) => {
          const entry = catalogByType.get(step.type)
          const rowErrors = validationErrors.filter(
            (error) => error.step_key === step.key || error.step_index === index
          )
          const selected = selectedStepKey === step.key

          return (
            <div
              key={`${step.key}-${index}`}
              className={cn(
                "rounded-md border bg-card p-3 transition-colors",
                selected && "border-primary bg-accent-soft"
              )}
            >
              <div className="flex gap-2">
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onSelectStep(step.key)}
                  title={`Select ${step.name}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border bg-background text-xs font-semibold">
                      {index + 1}
                    </span>
                    <p className="min-w-0 break-words text-sm font-semibold">
                      {step.name || step.key}
                    </p>
                    {entry ? (
                      <StatusBadge status={entry.enabled ? "info" : "warning"} showIcon={false}>
                        {entry.display_name}
                      </StatusBadge>
                    ) : (
                      <StatusBadge status="danger" showIcon={false}>
                        Unknown
                      </StatusBadge>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span className="break-all">{step.key}</span>
                    <span>{step.type}</span>
                    <span className="inline-flex items-center gap-1">
                      <ShieldCheck className="h-3 w-3" aria-hidden="true" />
                      {entry?.required_permissions.length || 0} permissions
                    </span>
                    {entry?.supports_retry ? (
                      <span className="inline-flex items-center gap-1">
                        <Repeat2 className="h-3 w-3" aria-hidden="true" />
                        Retry
                      </span>
                    ) : null}
                    {rowErrors.length > 0 ? (
                      <span className="font-medium text-danger-soft-foreground">
                        {rowErrors.length} validation
                      </span>
                    ) : null}
                  </div>
                </button>
                <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onMoveStep(step.key, "up")}
                    disabled={index === 0}
                    title="Move step up"
                  >
                    <ArrowUp className="h-4 w-4" aria-hidden="true" />
                    <span className="sr-only">Move step up</span>
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onMoveStep(step.key, "down")}
                    disabled={index === steps.length - 1}
                    title="Move step down"
                  >
                    <ArrowDown className="h-4 w-4" aria-hidden="true" />
                    <span className="sr-only">Move step down</span>
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onRemoveStep(step.key)}
                    disabled={steps.length <= 1}
                    title="Remove step"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    <span className="sr-only">Remove step</span>
                  </Button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
