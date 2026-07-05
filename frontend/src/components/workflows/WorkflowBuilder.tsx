"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Play,
  Rocket,
  Save,
  Send,
} from "lucide-react"

import { useToast } from "@/hooks/use-toast"
import { agentApi, ragApi, workflowApi } from "@/lib/api-client"
import type {
  WorkflowConcurrencyPolicy,
  WorkflowDefinitionDetail,
  WorkflowDefinitionDocument,
  WorkflowDefinitionStatus,
  WorkflowMisfirePolicy,
  WorkflowRedactionPolicy,
  WorkflowRuntimePolicy,
  WorkflowSchedulePreviewItem,
  WorkflowStepCatalogEntry,
  WorkflowStepDefinition,
  WorkflowTemplate,
  WorkflowTriggerDefinition,
  WorkflowTriggerType,
  WorkflowValidationErrorItem,
  WorkflowValidationResponse,
} from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { StatusBadge, type StatusBadgeStatus } from "@/components/ui/status-badge"
import { Textarea } from "@/components/ui/textarea"
import { useConfirm } from "@/components/ui/confirm-dialog"
import { WorkflowStepList } from "@/components/workflows/WorkflowStepList"
import {
  WorkflowBuilderAgentOption,
  WorkflowBuilderCollectionOption,
  WorkflowStepProperties,
} from "@/components/workflows/WorkflowStepProperties"
import { WorkflowValidationSummary } from "@/components/workflows/WorkflowValidationSummary"

type BuilderMode = "create" | "edit"
type BuilderAction = "save" | "validate" | "publish" | "enable" | "preview" | "run"

interface WorkflowBuilderProps {
  mode: BuilderMode
  workflowId?: string
}

const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Singapore",
  "Asia/Tokyo",
]

