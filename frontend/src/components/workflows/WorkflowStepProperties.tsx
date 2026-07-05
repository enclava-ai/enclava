"use client"

import type { ReactNode } from "react"
import { AlertTriangle } from "lucide-react"

import { Checkbox } from "@/components/ui/checkbox"
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

export interface WorkflowBuilderConnectorOption {
  id: string
  name: string
  connector_type?: string
  status?: string | null
}

export interface WorkflowBuilderExtractTemplateOption {
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
  connectors: WorkflowBuilderConnectorOption[]
  extractTemplates: WorkflowBuilderExtractTemplateOption[]
  onChange: (step: WorkflowStepDefinition) => void
}

const EMPTY_SELECT_VALUE = "__unset__"
const BRANCH_VALUE_OPERATORS = new Set([
  "equals",
  "not_equals",
  "contains",
  "greater_than",
  "greater_than_or_equal",
  "less_than",
  "less_than_or_equal",
])
const BRANCH_OPERATORS = [
  { value: "exists", label: "Exists" },
  { value: "empty", label: "Empty" },
  { value: "non_empty", label: "Not empty" },
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not equals" },
  { value: "contains", label: "Contains" },
  { value: "greater_than", label: "Greater than" },
  { value: "greater_than_or_equal", label: "Greater than or equal" },
  { value: "less_than", label: "Less than" },
  { value: "less_than_or_equal", label: "Less than or equal" },
  { value: "truthy", label: "Truthy" },
  { value: "falsy", label: "Falsy" },
]

