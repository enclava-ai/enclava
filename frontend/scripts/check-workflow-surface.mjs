import { existsSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const failures = []

function readRequired(relativePath) {
  const absolutePath = join(frontendRoot, relativePath)
  if (!existsSync(absolutePath)) {
    failures.push(`${relativePath}: file is missing`)
    return ""
  }
  return readFileSync(absolutePath, "utf8")
}

function requireIncludes(relativePath, needles, label) {
  const content = readRequired(relativePath)
  for (const needle of needles) {
    if (!content.includes(needle)) {
      failures.push(`${relativePath}: missing ${label || needle} (${needle})`)
    }
  }
}

function requireRegex(relativePath, regex, label) {
  const content = readRequired(relativePath)
  if (!regex.test(content)) {
    failures.push(`${relativePath}: missing ${label}`)
  }
}

const requiredFiles = [
  "src/app/workflows/page.tsx",
  "src/app/workflows/new/page.tsx",
  "src/app/workflows/[workflowId]/edit/page.tsx",
  "src/app/workflows/runs/[runId]/page.tsx",
  "src/app/api/workflows/route.ts",
  "src/app/api/workflows/runs/[runId]/route.ts",
  "src/components/workflows/WorkflowOperationsConsole.tsx",
  "src/components/workflows/WorkflowBuilder.tsx",
  "src/components/workflows/WorkflowRunsTable.tsx",
  "src/components/workflows/WorkflowRunTimeline.tsx",
  "src/components/workflows/WorkflowScheduleBoard.tsx",
  "src/components/workflows/WorkflowTemplatePicker.tsx",
  "src/components/ui/navigation.tsx",
  "src/lib/api-client.ts",
]

for (const file of requiredFiles) {
  readRequired(file)
}

requireIncludes("src/components/ui/navigation.tsx", [
  'workflow: { href: "/workflows", label: "Workflows" }',
  "isModuleEnabled(moduleName)",
  "...moduleNavItems",
], "workflow module navigation wiring")

requireIncludes("src/app/workflows/page.tsx", [
  "ProtectedRoute",
  'TabsTrigger value="overview"',
  'TabsTrigger value="runs"',
  'TabsTrigger value="schedules"',
  'TabsTrigger value="templates"',
  "WorkflowOperationsConsole",
  "WorkflowRunsTable",
  "WorkflowScheduleBoard",
  "WorkflowTemplatesPanel",
  'href="/workflows/new"',
], "workflow route tabs")

requireIncludes("src/app/api/workflows/route.ts", [
  "resource === 'admin_metrics'",
  "operations/admin-metrics",
  "action === 'recover_stale_locks'",
  "operations/recover-stale-locks",
  "action === 'apply_retention'",
  "operations/retention",
  "action === 'fire_api_trigger'",
  "action === 'fire_event_trigger'",
  "action === 'preview_schedule_definition'",
  "action === 'preview_schedule'",
  "action === 'publish'",
  "body?.action === 'enable' || body?.action === 'disable'",
  "/runs",
], "workflow proxy actions")

requireIncludes("src/lib/api-client.ts", [
  "getOperations()",
  "getAdminMetrics()",
  "getWorkflow(workflowId: string)",
  "createWorkflow(payload: WorkflowCreatePayload)",
  "updateWorkflow(workflowId: string",
  "publishWorkflow(workflowId: string",
  "validateDefinition(definition: WorkflowDefinitionDocument)",
  "previewDefinitionSchedule(cron: string, timezone: string",
  "getRecentRuns(params?:",
  "getScheduleBoard()",
  "fireApiTrigger(apiSlug: string",
  "fireEventTrigger(eventName: string",
  "recoverStaleLocks(payload: WorkflowStaleLockRecoveryRequest",
  "applyRetentionPolicy(payload: WorkflowRetentionPolicy",
  "runNow(workflowId: string",
  "enableWorkflow(workflowId: string",
  "disableWorkflow(workflowId: string",
  "previewSchedule(workflowId: string",
  "workflowRunApi",
  "cancelRun(runId: string",
  "retryRun(runId: string",
  "approveRun(runId: string",
  "rejectRun(runId: string",
], "workflow API client methods")

requireIncludes("src/components/workflows/WorkflowOperationsConsole.tsx", [
  "filterOptions",
  "workflowApi.getOperations",
  "workflowApi.getAdminMetrics",
  "OperationalMetricsStrip",
  "workflowApi.runNow",
  "Filter workflows",
  "latest_run",
  "failed + totals.missed",
  "/workflows/${row.id}/edit",
  "/workflows/runs/${row.latest_run.id}",
], "operations console states and actions")

requireIncludes("src/components/workflows/WorkflowBuilder.tsx", [
  "validateDraft",
  "persistDraft",
  "publishDraft",
  "enableWorkflow",
  "previewSchedule",
  "runTest",
  "workflowApi.validateDefinition",
  "workflowApi.previewDefinitionSchedule",
  "workflowApi.publishWorkflow",
  "workflowApi.enableWorkflow",
  "workflowApi.runNow",
  "WorkflowValidationSummary",
  "createDefinitionFromTemplate",
  "requestConfirmation",
], "builder validation, publish, enable, preview, and run paths")

requireIncludes("src/components/workflows/WorkflowScheduleBoard.tsx", [
  "workflowApi.getScheduleBoard",
  "workflowApi.previewSchedule",
  "workflowApi.disableWorkflow",
  "workflowApi.enableWorkflow",
  "workflowApi.runNow",
  "previewByWorkflow",
  "No schedules",
  "Workflow run started",
], "schedule board controls")

requireIncludes("src/app/workflows/runs/[runId]/page.tsx", [
  "workflowRunApi.getRun",
  "workflowRunApi.cancelRun",
  "workflowRunApi.retryRun",
  "workflowRunApi.approveRun",
  "workflowRunApi.rejectRun",
  "workflowRunApi.executeRun",
  "WorkflowRunTimeline",
], "run detail actions")

requireIncludes("src/components/workflows/WorkflowRunTimeline.tsx", [
  "WorkflowRunTimeline",
  "ApprovalList",
  "PayloadPanel",
  "EventList",
  "ArtifactList",
  "No steps have run.",
  "No artifacts recorded.",
  "formatPayload",
  "runTone",
  "stepTone",
], "run timeline and artifact preview")

requireRegex(
  "src/components/workflows/WorkflowOperationsConsole.tsx",
  /const filterOptions:[\s\S]*failed[\s\S]*missed[\s\S]*disabled[\s\S]*no_schedule/,
  "overview state filters"
)

if (failures.length) {
  console.error("Workflow surface guard failed:")
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log("Workflow surface guard passed.")