export function WorkflowBuilder({ mode, workflowId }: WorkflowBuilderProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  const requestConfirmation = useConfirm()
  const requestedTemplateId =
    mode === "create" ? searchParams.get("template") : null
  const [catalog, setCatalog] = useState<WorkflowStepCatalogEntry[]>([])
  const [agents, setAgents] = useState<WorkflowBuilderAgentOption[]>([])
  const [collections, setCollections] = useState<WorkflowBuilderCollectionOption[]>([])
  const [workflowIdState, setWorkflowIdState] = useState(workflowId || "")
  const [status, setStatus] = useState<WorkflowDefinitionStatus>("draft")
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null)
  const [latestVersionNumber, setLatestVersionNumber] = useState(0)
  const [sourceTemplateId, setSourceTemplateId] = useState<string | null>(null)
  const [name, setName] = useState("New workflow")
  const [description, setDescription] = useState("")
  const [tagsInput, setTagsInput] = useState("")
  const [definition, setDefinition] = useState<WorkflowDefinitionDocument>(
    createDefaultDefinition()
  )
  const [selectedStepKey, setSelectedStepKey] = useState("query_context")
  const [validation, setValidation] = useState<WorkflowValidationResponse | null>(null)
  const [hasValidated, setHasValidated] = useState(false)
  const [schedulePreview, setSchedulePreview] = useState<WorkflowSchedulePreviewItem[]>([])
  const [isLoading, setIsLoading] = useState(mode === "edit")
  const [action, setAction] = useState<BuilderAction | null>(null)
  const [error, setError] = useState<string | null>(null)

  const applyWorkflow = useCallback((workflow: WorkflowDefinitionDetail) => {
    setWorkflowIdState(workflow.id)
    setStatus(workflow.status)
    setCurrentVersionId(workflow.current_version_id || null)
    setLatestVersionNumber(workflow.latest_version_number || 0)
    setName(workflow.name)
    setDescription(workflow.description || "")
    setTagsInput((workflow.tags || []).join(", "))
    setDefinition(workflow.draft_definition)
    setSelectedStepKey(workflow.draft_definition.steps[0]?.key || "")
    setSourceTemplateId(
      String(
        workflow.metadata?.template_id ||
          workflow.draft_definition.metadata?.template ||
          ""
      ) || null
    )
  }, [])

  const applyTemplate = useCallback((template: WorkflowTemplate) => {
    if (!template.available_for_authoring) {
      const freshDefinition = createDefaultDefinition()
      setWorkflowIdState("")
      setStatus("draft")
      setCurrentVersionId(null)
      setLatestVersionNumber(0)
      setSourceTemplateId(null)
      setName("New workflow")
      setDescription("")
      setTagsInput("")
      setDefinition(freshDefinition)
      setSelectedStepKey(freshDefinition.steps[0]?.key || "")
      setError(template.unavailable_reason || "Template is not available.")
      return
    }

    const seededDefinition = createDefinitionFromTemplate(template)
    setWorkflowIdState("")
    setStatus("draft")
    setCurrentVersionId(null)
    setLatestVersionNumber(0)
    setSourceTemplateId(template.id)
    setName(template.name)
    setDescription(template.description)
    setTagsInput(template.tags.join(", "))
    setDefinition(seededDefinition)
    setSelectedStepKey(seededDefinition.steps[0]?.key || "")
    setValidation(null)
    setHasValidated(false)
    setSchedulePreview([])
  }, [])

  const loadBuilder = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const workflowPromise =
        mode === "edit" && workflowId
          ? workflowApi.getWorkflow(workflowId)
          : Promise.resolve(null)
      const templatePromise =
        requestedTemplateId && mode === "create"
          ? workflowApi.getTemplate(requestedTemplateId)
          : Promise.resolve(null)
      const [
        catalogResponse,
        agentResponse,
        collectionResponse,
        workflowResponse,
        templateResponse,
      ] = await Promise.all([
        workflowApi.getStepCatalog(),
        agentApi.listAgents().catch(() => ({ configs: [] })),
        ragApi.listCollections().catch(() => ({
          collections: [],
        })),
        workflowPromise,
        templatePromise,
      ])

      setCatalog(catalogResponse.steps)
      setAgents(normalizeAgents(agentResponse))
      setCollections(normalizeCollections(collectionResponse))

      if (workflowResponse?.workflow) {
        applyWorkflow(workflowResponse.workflow)
      } else if (templateResponse?.template) {
        applyTemplate(templateResponse.template)
      } else if (mode === "create") {
        const freshDefinition = createDefaultDefinition()
        setSourceTemplateId(null)
        setDefinition(freshDefinition)
        setSelectedStepKey(freshDefinition.steps[0]?.key || "")
      }
    } catch (err: any) {
      setError(errorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }, [applyTemplate, applyWorkflow, mode, requestedTemplateId, workflowId])

  useEffect(() => {
    loadBuilder()
  }, [loadBuilder])

  const catalogByType = useMemo(() => {
    return new Map(catalog.map((entry) => [entry.type, entry]))
  }, [catalog])

  const validationErrors = validation?.errors || []
  const selectedStepIndex = definition.steps.findIndex(
    (step) => step.key === selectedStepKey
  )
  const selectedStep =
    selectedStepIndex >= 0 ? definition.steps[selectedStepIndex] : null
  const selectedStepErrors = selectedStep
    ? validationErrors.filter(
        (item) =>
          item.step_key === selectedStep.key || item.step_index === selectedStepIndex
      )
    : []
  const isBusy = action !== null
  const trigger = definition.trigger
  const runtime = definition.runtime || defaultRuntimePolicy()

  function updateTrigger(patch: Partial<WorkflowTriggerDefinition>) {
    setDefinition((current) => ({
      ...current,
      trigger: {
        ...current.trigger,
        ...patch,
      },
    }))
    setSchedulePreview([])
  }

  function changeTriggerType(value: WorkflowTriggerType) {
    if (value === "schedule") {
      updateTrigger({
        type: "schedule",
        cron: trigger.cron || "0 2 * * *",
        timezone: trigger.timezone || "UTC",
        misfire_policy: trigger.misfire_policy || "run_once",
      })
      return
    }

    updateTrigger({
      type: "manual",
      cron: null,
      timezone: null,
      misfire_policy: "run_once",
    })
  }

  function updateRuntime(patch: Partial<WorkflowRuntimePolicy>) {
    setDefinition((current) => ({
      ...current,
      runtime: {
        ...defaultRuntimePolicy(),
        ...current.runtime,
        ...patch,
      },
    }))
  }

  function updateSelectedStep(nextStep: WorkflowStepDefinition) {
    setDefinition((current) => {
      const index = current.steps.findIndex((step) => step.key === selectedStepKey)
      if (index < 0) return current
      const nextSteps = [...current.steps]
      nextSteps[index] = nextStep
      return { ...current, steps: nextSteps }
    })
    setSelectedStepKey(nextStep.key)
  }

  function addStep(stepType: string) {
    const entry = catalogByType.get(stepType)
    const nextStep = createStepForType(stepType, definition.steps, entry)
    setDefinition((current) => ({
      ...current,
      steps: [...current.steps, nextStep],
    }))
    setSelectedStepKey(nextStep.key)
  }

  function moveStep(stepKey: string, direction: "up" | "down") {
    setDefinition((current) => {
      const index = current.steps.findIndex((step) => step.key === stepKey)
      if (index < 0) return current
      const nextIndex = direction === "up" ? index - 1 : index + 1
      if (nextIndex < 0 || nextIndex >= current.steps.length) return current
      const nextSteps = [...current.steps]
      const [step] = nextSteps.splice(index, 1)
      nextSteps.splice(nextIndex, 0, step)
      return { ...current, steps: nextSteps }
    })
  }

  function removeStep(stepKey: string) {
    setDefinition((current) => {
      if (current.steps.length <= 1) return current
      const index = current.steps.findIndex((step) => step.key === stepKey)
      const nextSteps = current.steps.filter((step) => step.key !== stepKey)
      if (selectedStepKey === stepKey) {
        const fallback = nextSteps[Math.max(0, index - 1)] || nextSteps[0]
        setSelectedStepKey(fallback?.key || "")
      }
      return { ...current, steps: nextSteps }
    })
  }

  async function validateDraft(): Promise<WorkflowValidationResponse | null> {
    setAction("validate")
    setError(null)
    try {
      const response = await workflowApi.validateDefinition(definition)
      setValidation(response)
      setHasValidated(true)
      if (response.valid) {
        toast({ title: "Workflow valid", description: name })
      }
      return response
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Validation failed",
        description: message,
        variant: "destructive",
      })
      return null
    } finally {
      setAction(null)
    }
  }

  async function persistDraft(showToast: boolean): Promise<WorkflowDefinitionDetail | null> {
    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      tags: parseTags(tagsInput),
      metadata: {
        source: "workflow_builder",
        ...(sourceTemplateId ? { template_id: sourceTemplateId } : {}),
      },
      definition,
    }

    if (!payload.name) {
      setError("Name is required.")
      return null
    }

    const response = workflowIdState
      ? await workflowApi.updateWorkflow(workflowIdState, payload)
      : await workflowApi.createWorkflow(payload)

    applyWorkflow(response.workflow)
    if (!workflowIdState) {
      router.replace(`/workflows/${response.workflow.id}/edit`)
    }
    if (showToast) {
      toast({ title: "Draft saved", description: response.workflow.name })
    }
    return response.workflow
  }

  async function saveDraft() {
    setAction("save")
    setError(null)
    try {
      await persistDraft(true)
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Save failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setAction(null)
    }
  }

  async function publishDraft() {
    const confirmed = await requestConfirmation({
      title: "Publish workflow",
      description: `Publish ${name || "this workflow"} as a new version.`,
      confirmText: "Publish",
    })
    if (!confirmed) return

    setAction("publish")
    setError(null)
    try {
      const validationResponse = await workflowApi.validateDefinition(definition)
      setValidation(validationResponse)
      setHasValidated(true)
      if (hasBlockingErrors(validationResponse.errors)) {
        toast({
          title: "Publish blocked",
          description: "Resolve validation errors before publishing.",
          variant: "destructive",
        })
        return
      }

      const saved = await persistDraft(false)
      if (!saved) return
      const response = await workflowApi.publishWorkflow(
        saved.id,
        "Published from workflow builder"
      )
      applyWorkflow(response.workflow)
      toast({
        title: "Workflow published",
        description: `Version ${response.workflow.latest_version_number}`,
      })
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Publish failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setAction(null)
    }
  }

  async function enableWorkflow() {
    if (!workflowIdState || !currentVersionId) {
      setError("Publish the workflow before enabling it.")
      return
    }

    const confirmed = await requestConfirmation({
      title: "Enable workflow",
      description: `Enable scheduled or manual execution for ${name}.`,
      confirmText: "Enable",
    })
    if (!confirmed) return

    setAction("enable")
    setError(null)
    try {
      const response = await workflowApi.enableWorkflow(
        workflowIdState,
        "Enabled from workflow builder"
      )
      applyWorkflow(response.workflow)
      toast({ title: "Workflow enabled", description: response.workflow.name })
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Enable failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setAction(null)
    }
  }

  async function previewSchedule() {
    const cron = trigger.cron || ""
    const timezone = trigger.timezone || ""
    if (!cron || !timezone) {
      setError("Schedule preview requires cron and timezone.")
      return
    }

    setAction("preview")
    setError(null)
    try {
      const response = await workflowApi.previewDefinitionSchedule(cron, timezone, 5)
      setSchedulePreview(response.preview.next_runs)
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Preview failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setAction(null)
    }
  }

  async function runTest() {
    if (!workflowIdState || status !== "active") return
    const confirmed = await requestConfirmation({
      title: "Run test",
      description: `Start a manual run for ${name}.`,
      confirmText: "Run",
    })
    if (!confirmed) return

    setAction("run")
    setError(null)
    try {
      const response = await workflowApi.runNow(workflowIdState)
      toast({
        title: "Workflow run started",
        description: shortId(response.run.id),
      })
    } catch (err: any) {
      const message = errorMessage(err)
      setError(message)
      toast({
        title: "Run failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setAction(null)
    }
  }

  function focusValidationPath(path: string, item: WorkflowValidationErrorItem) {
    if (item.step_key) {
      setSelectedStepKey(item.step_key)
      return
    }
    if (typeof item.step_index === "number" && definition.steps[item.step_index]) {
      setSelectedStepKey(definition.steps[item.step_index].key)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <Button asChild variant="ghost" size="sm" className="w-fit px-2">
              <Link href="/workflows">
                <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
                Back
              </Link>
            </Button>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="break-words text-2xl font-semibold tracking-normal">
                {mode === "create" && !workflowIdState ? "New workflow" : name}
              </h1>
              <StatusBadge status={statusTone(status)}>{labelize(status)}</StatusBadge>
              {currentVersionId ? (
                <StatusBadge status="info" showIcon={false}>
                  v{latestVersionNumber || 1}
                </StatusBadge>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={validateDraft}
              disabled={isBusy}
              title="Validate workflow"
            >
              {action === "validate" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Validate
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={saveDraft}
              disabled={isBusy}
              title="Save draft"
            >
              {action === "save" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              Save draft
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-danger-border bg-danger-soft p-3 text-sm text-danger-soft-foreground">
            {error}
          </div>
        ) : null}

        <section className="rounded-md border bg-card p-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
            <Field label="Name" htmlFor="workflow-name">
              <Input
                id="workflow-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
            <Field label="Tags" htmlFor="workflow-tags">
              <Input
                id="workflow-tags"
                value={tagsInput}
                onChange={(event) => setTagsInput(event.target.value)}
                placeholder="nightly, rag"
              />
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Description" htmlFor="workflow-description">
              <Textarea
                id="workflow-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
              />
            </Field>
          </div>
        </section>

        <section className="rounded-md border bg-card p-4">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Trigger</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Trigger" htmlFor="workflow-trigger-type">
                  <Select
                    value={trigger.type}
                    onValueChange={(value) =>
                      changeTriggerType(value as WorkflowTriggerType)
                    }
                  >
                    <SelectTrigger id="workflow-trigger-type">
                      <SelectValue placeholder="Trigger" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="manual">Manual</SelectItem>
                      <SelectItem value="schedule">Schedule</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                {trigger.type === "schedule" ? (
                  <Field label="Misfire" htmlFor="workflow-misfire-policy">
                    <Select
                      value={trigger.misfire_policy || "run_once"}
                      onValueChange={(value) =>
                        updateTrigger({
                          misfire_policy: value as WorkflowMisfirePolicy,
                        })
                      }
                    >
                      <SelectTrigger id="workflow-misfire-policy">
                        <SelectValue placeholder="Misfire" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="skip">Skip</SelectItem>
                        <SelectItem value="run_once">Run once</SelectItem>
                        <SelectItem value="catch_up">Catch up</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                ) : null}
              </div>

              {trigger.type === "schedule" ? (
                <div className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Schedule" htmlFor="workflow-cron">
                      <Input
                        id="workflow-cron"
                        value={trigger.cron || ""}
                        onChange={(event) =>
                          updateTrigger({ cron: event.target.value })
                        }
                      />
                    </Field>
                    <Field label="Timezone" htmlFor="workflow-timezone">
                      <Select
                        value={trigger.timezone || "UTC"}
                        onValueChange={(value) =>
                          updateTrigger({ timezone: value })
                        }
                      >
                        <SelectTrigger id="workflow-timezone">
                          <SelectValue placeholder="Timezone" />
                        </SelectTrigger>
                        <SelectContent>
                          {timezoneOptions(trigger.timezone).map((timezone) => (
                            <SelectItem key={timezone} value={timezone}>
                              {timezone}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={previewSchedule}
                      disabled={isBusy}
                      title="Preview schedule"
                    >
                      {action === "preview" ? (
                        <Loader2
                          className="mr-2 h-4 w-4 animate-spin"
                          aria-hidden="true"
                        />
                      ) : (
                        <CalendarClock className="mr-2 h-4 w-4" aria-hidden="true" />
                      )}
                      Preview
                    </Button>
                    {schedulePreview.slice(0, 3).map((item) => (
                      <span
                        key={item.run_at}
                        className="rounded-sm border px-2 py-1 text-xs text-muted-foreground"
                      >
                        {formatDate(item.run_at)}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="space-y-4">
              <h2 className="text-sm font-semibold">Runtime</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Concurrency" htmlFor="workflow-concurrency">
                  <Select
                    value={runtime.concurrency_policy || "skip_if_running"}
                    onValueChange={(value) =>
                      updateRuntime({
                        concurrency_policy: value as WorkflowConcurrencyPolicy,
                      })
                    }
                  >
                    <SelectTrigger id="workflow-concurrency">
                      <SelectValue placeholder="Concurrency" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="skip_if_running">Skip if running</SelectItem>
                      <SelectItem value="queue_after_current">Queue</SelectItem>
                      <SelectItem value="allow_parallel">Allow parallel</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Redaction" htmlFor="workflow-redaction">
                  <Select
                    value={runtime.redaction_policy || "default"}
                    onValueChange={(value) =>
                      updateRuntime({
                        redaction_policy: value as WorkflowRedactionPolicy,
                      })
                    }
                  >
                    <SelectTrigger id="workflow-redaction">
                      <SelectValue placeholder="Redaction" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="default">Default</SelectItem>
                      <SelectItem value="strict">Strict</SelectItem>
                      <SelectItem value="none">None</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Timeout seconds" htmlFor="workflow-timeout">
                  <Input
                    id="workflow-timeout"
                    type="number"
                    min={1}
                    value={runtime.timeout_seconds ?? 1800}
                    onChange={(event) =>
                      updateRuntime({
                        timeout_seconds: clampNumber(event.target.value, 1, 86400, 1800),
                      })
                    }
                  />
                </Field>
                <Field label="Budget cents" htmlFor="workflow-budget">
                  <Input
                    id="workflow-budget"
                    type="number"
                    min={0}
                    value={runtime.budget_limit_cents ?? ""}
                    onChange={(event) =>
                      updateRuntime({
                        budget_limit_cents:
                          event.target.value.trim() === ""
                            ? null
                            : clampNumber(event.target.value, 0, 100000000, 0),
                      })
                    }
                  />
                </Field>
              </div>
            </div>
          </div>
        </section>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
          <WorkflowStepList
            steps={definition.steps}
            catalog={catalog}
            selectedStepKey={selectedStepKey}
            validationErrors={validationErrors}
            onSelectStep={setSelectedStepKey}
            onMoveStep={moveStep}
            onRemoveStep={removeStep}
            onAddStep={addStep}
          />
          <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
            <WorkflowStepProperties
              step={selectedStep}
              stepIndex={selectedStepIndex}
              catalogEntry={
                selectedStep ? catalogByType.get(selectedStep.type) : undefined
              }
              validationErrors={selectedStepErrors}
              allSteps={definition.steps}
              agents={agents}
              collections={collections}
              onChange={updateSelectedStep}
            />
          </div>
        </div>

        <div className="sticky bottom-0 z-20 -mx-4 border-t bg-background/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-md sm:border">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <WorkflowValidationSummary
              errors={validationErrors}
              hasValidated={hasValidated}
              onFocusPath={focusValidationPath}
              className="xl:max-w-2xl xl:flex-1"
            />
            <div className="flex flex-wrap gap-2 xl:justify-end">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={saveDraft}
                disabled={isBusy}
                title="Save draft"
              >
                {action === "save" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Save className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Save draft
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={publishDraft}
                disabled={isBusy}
                title="Publish workflow"
              >
                {action === "publish" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Publish
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={enableWorkflow}
                disabled={isBusy || !workflowIdState || !currentVersionId || status === "active"}
                title="Enable workflow"
              >
                {action === "enable" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Rocket className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Enable
              </Button>
              {currentVersionId ? (
                <Button asChild variant="outline" size="sm">
                  <Link href="/workflows">
                    <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />
                    Operations
                  </Link>
                </Button>
              ) : null}
              {status === "active" ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={runTest}
                  disabled={isBusy || !workflowIdState}
                  title="Run test"
                >
                  {action === "run" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" aria-hidden="true" />
                  )}
                  Run test
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  )
}

function createDefinitionFromTemplate(
  template: WorkflowTemplate
): WorkflowDefinitionDocument {
  const definition = cloneDefinition(template.definition)
  return {
    ...definition,
    metadata: {
      ...(definition.metadata || {}),
      template: template.id,
      template_seeded: true,
    },
    runtime: {
      ...defaultRuntimePolicy(),
      ...(definition.runtime || {}),
    },
    steps: definition.steps.map((step) => seedStepFromTemplate(step)),
  }
}

function seedStepFromTemplate(
  step: WorkflowStepDefinition
): WorkflowStepDefinition {
  if (step.type === "rag.query") {
    return {
      ...step,
      config: {
        ...step.config,
        collection_id: "",
        query:
          String(step.config.query || "").includes("{{")
            ? "Summarize documents added since the last successful run."
            : step.config.query,
      },
    }
  }
  if (step.type === "agent.run") {
    return {
      ...step,
      config: {
        ...step.config,
        agent_id: "",
      },
    }
  }
  if (step.type === "notify.in_app") {
    return {
      ...step,
      config: {
        ...step.config,
        recipients: [],
      },
    }
  }
  return step
}

function cloneDefinition(
  definition: WorkflowDefinitionDocument
): WorkflowDefinitionDocument {
  return JSON.parse(JSON.stringify(definition)) as WorkflowDefinitionDocument
}

function createDefaultDefinition(): WorkflowDefinitionDocument {
  return {
    schema_version: 1,
    trigger: {
      type: "manual",
      misfire_policy: "run_once",
    },
    runtime: defaultRuntimePolicy(),
    steps: [
      {
        key: "query_context",
        type: "rag.query",
        name: "Query knowledge",
        config: {
          collection_id: "",
          query: "{{input.query}}",
          limit: 5,
        },
        depends_on: [],
        retry: {
          max_attempts: 1,
          backoff_seconds: 0,
        },
      },
    ],
    metadata: {},
  }
}

function defaultRuntimePolicy(): WorkflowRuntimePolicy {
  return {
    concurrency_policy: "skip_if_running",
    timeout_seconds: 1800,
    budget_limit_cents: null,
    redaction_policy: "default",
  }
}

function createStepForType(
  stepType: string,
  existingSteps: WorkflowStepDefinition[],
  entry?: WorkflowStepCatalogEntry
): WorkflowStepDefinition {
  const key = nextStepKey(stepType, existingSteps)
  return {
    key,
    type: stepType,
    name: entry?.display_name || labelize(stepType),
    config: defaultConfigForType(stepType, existingSteps),
    depends_on: [],
    retry: {
      max_attempts: 1,
      backoff_seconds: 0,
    },
  }
}

function defaultConfigForType(
  stepType: string,
  existingSteps: WorkflowStepDefinition[]
): Record<string, unknown> {
  if (stepType === "rag.query") {
    return {
      collection_id: "",
      query: "{{input.query}}",
      limit: 5,
    }
  }
  if (stepType === "agent.run") {
    return {
      agent_id: "",
      prompt_template: "Summarize the workflow input.",
    }
  }
  if (stepType === "condition.no_results_skip") {
    return {
      input_step_key: existingSteps[existingSteps.length - 1]?.key || "",
      path: "documents",
    }
  }
  if (stepType === "notify.in_app") {
    return {
      recipients: ["admin"],
      title_template: "Workflow update",
      body_template: "{{previous.message}}",
      severity: "info",
    }
  }
  return {}
}

function nextStepKey(
  stepType: string,
  existingSteps: WorkflowStepDefinition[]
): string {
  const bases: Record<string, string> = {
    "rag.query": "query_context",
    "agent.run": "run_agent",
    "condition.no_results_skip": "skip_if_empty",
    "notify.in_app": "notify_team",
  }
  const existingKeys = new Set(existingSteps.map((step) => step.key))
  const base =
    bases[stepType] ||
    stepType
      .replace(/[^a-zA-Z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .toLowerCase() ||
    "step"
  let candidate = base
  let suffix = 2
  while (existingKeys.has(candidate)) {
    candidate = `${base}_${suffix}`
    suffix += 1
  }
  return candidate
}

function normalizeAgents(data: any): WorkflowBuilderAgentOption[] {
  const items = Array.isArray(data?.configs)
    ? data.configs
    : Array.isArray(data?.agents)
      ? data.agents
      : Array.isArray(data)
        ? data
        : []
  return items
    .map((item: any) => ({
      id: String(item.id),
      name: String(item.name || item.display_name || `Agent ${item.id}`),
    }))
    .filter((item: WorkflowBuilderAgentOption) => item.id && item.name)
}

function normalizeCollections(data: any): WorkflowBuilderCollectionOption[] {
  const items = Array.isArray(data?.collections)
    ? data.collections
    : Array.isArray(data)
      ? data
      : []
  return items
    .map((item: any) => ({
      id: String(item.id),
      name: String(item.name || item.display_name || `Collection ${item.id}`),
    }))
    .filter((item: WorkflowBuilderCollectionOption) => item.id && item.name)
}

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function timezoneOptions(current?: string | null): string[] {
  if (current && !COMMON_TIMEZONES.includes(current)) {
    return [current, ...COMMON_TIMEZONES]
  }
  return COMMON_TIMEZONES
}

function hasBlockingErrors(errors: WorkflowValidationErrorItem[]): boolean {
  return errors.some((error) => error.severity !== "warning")
}

function statusTone(status: WorkflowDefinitionStatus): StatusBadgeStatus {
  if (status === "active") return "success"
  if (status === "draft") return "warning"
  return "neutral"
}

function labelize(value: string): string {
  return value
    .split(/[._-]/)
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