export function WorkflowStepProperties({
  step,
  stepIndex,
  catalogEntry,
  validationErrors,
  allSteps,
  agents,
  collections,
  connectors,
  extractTemplates,
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

        {step.type === "connector.sync" ? (
          <ConnectorSyncEditor
            step={step}
            connectors={connectors}
            errors={validationErrors}
            catalogEntry={catalogEntry}
            onChange={onChange}
          />
        ) : null}

        {step.type === "extract.run_template" ? (
          <ExtractTemplateEditor
            step={step}
            stepIndex={stepIndex}
            allSteps={allSteps}
            collections={collections}
            connectors={connectors}
            templates={extractTemplates}
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

        {step.type === "condition.branch" ? (
          <BranchConditionEditor
            step={step}
            stepIndex={stepIndex}
            allSteps={allSteps}
            errors={validationErrors}
            onChange={onChange}
          />
        ) : null}

        {step.type === "approval.request" ? (
          <ApprovalRequestEditor
            step={step}
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

function ConnectorSyncEditor({
  step,
  connectors,
  errors,
  catalogEntry,
  onChange,
}: {
  step: WorkflowStepDefinition
  connectors: WorkflowBuilderConnectorOption[]
  errors: WorkflowValidationErrorItem[]
  catalogEntry: WorkflowStepCatalogEntry
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const connectorOptions = ensureOption(
    connectors,
    String(step.config.connector_id || ""),
    "Current connector"
  )

  return (
    <div className="space-y-4">
      <Field
        label="Connector"
        htmlFor="workflow-connector"
        error={fieldError(errors, "connector_id")}
      >
        <Select
          value={selectValue(step.config.connector_id)}
          onValueChange={(value) =>
            updateConfig(step, "connector_id", selectOutput(value), onChange)
          }
        >
          <SelectTrigger id="workflow-connector">
            <SelectValue placeholder="Select connector" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EMPTY_SELECT_VALUE}>Select connector</SelectItem>
            {connectorOptions.map((connector) => (
              <SelectItem key={connector.id} value={connector.id}>
                {connector.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Since" htmlFor="workflow-connector-since">
          <Select
            value={String(step.config.since || "connector_checkpoint")}
            onValueChange={(value) =>
              updateConfig(step, "since", value, onChange)
            }
          >
            <SelectTrigger id="workflow-connector-since">
              <SelectValue placeholder="Since" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="connector_checkpoint">Connector checkpoint</SelectItem>
              <SelectItem value="last_successful_run">
                Last successful run
              </SelectItem>
              <SelectItem value="full_sync">Full sync</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Max records" htmlFor="workflow-connector-max-records">
          <Input
            id="workflow-connector-max-records"
            type="number"
            min={1}
            max={100}
            value={inputNumber(step.config.max_records ?? 50)}
            onChange={(event) =>
              updateOptionalNumberConfig(
                step,
                "max_records",
                event.target.value,
                onChange
              )
            }
          />
        </Field>
      </div>
      {catalogEntry.supports_retry ? (
        <RetryField step={step} onChange={onChange} />
      ) : null}
    </div>
  )
}

function ExtractTemplateEditor({
  step,
  stepIndex,
  allSteps,
  collections,
  connectors,
  templates,
  errors,
  catalogEntry,
  onChange,
}: {
  step: WorkflowStepDefinition
  stepIndex: number
  allSteps: WorkflowStepDefinition[]
  collections: WorkflowBuilderCollectionOption[]
  connectors: WorkflowBuilderConnectorOption[]
  templates: WorkflowBuilderExtractTemplateOption[]
  errors: WorkflowValidationErrorItem[]
  catalogEntry: WorkflowStepCatalogEntry
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const templateOptions = ensureOption(
    templates,
    String(step.config.template_id || ""),
    "Current template"
  )
  const collectionOptions = ensureOption(
    collections,
    String(step.config.collection_id || ""),
    "Current collection"
  )
  const connectorOptions = ensureOption(
    connectors,
    String(step.config.connector_id || ""),
    "Current connector"
  )
  const previousStepOptions = ensureOption(
    allSteps
      .slice(0, Math.max(stepIndex, 0))
      .map((item) => ({ id: item.key, name: item.name || item.key })),
    String(step.config.input_step_key || ""),
    "Current step"
  )
  const source = String(step.config.document_source || "previous_step")

  return (
    <div className="space-y-4">
      <Field
        label="Template"
        htmlFor="workflow-extract-template"
        error={fieldError(errors, "template_id")}
      >
        <Select
          value={selectValue(step.config.template_id)}
          onValueChange={(value) =>
            updateConfig(step, "template_id", selectOutput(value), onChange)
          }
        >
          <SelectTrigger id="workflow-extract-template">
            <SelectValue placeholder="Select template" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EMPTY_SELECT_VALUE}>Select template</SelectItem>
            {templateOptions.map((template) => (
              <SelectItem key={template.id} value={template.id}>
                {template.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="Documents" htmlFor="workflow-extract-source">
        <Select
          value={source}
          onValueChange={(value) =>
            onChange({
              ...step,
              config: normalizeExtractSourceConfig(
                step.config,
                value,
                allSteps.slice(0, Math.max(stepIndex, 0))
              ),
            })
          }
        >
          <SelectTrigger id="workflow-extract-source">
            <SelectValue placeholder="Document source" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="previous_step">Previous step</SelectItem>
            <SelectItem value="rag_filter">RAG collection</SelectItem>
          </SelectContent>
        </Select>
      </Field>

      {source === "previous_step" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label="Input step"
            htmlFor="workflow-extract-input-step"
            error={fieldError(errors, "input_step_key")}
          >
            <Select
              value={selectValue(step.config.input_step_key)}
              onValueChange={(value) =>
                updateConfig(step, "input_step_key", selectOutput(value), onChange)
              }
            >
              <SelectTrigger id="workflow-extract-input-step">
                <SelectValue placeholder="Select step" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={EMPTY_SELECT_VALUE}>Select step</SelectItem>
                {previousStepOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Path" htmlFor="workflow-extract-path">
            <Input
              id="workflow-extract-path"
              value={String(step.config.path || "items")}
              onChange={(event) =>
                updateConfig(step, "path", event.target.value, onChange)
              }
            />
          </Field>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label="Collection"
            htmlFor="workflow-extract-collection"
            error={fieldError(errors, "collection_id")}
          >
            <Select
              value={selectValue(step.config.collection_id)}
              onValueChange={(value) =>
                updateConfig(step, "collection_id", selectOutput(value), onChange)
              }
            >
              <SelectTrigger id="workflow-extract-collection">
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
          <Field label="Connector" htmlFor="workflow-extract-connector">
            <Select
              value={selectValue(step.config.connector_id)}
              onValueChange={(value) =>
                updateConfig(step, "connector_id", selectOutput(value), onChange)
              }
            >
              <SelectTrigger id="workflow-extract-connector">
                <SelectValue placeholder="Any connector" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={EMPTY_SELECT_VALUE}>Any connector</SelectItem>
                {connectorOptions.map((connector) => (
                  <SelectItem key={connector.id} value={connector.id}>
                    {connector.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Since" htmlFor="workflow-extract-since">
          <Select
            value={String(step.config.since || "last_successful_run")}
            onValueChange={(value) => updateConfig(step, "since", value, onChange)}
          >
            <SelectTrigger id="workflow-extract-since">
              <SelectValue placeholder="Since" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="last_successful_run">
                Last successful run
              </SelectItem>
              <SelectItem value="all_matching">All matching</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Max documents" htmlFor="workflow-extract-max-documents">
          <Input
            id="workflow-extract-max-documents"
            type="number"
            min={1}
            max={100}
            value={inputNumber(step.config.max_documents ?? 25)}
            onChange={(event) =>
              updateOptionalNumberConfig(
                step,
                "max_documents",
                event.target.value,
                onChange
              )
            }
          />
        </Field>
      </div>

      <Field
        label="Context JSON"
        htmlFor="workflow-extract-context"
        error={fieldError(errors, "context")}
      >
        <Textarea
          id="workflow-extract-context"
          value={formatContextValue(step.config.context)}
          onChange={(event) =>
            updateConfig(step, "context", event.target.value, onChange)
          }
          rows={4}
        />
      </Field>

      {catalogEntry.supports_retry ? (
        <RetryField step={step} onChange={onChange} />
      ) : null}
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

function BranchConditionEditor({
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
  const previousSteps = allSteps.slice(0, Math.max(stepIndex, 0))
  const laterSteps = allSteps.slice(Math.max(stepIndex + 1, 0))
  const sourceOptions = ensureOption(
    previousSteps.map((item) => ({ id: item.key, name: item.name || item.key })),
    String(step.config.input_step_key || ""),
    "Current step"
  )
  const targetOptions = laterSteps.map((item) => ({
    id: item.key,
    name: item.name || item.key,
  }))
  const allowedTargetKeys = targetOptions.map((item) => item.id)
  const operator = String(step.config.operator || "exists")
  const operatorUsesValue = BRANCH_VALUE_OPERATORS.has(operator)

  function updateOperator(value: string) {
    const nextConfig = { ...step.config, operator: value }
    if (!BRANCH_VALUE_OPERATORS.has(value)) {
      delete nextConfig.value
    } else if (nextConfig.value === undefined) {
      nextConfig.value = ""
    }
    onChange({ ...step, config: nextConfig })
  }

  function toggleTarget(
    field: "matched_skip_step_keys" | "not_matched_skip_step_keys",
    targetKey: string,
    checked: boolean
  ) {
    onChange({
      ...step,
      config: toggleBranchTarget(
        step.config,
        field,
        targetKey,
        checked,
        allowedTargetKeys
      ),
    })
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Input step"
          htmlFor="workflow-branch-input"
          error={fieldError(errors, "input_step_key")}
        >
          <Select
            value={selectValue(step.config.input_step_key)}
            onValueChange={(value) =>
              updateConfig(step, "input_step_key", selectOutput(value), onChange)
            }
          >
            <SelectTrigger id="workflow-branch-input">
              <SelectValue placeholder="Select step" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={EMPTY_SELECT_VALUE}>Select step</SelectItem>
              {sourceOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Path" htmlFor="workflow-branch-path">
          <Input
            id="workflow-branch-path"
            value={String(step.config.path || "")}
            onChange={(event) =>
              updateConfig(step, "path", event.target.value, onChange)
            }
          />
        </Field>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Operator"
          htmlFor="workflow-branch-operator"
          error={fieldError(errors, "operator")}
        >
          <Select value={operator} onValueChange={updateOperator}>
            <SelectTrigger id="workflow-branch-operator">
              <SelectValue placeholder="Operator" />
            </SelectTrigger>
            <SelectContent>
              {BRANCH_OPERATORS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        {operatorUsesValue ? (
          <Field
            label="Value"
            htmlFor="workflow-branch-value"
            error={fieldError(errors, "value")}
          >
            <Input
              id="workflow-branch-value"
              value={String(step.config.value ?? "")}
              onChange={(event) =>
                updateConfig(step, "value", event.target.value, onChange)
              }
            />
          </Field>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="When matched" htmlFor="workflow-branch-matched-label">
          <Input
            id="workflow-branch-matched-label"
            value={String(step.config.matched_label || "Matched")}
            onChange={(event) =>
              updateConfig(step, "matched_label", event.target.value, onChange)
            }
          />
        </Field>
        <Field label="When not matched" htmlFor="workflow-branch-not-matched-label">
          <Input
            id="workflow-branch-not-matched-label"
            value={String(step.config.not_matched_label || "Not matched")}
            onChange={(event) =>
              updateConfig(step, "not_matched_label", event.target.value, onChange)
            }
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <BranchTargetList
          idPrefix="workflow-branch-matched-target"
          label="Skip steps"
          pathLabel="When matched"
          options={targetOptions}
          selected={normalizeBranchTargets(
            step.config.matched_skip_step_keys,
            allowedTargetKeys
          )}
          error={fieldError(errors, "matched_skip_step_keys")}
          onToggle={(targetKey, checked) =>
            toggleTarget("matched_skip_step_keys", targetKey, checked)
          }
        />
        <BranchTargetList
          idPrefix="workflow-branch-not-matched-target"
          label="Skip steps"
          pathLabel="When not matched"
          options={targetOptions}
          selected={normalizeBranchTargets(
            step.config.not_matched_skip_step_keys,
            allowedTargetKeys
          )}
          error={fieldError(errors, "not_matched_skip_step_keys")}
          onToggle={(targetKey, checked) =>
            toggleTarget("not_matched_skip_step_keys", targetKey, checked)
          }
        />
      </div>
    </div>
  )
}

function BranchTargetList({
  idPrefix,
  label,
  pathLabel,
  options,
  selected,
  error,
  onToggle,
}: {
  idPrefix: string
  label: string
  pathLabel: string
  options: { id: string; name: string }[]
  selected: string[]
  error?: string
  onToggle: (targetKey: string, checked: boolean) => void
}) {
  return (
    <div className="space-y-2">
      <div>
        <Label>{label}</Label>
        <p className="text-xs text-muted-foreground">{pathLabel}</p>
      </div>
      {options.length ? (
        <div className="space-y-2">
          {options.map((option) => {
            const inputId = `${idPrefix}-${option.id}`
            return (
              <div key={option.id} className="flex items-center gap-2">
                <Checkbox
                  id={inputId}
                  checked={selected.includes(option.id)}
                  onCheckedChange={(checked) =>
                    onToggle(option.id, checked === true)
                  }
                />
                <Label
                  htmlFor={inputId}
                  className="min-w-0 break-words text-sm font-normal"
                >
                  {option.name}
                </Label>
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No later steps available</p>
      )}
      {error ? (
        <p className="break-words text-xs text-danger-soft-foreground">{error}</p>
      ) : null}
    </div>
  )
}

function ApprovalRequestEditor({
  step,
  errors,
  onChange,
}: {
  step: WorkflowStepDefinition
  errors: WorkflowValidationErrorItem[]
  onChange: (step: WorkflowStepDefinition) => void
}) {
  const approverUserIds = formatApproverUserIds(step.config.approver_user_ids)

  return (
    <div className="space-y-4">
      <Field
        label="Title"
        htmlFor="workflow-approval-title"
        error={fieldError(errors, "title_template")}
      >
        <Input
          id="workflow-approval-title"
          value={String(step.config.title_template || "")}
          onChange={(event) =>
            updateConfig(step, "title_template", event.target.value, onChange)
          }
        />
      </Field>

      <Field label="Body" htmlFor="workflow-approval-body">
        <Textarea
          id="workflow-approval-body"
          value={String(step.config.body_template || "")}
          onChange={(event) =>
            updateConfig(step, "body_template", event.target.value, onChange)
          }
          rows={4}
        />
      </Field>

      <Field
        label="Approver user ids"
        htmlFor="workflow-approval-approvers"
        error={fieldError(errors, "approver_user_ids")}
      >
        <Input
          id="workflow-approval-approvers"
          value={approverUserIds}
          onChange={(event) =>
            updateConfig(
              step,
              "approver_user_ids",
              parseApproverUserIds(event.target.value),
              onChange
            )
          }
        />
      </Field>

      <div className="flex items-center gap-2">
        <Checkbox
          id="workflow-approval-self"
          checked={Boolean(step.config.allow_requester_approval)}
          onCheckedChange={(checked) =>
            updateConfig(
              step,
              "allow_requester_approval",
              checked === true,
              onChange
            )
          }
        />
        <Label htmlFor="workflow-approval-self" className="text-sm font-normal">
          Allow requester approval
        </Label>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Approve label" htmlFor="workflow-approval-approve-label">
          <Input
            id="workflow-approval-approve-label"
            value={String(step.config.approved_label || "Approve")}
            onChange={(event) =>
              updateConfig(step, "approved_label", event.target.value, onChange)
            }
          />
        </Field>
        <Field label="Reject label" htmlFor="workflow-approval-reject-label">
          <Input
            id="workflow-approval-reject-label"
            value={String(step.config.rejected_label || "Reject")}
            onChange={(event) =>
              updateConfig(step, "rejected_label", event.target.value, onChange)
            }
          />
        </Field>
      </div>
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

function normalizeExtractSourceConfig(
  config: Record<string, any>,
  source: string,
  allSteps: WorkflowStepDefinition[]
): Record<string, any> {
  if (source === "previous_step") {
    const next = { ...config }
    delete next.collection_id
    delete next.connector_id
    return {
      ...next,
      document_source: "previous_step",
      input_step_key:
        String(config.input_step_key || "") ||
        allSteps[allSteps.length - 1]?.key ||
        "",
      path: String(config.path || "items"),
    }
  }

  const next = { ...config }
  delete next.input_step_key
  delete next.path
  return {
    ...next,
    document_source: "rag_filter",
    collection_id: String(config.collection_id || ""),
    since: String(config.since || "last_successful_run"),
  }
}

function normalizeBranchTargets(value: unknown, allowedStepKeys: string[]): string[] {
  if (!Array.isArray(value)) return []
  const allowed = new Set(allowedStepKeys)
  return value.filter(
    (item): item is string => typeof item === "string" && allowed.has(item)
  )
}

function toggleBranchTarget(
  config: Record<string, any>,
  field: "matched_skip_step_keys" | "not_matched_skip_step_keys",
  targetKey: string,
  checked: boolean,
  allowedStepKeys: string[]
): Record<string, any> {
  const current = normalizeBranchTargets(config[field], allowedStepKeys)
  const next = new Set(current)
  if (checked) {
    next.add(targetKey)
  } else {
    next.delete(targetKey)
  }
  return {
    ...config,
    [field]: allowedStepKeys.filter((item) => next.has(item)),
  }
}

function formatApproverUserIds(value: unknown): string {
  if (!Array.isArray(value)) return ""
  return value
    .map((item) => String(item).trim())
    .filter(Boolean)
    .join(", ")
}

function parseApproverUserIds(value: string): Array<number | string> {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const parsed = Number(item)
      return Number.isFinite(parsed) && parsed > 0 ? parsed : item
    })
}

function formatContextValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return ""
  if (typeof value === "string") return value
  return JSON.stringify(value, null, 2)
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
  const suffix = `.${fieldName}`
  return errors.find(
    (error) =>
      error.path.endsWith(suffix) || error.path.includes(`${suffix}[`)
  )?.message
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
