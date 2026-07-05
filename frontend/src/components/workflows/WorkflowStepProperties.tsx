"use client"

import type { ReactNode } from "react"
import { AlertTriangle } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { StatusBadge } from "@/components/ui/status-badge"
import { Textarea } from "@/components/ui/textarea"
import {
  WorkflowStepCatalogEntry,
  WorkflowStepDefinition,
  WorkflowValidationErrorItem,
} from "@/lib/api-client"

export interface WorkflowBuilderAgentOption {
  id: string
  name: string
}

export interface WorkflowBuilderCollectionOption {
  id: string
  name: string
}

interface WorkflowStepPropertiesProps {
  step: WorkflowStepDefinition | null
  stepIndex: number
  catalogEntry?: WorkflowStepCatalogEntry
  validationErrors: WorkflowValidationErrorItem[]
  allSteps: WorkflowStepDefinition[]
  agents: WorkflowBuilderAgentOption[]
  collections: WorkflowBuilderCollectionOption[]
  onChange: (step: WorkflowStepDefinition) => void
}

const EMPTY_SELECT_VALUE = "__unset__"

export function WorkflowStepProperties({
  step,
  stepIndex,
  catalogEntry,
  validationErrors,
  allSteps,
  agents,
  collections,
  onChange,
}: WorkflowStepPropertiesProps) {
  if (!step) {
    return (
      <section className="rounded-md border bg-card p-4">
        <h2 className="text-sm font-semibold">Properties</h2>
        <p className="mt-2 text-sm text-muted-foreground">No step selected.</p>
      </section>
    )
  }

  if (!catalogEntry || !catalogEntry.enabled) {
    return (
      <section className="rounded-md border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">Properties</h2>
          <StatusBadge status="warning">
            {!catalogEntry ? "Unknown" : "Unavailable"}
          </StatusBadge>
        </div>
        <div className="mt-4 rounded-md border border-warning-border bg-warning-soft p-3 text-sm text-warning-soft-foreground">
          <div className="flex gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>
              {catalogEntry?.disabled_reason ||
                `${step.type} is not available in the builder.`}
            </p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-md border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Properties</h2>
          <p className="text-xs text-muted-foreground">{catalogEntry.display_name}</p>
        </div>
        <StatusBadge status={validationErrors.length > 0 ? "danger" : "success"}>
          {validationErrors.length > 0 ? `${validationErrors.length} issues` : "OK"}
        </StatusBadge>
      </div>

      <div className="mt-4 space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Step key" htmlFor="workflow-step-key" error={fieldError(validationErrors, "key")}>
            <Input
              id="workflow-step-key"
              value={step.key}
              onChange={(event) => onChange({ ...step, key: event.target.value })}
            />
          </Field>
          <Field label="Name" htmlFor="workflow-step-name" error={fieldError(validationErrors, "name")}>
            <Input
              id="workflow-step-name"
              value={step.name}
              onChange={(event) => onChange({ ...step, name: event.target.value })}
            />
          </Field>
        </div>

        {step.type === "rag.query" ? (
          <RagQueryEditor
            step={step}
            collections={collections}
            errors={validationErrors}
            catalogEntry={catalogEntry}
            onChange={onChange}
          />
        ) : null}

        {step.type === "agent.run" ? (
          <AgentRunEditor
            step={step}
            agents={agents}
            errors={validationErrors}
            catalogEntry={catalogEntry}
            onChange={onChange}
          />
        ) : null}

        {step.type === "condition.no_results_skip" ? (
          <ConditionEditor
            step={step}
            stepIndex={stepIndex}
            allSteps={allSteps}
            errors={validationErrors}
            onChange={onChange}
          />
        ) : null}

        {step.type === "notify.in_app" ? (
          <NotificationEditor
            step={step}
            errors={validationErrors}
            catalogEntry={catalogEntry}
            onChange={onChange}
          />
        ) : null}

        {validationErrors.length > 0 ? (
          <div className="space-y-2 rounded-md border border-danger-border bg-danger-soft p-3">
            {validationErrors.map((error, index) => (
              <p
                key={`${error.path}-${index}`}
                className="break-words text-sm text-danger-soft-foreground"
              >
                {error.message}
              </p>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function RagQueryEditor({
  step,
  collections,
  errors,
  catalogEntry,
  onChange,
}: {
  step: WorkflowStepDefinition
  collections: WorkflowBuilderCollectionOption[]
  errors: WorkflowValidationErrorItem[]
  catalogEntry: WorkflowStepCatalogEntry
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const collectionOptions = ensureOption(
    collections,
    String(step.config.collection_id || ""),
    "Current collection"
  )

  return (
    <div className="space-y-4">
      <Field
        label="Collection"
        htmlFor="workflow-rag-collection"
        error={fieldError(errors, "collection_id")}
      >
        <Select
          value={selectValue(step.config.collection_id)}
          onValueChange={(value) =>
            updateConfig(step, "collection_id", selectOutput(value), onChange)
          }
        >
          <SelectTrigger id="workflow-rag-collection">
            <SelectValue placeholder="Select collection" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EMPTY_SELECT_VALUE}>Select collection</SelectItem>
            {collectionOptions.map((collection) => (
              <SelectItem key={collection.id} value={collection.id}>
                {collection.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Query" htmlFor="workflow-rag-query">
        <Textarea
          id="workflow-rag-query"
          value={String(step.config.query || "")}
          onChange={(event) =>
            updateConfig(step, "query", event.target.value, onChange)
          }
          rows={4}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Limit" htmlFor="workflow-rag-limit">
          <Input
            id="workflow-rag-limit"
            type="number"
            min={1}
            value={inputNumber(step.config.limit)}
            onChange={(event) =>
              updateOptionalNumberConfig(step, "limit", event.target.value, onChange)
            }
          />
        </Field>
        {catalogEntry.supports_retry ? (
          <RetryField step={step} onChange={onChange} />
        ) : null}
      </div>
    </div>
  )
}

function AgentRunEditor({
  step,
  agents,
  errors,
  catalogEntry,
  onChange,
}: {
  step: WorkflowStepDefinition
  agents: WorkflowBuilderAgentOption[]
  errors: WorkflowValidationErrorItem[]
  catalogEntry: WorkflowStepCatalogEntry
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const agentOptions = ensureOption(
    agents,
    String(step.config.agent_id || ""),
    "Current agent"
  )

  return (
    <div className="space-y-4">
      <Field label="Agent" htmlFor="workflow-agent" error={fieldError(errors, "agent_id")}>
        <Select
          value={selectValue(step.config.agent_id)}
          onValueChange={(value) =>
            updateConfig(step, "agent_id", selectOutput(value), onChange)
          }
        >
          <SelectTrigger id="workflow-agent">
            <SelectValue placeholder="Select agent" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EMPTY_SELECT_VALUE}>Select agent</SelectItem>
            {agentOptions.map((agent) => (
              <SelectItem key={agent.id} value={agent.id}>
                {agent.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field
        label="Prompt template"
        htmlFor="workflow-agent-prompt"
        error={fieldError(errors, "prompt_template")}
      >
        <Textarea
          id="workflow-agent-prompt"
          value={String(step.config.prompt_template || "")}
          onChange={(event) =>
            updateConfig(step, "prompt_template", event.target.value, onChange)
          }
          rows={5}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Max tokens" htmlFor="workflow-agent-max-tokens">
          <Input
            id="workflow-agent-max-tokens"
            type="number"
            min={1}
            value={inputNumber(step.config.max_tokens)}
            onChange={(event) =>
              updateOptionalNumberConfig(
                step,
                "max_tokens",
                event.target.value,
                onChange
              )
            }
          />
        </Field>
        {catalogEntry.supports_retry ? (
          <RetryField step={step} onChange={onChange} />
        ) : null}
      </div>
    </div>
  )
}

function ConditionEditor({
  step,
  stepIndex,
  allSteps,
  errors,
  onChange,
}: {
  step: WorkflowStepDefinition
  stepIndex: number
  allSteps: WorkflowStepDefinition[]
  errors: WorkflowValidationErrorItem[]
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const inputSteps = allSteps.slice(0, Math.max(stepIndex, 0))
  const options = ensureOption(
    inputSteps.map((item) => ({ id: item.key, name: item.name || item.key })),
    String(step.config.input_step_key || ""),
    "Current step"
  )

  return (
    <div className="space-y-4">
      <Field
        label="Input step"
        htmlFor="workflow-condition-input"
        error={fieldError(errors, "input_step_key")}
      >
        <Select
          value={selectValue(step.config.input_step_key)}
          onValueChange={(value) =>
            updateConfig(step, "input_step_key", selectOutput(value), onChange)
          }
        >
          <SelectTrigger id="workflow-condition-input">
            <SelectValue placeholder="Select step" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EMPTY_SELECT_VALUE}>Select step</SelectItem>
            {options.map((option) => (
              <SelectItem key={option.id} value={option.id}>
                {option.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Path" htmlFor="workflow-condition-path">
        <Input
          id="workflow-condition-path"
          value={String(step.config.path || "")}
          onChange={(event) =>
            updateConfig(step, "path", event.target.value, onChange)
          }
        />
      </Field>
    </div>
  )
}

function NotificationEditor({
  step,
  errors,
  catalogEntry,
  onChange,
}: {
  step: WorkflowStepDefinition
  errors: WorkflowValidationErrorItem[]
  catalogEntry: WorkflowStepCatalogEntry
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const recipients = Array.isArray(step.config.recipients)
    ? step.config.recipients.join(", ")
    : String(step.config.recipients || "")

  return (
    <div className="space-y-4">
      <Field
        label="Recipients"
        htmlFor="workflow-notify-recipients"
        error={fieldError(errors, "recipients")}
      >
        <Input
          id="workflow-notify-recipients"
          value={recipients}
          onChange={(event) =>
            updateConfig(
              step,
              "recipients",
              event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
              onChange
            )
          }
        />
      </Field>
      <Field
        label="Title template"
        htmlFor="workflow-notify-title"
        error={fieldError(errors, "title_template")}
      >
        <Input
          id="workflow-notify-title"
          value={String(step.config.title_template || "")}
          onChange={(event) =>
            updateConfig(step, "title_template", event.target.value, onChange)
          }
        />
      </Field>
      <Field label="Body template" htmlFor="workflow-notify-body">
        <Textarea
          id="workflow-notify-body"
          value={String(step.config.body_template || "")}
          onChange={(event) =>
            updateConfig(step, "body_template", event.target.value, onChange)
          }
          rows={4}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Severity" htmlFor="workflow-notify-severity">
          <Select
            value={String(step.config.severity || "info")}
            onValueChange={(value) =>
              updateConfig(step, "severity", value, onChange)
            }
          >
            <SelectTrigger id="workflow-notify-severity">
              <SelectValue placeholder="Severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warning">Warning</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        {catalogEntry.supports_retry ? (
          <RetryField step={step} onChange={onChange} />
        ) : null}
      </div>
    </div>
  )
}

function RetryField({
  step,
  onChange,
}: {
  step: WorkflowStepDefinition
  onChange: (step: WorkflowStepDefinition) => void
}) {
  return (
    <Field label="Retry attempts" htmlFor={`workflow-retry-${step.key}`}>
      <Input
        id={`workflow-retry-${step.key}`}
        type="number"
        min={1}
        max={10}
        value={step.retry?.max_attempts ?? 1}
        onChange={(event) => {
          const maxAttempts = clampNumber(event.target.value, 1, 10, 1)
          onChange({
            ...step,
            retry: {
              ...step.retry,
              max_attempts: maxAttempts,
            },
          })
        }}
      />
    </Field>
  )
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? (
        <p className="break-words text-xs text-danger-soft-foreground">{error}</p>
      ) : null}
    </div>
  )
}

function updateConfig(
  step: WorkflowStepDefinition,
  key: string,
  value: unknown,
  onChange: (step: WorkflowStepDefinition) => void
) {
  onChange({
    ...step,
    config: {
      ...step.config,
      [key]: value,
    },
  })
}

function updateOptionalNumberConfig(
  step: WorkflowStepDefinition,
  key: string,
  value: string,
  onChange: (step: WorkflowStepDefinition) => void
) {
  const nextConfig = { ...step.config }
  if (value.trim() === "") {
    delete nextConfig[key]
  } else {
    nextConfig[key] = Number(value)
  }
  onChange({ ...step, config: nextConfig })
}

function selectValue(value: unknown): string {
  const normalized = String(value || "").trim()
  return normalized || EMPTY_SELECT_VALUE
}

function selectOutput(value: string): string {
  return value === EMPTY_SELECT_VALUE ? "" : value
}

function inputNumber(value: unknown): string | number {
  if (value === null || value === undefined || value === "") return ""
  return Number(value)
}

function clampNumber(
  value: string,
  min: number,
  max: number,
  fallback: number
): number {
  const next = Number(value)
  if (!Number.isFinite(next)) return fallback
  return Math.min(max, Math.max(min, Math.trunc(next)))
}

function fieldError(
  errors: WorkflowValidationErrorItem[],
  fieldName: string
): string | undefined {
  return errors.find((error) => error.path.endsWith(`.${fieldName}`))?.message
}

function ensureOption<T extends { id: string; name: string }>(
  options: T[],
  currentValue: string,
  fallbackName: string
): T[] {
  if (!currentValue || options.some((option) => option.id === currentValue)) {
    return options
  }
  return [{ id: currentValue, name: `${fallbackName} ${currentValue}` } as T, ...options]
}
