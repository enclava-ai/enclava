# Workflows Implementation Plan

Status: Proposed
Prepared: 2026-07-05
Related sketch: `.planning/sketches/001-workflow-ux-options/`

## Executive Summary

Enclava should implement workflows as a governed automation layer around existing platform capabilities, not as a general-purpose workflow product. A workflow is a durable, auditable process that can run on a schedule, manually, or from a future event/API trigger. It coordinates steps such as connector sync, RAG search/summarization, agent execution, extraction jobs, notifications, and approvals.

The first release should avoid an elaborate canvas engine. The useful core is:

- Scheduled and manual runs.
- Linear typed steps with clear inputs/outputs.
- Run history, logs, retry, and artifacts.
- Permission, audit, and budget enforcement.
- A first screen that answers: what is running, what failed, what runs next.

Agents remain the reasoning/action unit. Workflows are the orchestration and governance unit. For example, "Every night at 2am summarize new RAG data" is a workflow that wakes up an agent or RAG summarizer as one step.

## Product Definition

### Workflow

A workflow is a saved automation definition with triggers, steps, runtime policy, and ownership metadata. It owns schedule state, run state, audit trail, retry policy, budget limits, and artifacts.

Examples:

- Nightly RAG summary.
- Connector intake triage.
- Weekly extraction report.
- Admin usage anomaly digest.
- Manual "process this collection" automation.
- Future API-triggered customer-specific automation.

### Agent

An agent is a configured AI worker with model, tools, knowledge access, and behavior instructions. An agent can be invoked by chat, API, or workflow step. It should not own scheduling, retries, approval state, or workflow-level audit.

### Non-Goal

Do not build a full Airflow, Temporal, Zapier, or n8n replacement in the first implementation. Enclava needs a platform-native automation layer optimized for confidential AI operations. Start with a typed linear workflow engine; add branches, approvals, and external triggers after the core is proven.

## UX Direction

The winning UX direction should combine the three sketch variants:

- Default view: Operations Console.
- Edit view: Step Builder.
- Secondary view: Schedule Board.

The product should open on operational clarity, not authoring complexity. Users who visit Workflows usually need to know whether automations are healthy before they need to drag steps around.

### Navigation

Add `Workflows` to the primary app navigation once the route exists and the module is enabled.

Current relevant file:

- `frontend/src/components/ui/navigation.tsx`

Target module mapping:

```ts
const MODULE_NAV_MAP: Record<string, NavItem> = {
  rag: { href: "/rag", label: "RAG" },
  extract: { href: "/extract", label: "Extract" },
  workflow: { href: "/workflows", label: "Workflows" },
}
```

### Primary Route

Add:

- `frontend/src/app/workflows/page.tsx`

Initial tabs:

- `Overview`: operations console.
- `Runs`: run history and failures.
- `Schedules`: recurring and upcoming runs.
- `Templates`: starting points for common automations.

The builder should be reached from `New workflow`, `Edit draft`, or workflow detail, not be the default landing page.

### Operations Console

Purpose: answer "what is running, what failed, and what happens next?"

Layout:

- Left: workflow list with status, next run, last run, owner, and health.
- Center: selected workflow details, active run timeline, next scheduled run, recent incidents.
- Right: compact actions and policy summary: run now, disable, edit draft, retry failed run, budget cap, concurrency policy.

Key interactions:

- Filter workflows by status, module, owner, tag, and text.
- Run now with confirmation for workflows that may spend budget.
- Disable with confirmation and audit reason.
- Retry from failed step where supported.
- Open latest artifact directly from run detail.

States:

- Empty: no workflows yet, show templates rather than explanatory marketing copy.
- Loading: skeleton rows and timeline placeholders.
- Error: retryable error banner using existing frontend error utilities.
- Disabled module: consistent module-disabled messaging from existing module context.

### Step Builder

Purpose: make authoring readable and hard to misconfigure.

Layout:

- Top trigger strip: Manual, Schedule, Event/API later.
- Center step sequence: numbered typed steps.
- Right properties panel: selected trigger or step configuration.
- Bottom validation/action bar: save draft, publish, enable, run test.

Builder rules:

- Prefer a linear step list for v1.
- Avoid an arbitrary visual canvas initially.
- Show each step's declared inputs, outputs, permissions, and estimated cost.
- Validate required fields inline.
- Allow "test this step" using sample input once the execution engine supports isolated step runs.

### Schedule Board

Purpose: make recurring automations feel first-class.

Layout:

- Upcoming run queue grouped by today, tomorrow, this week.
- Calendar/list toggle only if useful after MVP.
- Schedule health: missed runs, paused schedules, next retry, last duration.
- Schedule preview when editing cron/timezone.

Critical scheduling UX:

- Let users choose timezone.
- Store and display next run as absolute timestamp plus relative display.
- Preview next 5 run times before publish.
- Explain missed-run policy in short labels, not long help text.

### Run Detail

Run detail is the source of truth for operational debugging.

It should include:

- Run metadata: workflow, version, trigger, started by, timestamps, duration, status.
- Step timeline: pending, running, skipped, succeeded, failed, retrying.
- Logs/events: structured messages with timestamps and severity.
- Inputs/outputs: JSON preview with sensitive values redacted.
- Artifacts: generated summaries, extraction results, files, notification payloads.
- Actions: cancel, retry run, retry from failed step, duplicate as test.

## Core Use Cases

### 1. Nightly RAG Summary

Goal: every night at 2am, summarize new data in a selected RAG collection and send/store the summary.

Trigger:

- Schedule: daily at 02:00 in selected timezone.

Steps:

1. Query RAG collection for documents added since last successful run.
2. If no new documents, record skipped result.
3. Run agent or summarizer prompt over the result set.
4. Save summary artifact.
5. Notify configured users or expose on workflow detail.

Why workflow over agent:

- Schedule ownership.
- "Since last successful run" checkpoint.
- No-new-data skip state.
- Artifact and audit history.
- Budget cap and retry policy.

### 2. Connector Intake Triage

Goal: sync a connector, classify new items, and route outputs.

Trigger:

- Schedule or manual.

Steps:

1. Run connector sync.
2. Collect newly ingested documents/items.
3. Run RAG or agent triage.
4. Store classifications as artifact or metadata.
5. Notify owner if high-priority items exist.

Why workflow over agent:

- Connector sync is deterministic operational work.
- Agent is only one decision step.
- Users need a run history when connector auth or remote APIs fail.

### 3. Weekly Extraction Report

Goal: every Monday morning, process documents through an Extract template and create a report.

Trigger:

- Schedule: weekly.

Steps:

1. Select documents by collection, uploaded date, or connector source.
2. Run Extract template.
3. Aggregate successful and failed extraction rows.
4. Save report artifact.
5. Notify owner.

Why workflow over agent:

- Extraction jobs already have their own execution semantics.
- Workflow coordinates selection, execution, aggregation, and notification.

### 4. Admin Operations Digest

Goal: generate a daily admin digest for usage, spend, provider health, and failed automations.

Trigger:

- Schedule.

Steps:

1. Query internal usage and budget data.
2. Query provider health.
3. Query failed workflow runs.
4. Summarize with an agent.
5. Store digest and notify admins.

Why workflow over agent:

- Needs privileged platform data and audit.
- Needs schedule and controlled scope.

### 5. Human Approval Flow

Goal: pause before a sensitive action until an authorized user approves.

Trigger:

- Manual, schedule, or event.

Steps:

1. Run analysis.
2. Create approval task.
3. Pause run.
4. Continue only after approval.
5. Execute final action.

This should be post-MVP because it requires pause/resume state, assignee UX, and stronger permission boundaries.

## Current Codebase Fit

### Existing Workflow Module

Current file:

- `backend/app/modules/workflow/main.py`

Current behavior:

- Registers a `workflow` module.
- Tracks basic in-memory counters.
- Provides `workflow.execute`, `workflow.read`, and `workflow.manage` permissions.
- `execute` currently echoes request data and returns `completed`.
- No persistence, real scheduling, real orchestration, run state, artifacts, or UI route.

Target behavior:

- Keep the module as the module-system adapter.
- Move business logic to services and data models.
- Let `WorkflowModule.process_request` delegate status/manual execution to `WorkflowService`.
- Do not rely on generic module execution for production workflow APIs.

### Module Factory

Current file:

- `backend/app/modules/factory.py`

Current behavior:

- Builds RAG, Agent, and Workflow in dependency order.
- Workflow depends on Agent.

Target behavior:

- Workflow should depend on service interfaces, not concrete module internals where possible.
- Add dependencies through a `WorkflowRuntimeDependencies` object or service registry:
  - agent service/module
  - RAG service/module
  - extract service/module
  - connector service
  - notification service
  - audit service
  - budget/usage service

### API Shape

Current generic module APIs are useful for module management and smoke behavior. Workflows need dedicated internal APIs under:

- `/api-internal/v1/workflows`

Rationale:

- Workflow APIs need authenticated user context.
- Runs need ownership, permissions, pagination, filtering, and audit.
- Schedule operations need validation and preview.
- Run actions need idempotency and authorization.

### Frontend Fit

Current relevant files:

- `frontend/src/contexts/ModulesContext.tsx`
- `frontend/src/components/ui/navigation.tsx`
- `frontend/src/app/rag/page.tsx`
- `frontend/src/app/extract/page.tsx`
- `frontend/src/components/ui/confirm-dialog.tsx`
- `frontend/src/hooks/use-toast.ts`

Target behavior:

- Use existing module context to conditionally show Workflows.
- Add route-level API client helpers for workflow REST calls.
- Reuse existing page, card, badge, table, dialog, toast, confirmation, skeleton, and error utilities.

## Backend Architecture

### Package Layout

Recommended additions:

```text
backend/app/models/workflow.py
backend/app/schemas/workflow.py
backend/app/services/workflows/
  __init__.py
  service.py
  runner.py
  scheduler.py
  steps.py
  registry.py
  artifacts.py
  events.py
backend/app/api/internal_v1/workflows.py
backend/alembic/versions/034_add_workflows.py
```

Optional later split:

```text
backend/app/tasks/workflow_scheduler.py
backend/app/tasks/workflow_runner.py
```

### Data Model

Use Postgres as the source of truth. Avoid in-memory workflow state except transient worker-local caches.

#### `workflow_definitions`

Represents the stable identity and ownership of a workflow.

Fields:

- `id`: UUID primary key.
- `name`: string.
- `slug`: string, unique per owner/tenant scope.
- `description`: nullable text.
- `status`: `draft`, `active`, `disabled`, `archived`.
- `owner_user_id`: FK users.
- `created_by_user_id`: FK users.
- `updated_by_user_id`: FK users.
- `tags`: JSON array or separate table if project conventions prefer.
- `current_version_id`: FK workflow_versions nullable.
- `created_at`, `updated_at`, `archived_at`.

Indexes:

- `(owner_user_id, status)`
- `(owner_user_id, slug)`
- `(status, updated_at)`

#### `workflow_versions`

Immutable published workflow configuration. Drafts can be mutable until published.

Fields:

- `id`: UUID primary key.
- `workflow_id`: FK workflow_definitions.
- `version_number`: integer.
- `status`: `draft`, `published`, `deprecated`.
- `definition`: JSONB typed document containing trigger, steps, runtime policy, and UI metadata.
- `validation_errors`: JSONB nullable.
- `published_by_user_id`: FK users nullable.
- `published_at`: nullable datetime.
- `created_at`, `updated_at`.

Indexes:

- `(workflow_id, version_number)` unique.
- `(workflow_id, status)`.

#### `workflow_triggers`

Materialized trigger records for queryable schedule state.

Fields:

- `id`: UUID primary key.
- `workflow_id`: FK.
- `workflow_version_id`: FK.
- `type`: `manual`, `schedule`, `event`, `api`.
- `enabled`: boolean.
- `schedule_cron`: nullable string.
- `timezone`: nullable IANA timezone string.
- `next_run_at`: UTC datetime nullable.
- `last_scheduled_at`: UTC datetime nullable.
- `misfire_policy`: `skip`, `run_once`, `catch_up`.
- `catchup_limit`: integer nullable.
- `created_at`, `updated_at`.

Indexes:

- `(enabled, next_run_at)`
- `(workflow_id, type)`

#### `workflow_runs`

Durable execution instance.

Fields:

- `id`: UUID primary key.
- `workflow_id`: FK.
- `workflow_version_id`: FK.
- `trigger_id`: FK nullable.
- `trigger_type`: string.
- `status`: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `paused`, `skipped`.
- `started_by_user_id`: FK nullable for schedules.
- `idempotency_key`: string nullable, unique per workflow.
- `input`: JSONB.
- `output`: JSONB nullable.
- `error`: JSONB nullable.
- `budget_limit_cents`: integer nullable.
- `budget_used_cents`: integer default 0.
- `started_at`, `finished_at`, `created_at`, `updated_at`.
- `locked_at`, `locked_by`: nullable worker ownership.

Indexes:

- `(workflow_id, created_at desc)`
- `(status, created_at)`
- `(trigger_type, created_at)`
- unique `(workflow_id, idempotency_key)` where idempotency key is not null.

#### `workflow_step_runs`

One row per step execution attempt group.

Fields:

- `id`: UUID primary key.
- `workflow_run_id`: FK.
- `step_key`: stable key from definition.
- `step_type`: string.
- `step_name`: string.
- `status`: `pending`, `running`, `succeeded`, `failed`, `skipped`, `retrying`, `cancelled`.
- `attempt`: integer.
- `max_attempts`: integer.
- `input`: JSONB.
- `output`: JSONB nullable.
- `error`: JSONB nullable.
- `started_at`, `finished_at`, `created_at`, `updated_at`.

Indexes:

- `(workflow_run_id, step_key)`
- `(status, created_at)`

#### `workflow_artifacts`

Stores references to generated output without bloating run rows.

Fields:

- `id`: UUID primary key.
- `workflow_run_id`: FK.
- `step_run_id`: FK nullable.
- `type`: `summary`, `extract_result`, `file`, `notification`, `json`, `text`.
- `title`: string.
- `content_type`: string.
- `storage_ref`: string nullable.
- `preview`: text nullable.
- `metadata`: JSONB.
- `created_at`.

Indexes:

- `(workflow_run_id, created_at)`
- `(type, created_at)`

#### `workflow_events`

Structured audit/debug events for the run detail timeline.

Fields:

- `id`: UUID primary key.
- `workflow_id`: FK.
- `workflow_run_id`: FK nullable.
- `step_run_id`: FK nullable.
- `level`: `debug`, `info`, `warning`, `error`.
- `event_type`: string.
- `message`: text.
- `metadata`: JSONB.
- `created_at`.

Indexes:

- `(workflow_run_id, created_at)`
- `(workflow_id, created_at)`
- `(level, created_at)`

### Workflow Definition JSON

The JSON definition stored in `workflow_versions.definition` should be validated through Pydantic schemas.

Example:

```json
{
  "schema_version": 1,
  "trigger": {
    "type": "schedule",
    "cron": "0 2 * * *",
    "timezone": "America/New_York",
    "misfire_policy": "run_once"
  },
  "runtime": {
    "concurrency_policy": "skip_if_running",
    "timeout_seconds": 1800,
    "budget_limit_cents": 500,
    "redaction_policy": "default"
  },
  "steps": [
    {
      "key": "find_new_docs",
      "type": "rag.query",
      "name": "Find new documents",
      "config": {
        "collection_id": "uuid",
        "since": {"type": "last_successful_run"}
      },
      "retry": {"max_attempts": 2, "backoff_seconds": 60}
    },
    {
      "key": "summarize",
      "type": "agent.run",
      "name": "Summarize changes",
      "depends_on": ["find_new_docs"],
      "config": {
        "agent_id": "uuid",
        "prompt_template": "Summarize the new documents for an operations digest."
      },
      "retry": {"max_attempts": 1}
    }
  ]
}
```

V1 should support `depends_on` only as a validation mechanism for linear order. True DAG branching can come later.

### State Machines

#### Workflow Definition Status

- `draft`: not executable except test run.
- `active`: can run manually and from triggers.
- `disabled`: preserved but triggers do not enqueue runs.
- `archived`: hidden from default lists; cannot run.

#### Workflow Version Status

- `draft`: mutable.
- `published`: immutable and executable.
- `deprecated`: retained for historical runs.

#### Run Status

- `queued`: created and ready for runner.
- `running`: runner owns it.
- `succeeded`: all required steps succeeded or were intentionally skipped.
- `failed`: required step failed after retries or workflow-level validation failed.
- `cancelled`: user/system cancelled.
- `paused`: waiting for human approval or external event, post-MVP.
- `skipped`: trigger fired but policy skipped the run.

#### Step Status

- `pending`
- `running`
- `succeeded`
- `failed`
- `skipped`
- `retrying`
- `cancelled`

### Service Components

#### `WorkflowService`

Responsibilities:

- CRUD workflow definitions.
- Draft creation and update.
- Validate definitions.
- Publish versions.
- Enable/disable/archive.
- Manual run creation.
- Query runs, events, and artifacts.
- Enforce workflow permissions.
- Write audit records for lifecycle actions.

#### `WorkflowRunner`

Responsibilities:

- Claim queued runs with DB locking.
- Load immutable workflow version.
- Execute steps in order.
- Persist step inputs, outputs, errors, events, and artifacts.
- Apply retry policy.
- Enforce timeout and cancellation checks.
- Update usage/budget records.
- Redact sensitive data before persistence.

#### `WorkflowScheduler`

Responsibilities:

- Poll enabled schedule triggers due at or before `now`.
- Create queued runs with idempotency keys.
- Advance `next_run_at`.
- Apply misfire policy.
- Avoid duplicate scheduling across multiple backend instances.

Scheduling implementation:

- Store `next_run_at` in UTC.
- Store user-selected timezone on trigger.
- Use a cron parser that supports timezone-aware previews.
- Use DB row lock or advisory lock when claiming due triggers.
- Default poll interval: 30 seconds.
- Default misfire policy: `run_once`.

#### `StepRegistry`

Responsibilities:

- Register available workflow step types.
- Expose schemas for UI builder.
- Validate step config.
- Execute step handlers.
- Declare required permissions and budget categories.

Each step type should define:

- `type`
- `display_name`
- `description`
- `input_schema`
- `config_schema`
- `output_schema`
- `required_permissions`
- `supports_retry`
- `supports_test`
- `estimated_cost_kind`

#### `WorkflowArtifactsService`

Responsibilities:

- Persist generated outputs.
- Produce compact previews.
- Attach artifacts to run/step.
- Enforce access permissions.
- Redact sensitive content when needed.

#### `WorkflowEventsService`

Responsibilities:

- Append structured events.
- Provide paginated event query.
- Mirror important events to existing audit logs where appropriate.

### Runtime Strategy

Start with an in-process scheduler and runner backed by Postgres.

Rationale:

- Lower operational complexity.
- Enough for a product-native workflow engine.
- Existing platform already relies on backend services and DB state.
- Durable state lives in Postgres, so the process can restart safely.

Escalation path:

- Add Redis/RQ/Celery or a dedicated worker process only when run volume, long jobs, or horizontal scaling require it.
- Keep DB schema and state machine stable so the runner transport can change later.

### Concurrency

Workflow-level policy:

- `skip_if_running`: default for scheduled workflows.
- `queue_after_current`: enqueue but run sequentially.
- `allow_parallel`: allowed only for workflows marked safe.

Run claiming:

- Use `SELECT ... FOR UPDATE SKIP LOCKED` or equivalent SQLAlchemy transaction pattern.
- Set `locked_at` and `locked_by`.
- Treat stale locks as recoverable after a configured timeout.

Idempotency:

- Manual runs can accept an optional request idempotency key.
- Scheduled runs should use key format:
  - `schedule:{trigger_id}:{scheduled_at_iso}`
- API-triggered runs later should require explicit idempotency for retry-safe clients.

### Timezone and Schedule Semantics

Rules:

- Persist all run timestamps in UTC.
- Persist schedule timezone as IANA string.
- Compute `next_run_at` from cron plus timezone.
- Show schedule previews in the selected timezone and absolute UTC in debug metadata.
- Handle DST explicitly through preview. For ambiguous or nonexistent local times, use the cron library's documented behavior and surface preview to the user.

### Budget and Usage

Budget controls:

- Optional budget cap per workflow.
- Optional budget cap per run.
- Optional max tokens or model cost caps for agent/RAG steps where supported.
- Stop run before starting a step if remaining budget cannot cover configured hard limit.

Usage attribution:

- Attribute AI usage to workflow run and step where possible.
- Preserve existing user/API key attribution.
- Add workflow/run identifiers to usage metadata if existing usage schema allows.

### Permissions

Recommended permissions:

- `workflow:read`
- `workflow:create`
- `workflow:update`
- `workflow:delete`
- `workflow:execute`
- `workflow:disable`
- `workflow:manage`
- `workflow:approve` later

Step-level permission enforcement:

- Workflow author must have permission to configure a step.
- Workflow executor/schedule principal must have permission to run each step.
- Scheduled workflows should run as a stored owner/service principal with clear audit attribution.

### Audit

Audit these actions:

- Create workflow.
- Update draft.
- Publish version.
- Enable/disable/archive.
- Manual run requested.
- Schedule created/updated/disabled.
- Run cancelled.
- Run retried.
- Approval accepted/rejected later.

Audit entries should include:

- Workflow id/name.
- Version id/number.
- Run id if applicable.
- Acting user or system principal.
- Before/after state for lifecycle changes.
- Reason/comment when disabling or cancelling if provided.

### Security Boundaries

V1 must not support arbitrary code execution.

V1 should not allow users to paste raw secrets into workflow definitions. Workflows should reference existing connector credentials, API keys, or stored settings through IDs.

Sensitive fields:

- Redact prompt variables marked secret.
- Redact connector credentials.
- Redact API headers and tokens.
- Redact raw document content from logs unless explicitly permitted.

External calls:

- Webhook step should be post-MVP unless the platform already has a hardened outbound HTTP policy.
- If added, enforce allowlists, method restrictions, timeout, payload size, and redaction.

## Step Type Catalog

### MVP Step Types

#### `rag.query`

Purpose:

- Search or retrieve documents from a collection.

Config:

- `collection_id`
- `query`
- `filters`
- `limit`
- `since`: fixed timestamp, previous successful run, or trigger input.

Output:

- `documents`
- `count`
- `query_metadata`

#### `agent.run`

Purpose:

- Invoke a configured agent with input from previous steps.

Config:

- `agent_id`
- `prompt_template`
- `input_mapping`
- `model_override` only if existing agent permissions allow it.
- `max_tokens`

Output:

- `message`
- `tool_calls`
- `usage`
- `artifact_refs`

#### `notify.in_app`

Purpose:

- Create in-app notification for user/admin.

Config:

- `recipients`
- `title_template`
- `body_template`
- `severity`
- `artifact_refs`

Output:

- `notification_ids`

#### `condition.no_results_skip`

Purpose:

- Simple MVP condition for common "no new data" workflows without full branching.

Config:

- `input_step_key`
- `path`
- `operator`: `is_empty`, `equals`, `greater_than`
- `on_match`: `skip_remaining`, `continue`

Output:

- `matched`
- `action`

This gives useful conditional behavior without a full visual branching engine.

### Near-Term Step Types

#### `connector.sync`

Purpose:

- Run or wait for connector sync and return newly ingested records.

#### `extract.run_template`

Purpose:

- Run an Extract template over selected documents.

#### `artifact.create`

Purpose:

- Save text/JSON/file output as named artifact.

#### `budget.check`

Purpose:

- Explicit guardrail step for budget-sensitive workflows.

### Later Step Types

#### `approval.request`

Requires:

- Pause/resume support.
- Approval inbox UI.
- `workflow:approve`.

#### `webhook.call`

Requires:

- Outbound HTTP security policy.
- Secret management references.
- Response validation.

#### `workflow.run`

Requires:

- Nested workflow safety.
- Loop prevention.
- Cross-workflow budget attribution.

## API Plan

All frontend workflow product APIs should be internal authenticated APIs.

Base path:

- `/api-internal/v1/workflows`

### Workflow Definitions

```text
GET    /workflows
POST   /workflows
GET    /workflows/{workflow_id}
PATCH  /workflows/{workflow_id}
DELETE /workflows/{workflow_id}
POST   /workflows/{workflow_id}/archive
POST   /workflows/{workflow_id}/enable
POST   /workflows/{workflow_id}/disable
```

List filters:

- `status`
- `owner_user_id`
- `tag`
- `module`
- `q`
- `has_failures`
- `next_run_before`

### Versions and Drafts

```text
GET   /workflows/{workflow_id}/versions
POST  /workflows/{workflow_id}/draft
PATCH /workflows/{workflow_id}/draft
POST  /workflows/{workflow_id}/validate
POST  /workflows/{workflow_id}/publish
```

Publish behavior:

- Validate definition.
- Create immutable published version.
- Update `current_version_id`.
- Materialize trigger rows.
- Audit publish.

### Runs

```text
GET  /workflows/runs
GET  /workflows/runs/{run_id}
POST /workflows/{workflow_id}/runs
POST /workflows/runs/{run_id}/cancel
POST /workflows/runs/{run_id}/retry
POST /workflows/runs/{run_id}/retry-from-step/{step_key}
```

Run filters:

- `workflow_id`
- `status`
- `trigger_type`
- `created_after`
- `created_before`
- `q`

### Step Catalog

```text
GET /workflows/steps/catalog
GET /workflows/steps/catalog/{step_type}
POST /workflows/steps/validate
```

Used by builder for available step types, form schema, validation, labels, and required permissions.

### Scheduling

```text
POST /workflows/schedules/preview
GET  /workflows/schedules/upcoming
```

Preview request:

- cron
- timezone
- start time
- count

Upcoming response:

- workflow id/name
- trigger id
- scheduled time
- status/policy

### Artifacts and Events

```text
GET /workflows/runs/{run_id}/events
GET /workflows/runs/{run_id}/artifacts
GET /workflows/artifacts/{artifact_id}
```

## Frontend Implementation Plan

### Route and Structure

Add:

```text
frontend/src/app/workflows/page.tsx
frontend/src/components/workflows/
  WorkflowPage.tsx
  WorkflowOverview.tsx
  WorkflowList.tsx
  WorkflowDetail.tsx
  WorkflowRunTimeline.tsx
  WorkflowRunsTable.tsx
  WorkflowScheduleBoard.tsx
  WorkflowBuilder.tsx
  WorkflowStepList.tsx
  WorkflowStepCatalog.tsx
  WorkflowStepProperties.tsx
  WorkflowTemplatePicker.tsx
  WorkflowStatusBadge.tsx
  WorkflowRunActions.tsx
frontend/src/lib/api/workflows.ts
frontend/src/types/workflows.ts
```

### Page Behavior

On load:

- Fetch module status through existing module context.
- Fetch workflow summary list.
- Fetch recent runs and upcoming schedules.
- Select the first workflow with active failure, otherwise first active workflow, otherwise first workflow.

Primary controls:

- `New workflow`
- `Run now`
- `Refresh`
- `Disable/Enable`
- `Edit draft`

### API Client

Create a typed client in `frontend/src/lib/api/workflows.ts` that:

- Uses existing authenticated fetch pattern.
- Normalizes errors with existing frontend utilities.
- Provides typed functions for list/detail/run actions.
- Supports pagination and filters.

### Component Responsibilities

#### `WorkflowOverview`

- Owns tab state.
- Coordinates list/detail selection.
- Displays dashboard cards:
  - active workflows
  - runs today
  - failed runs
  - next scheduled run

#### `WorkflowList`

- Dense rows.
- Status icon/badge.
- Next run.
- Last run result.
- Search/filter controls.

#### `WorkflowDetail`

- Selected workflow summary.
- Current version.
- Trigger summary.
- Runtime policy.
- Recent runs.
- Latest artifacts.
- Primary actions.

#### `WorkflowBuilder`

- Draft editing only.
- Trigger configuration.
- Step sequence.
- Property panel.
- Validation summary.
- Save/publish actions.

#### `WorkflowRunTimeline`

- Step timeline with state icons.
- Retry affordances.
- Event stream.
- Artifact links.

#### `WorkflowScheduleBoard`

- Upcoming runs grouped by time.
- Schedule health indicators.
- Link back to workflow detail.

### UX Copy Principles

Use short operational labels:

- `Running`
- `Failed`
- `Next run`
- `Last success`
- `Retry`
- `Run now`
- `Disabled`
- `Budget cap`

Avoid visible instructional copy that explains the app. Use tooltips for unfamiliar icons and concise labels in empty states.

### Accessibility

Requirements:

- Keyboard accessible tabs, menus, dialogs, and action buttons.
- `aria-current` for selected nav/list items where appropriate.
- Status badges must not rely on color alone.
- Run timeline should be readable by screen readers in chronological order.
- Confirmation dialogs for destructive/expensive actions should focus correctly.

## Milestone Phases

### Phase 0: Product Contract and Technical Scaffold

Goal:

- Lock the MVP boundary and introduce code structure without changing behavior.

Tasks:

- Add this plan to project planning.
- Decide first templates:
  - Nightly RAG Summary.
  - Connector Intake Triage.
  - Weekly Extraction Report.
- Add workflow schemas with Pydantic validation only.
- Add service interfaces and empty step registry.
- Keep existing stub behavior working.

Acceptance:

- Existing module tests still pass.
- Workflow definition sample validates in unit tests.
- No new navigation item until route exists.

### Phase 1: Persistence, CRUD, Permissions, Audit

Goal:

- Users can create, edit, publish, enable/disable, and list workflow definitions.

Backend tasks:

- Add Alembic migration for workflow tables.
- Add SQLAlchemy models.
- Add Pydantic request/response schemas.
- Implement `WorkflowService` CRUD.
- Implement definition validation.
- Implement publish/version lifecycle.
- Add permission checks.
- Add audit hooks for lifecycle actions.
- Add internal workflow API router.

Frontend tasks:

- Add `/workflows` route.
- Add overview shell with list/detail empty state.
- Add create/edit draft basics.
- Add nav item only when module is enabled.

Acceptance:

- User can create a draft workflow.
- User can publish a valid workflow.
- User can enable and disable workflow.
- Audit records exist for create, update, publish, enable, disable.
- Invalid definitions show actionable validation errors.

### Phase 2: Manual Execution Engine

Goal:

- Users can run a published workflow manually and inspect the run.

Backend tasks:

- Implement `WorkflowRunner`.
- Implement run and step state transitions.
- Implement run creation endpoint.
- Implement run detail/events/artifacts endpoints.
- Implement MVP steps:
  - `rag.query`
  - `agent.run`
  - `notify.in_app`
  - `condition.no_results_skip`
- Implement basic retry policy.
- Add cancellation check between steps.
- Add budget cap check before AI steps.

Frontend tasks:

- Add `Run now`.
- Add run history table.
- Add run detail/timeline.
- Add artifact preview panel.
- Add retry failed run action.

Acceptance:

- User can run Nightly RAG Summary manually.
- Run persists after backend restart.
- Each step records status, input/output preview, timing, and errors.
- Failed step can be retried when the step supports retry.
- Budget cap prevents an expensive run before the next AI step starts.

### Phase 3: Scheduler and Operations Console

Goal:

- Scheduled workflows run reliably and the overview becomes operationally useful.

Backend tasks:

- Implement `WorkflowScheduler`.
- Add cron/timezone schedule validation.
- Add schedule preview endpoint.
- Add due trigger polling and queued run creation.
- Add idempotency keys for scheduled runs.
- Add misfire policies.
- Add concurrency policies.
- Add stale lock recovery.

Frontend tasks:

- Add schedule editor.
- Add next 5 run preview.
- Add schedule board/upcoming runs.
- Add health indicators for failed/missed/paused schedules.
- Make overview select failed workflows first.

Acceptance:

- A daily 02:00 workflow runs according to selected timezone.
- Duplicate runs are not created for the same scheduled fire time.
- If the backend restarts, due schedules recover according to misfire policy.
- User can see next run and last run from workflow list.
- User can disable a schedule and confirm it no longer enqueues runs.

### Phase 4: Builder UX, Templates, and Validation

Goal:

- Users can author the common workflows without editing JSON.

Backend tasks:

- Expose step catalog and JSON schemas.
- Add template definitions for MVP use cases.
- Add validation endpoint with per-step errors.
- Add optional isolated step test endpoint if safe.

Frontend tasks:

- Implement full Step Builder.
- Implement template picker.
- Implement step catalog panel.
- Implement property forms for MVP steps.
- Implement validation summary.
- Implement publish flow from draft.

Acceptance:

- User can create Nightly RAG Summary from template.
- User can configure schedule, RAG collection, agent, recipients, and budget.
- Builder prevents publishing with missing required fields.
- Builder shows step-level required permissions.

### Phase 5: Connector and Extract Integration

Goal:

- Workflows coordinate existing platform modules beyond RAG and Agent.

Backend tasks:

- Add `connector.sync` step.
- Add `extract.run_template` step.
- Add artifact handling for extraction output.
- Add per-step duration/timeout controls.
- Add richer usage attribution.

Frontend tasks:

- Add connector and extract step forms.
- Add extraction artifact views.
- Add module-specific run summaries.

Acceptance:

- Connector Intake Triage runs end to end.
- Weekly Extraction Report runs end to end.
- Connector failures appear in run detail with actionable errors.
- Extract outputs are linked as workflow artifacts.

### Phase 6: Advanced Control Flow

Goal:

- Add only the branching and approvals proven necessary by real workflows.

Backend tasks:

- Add condition branches.
- Add approval request step.
- Add pause/resume run support.
- Add approval API and permissions.
- Add API trigger skeleton if needed.

Frontend tasks:

- Add minimal branch UI.
- Add approval inbox or approval panel.
- Add paused run state.
- Add API trigger docs panel only after API trigger is implemented.

Acceptance:

- Workflow can pause for authorized approval.
- Approval/rejection is audited.
- Paused runs survive restart.
- Branch UI remains readable without a general canvas.

### Phase 7: Hardening, Scale, and Release Readiness

Goal:

- Make workflows dependable enough for production use.

Tasks:

- Add load tests for scheduled run creation.
- Add recovery tests for backend restart during run.
- Add migration rollback notes.
- Add retention policy for events/artifacts.
- Add admin metrics.
- Add E2E tests for core workflows.
- Add documentation for workflow concepts and troubleshooting.
- Evaluate whether to split runner/scheduler into worker process.

Acceptance:

- Scheduled and manual runs pass E2E in containers.
- Race-condition tests prove no duplicate scheduled run creation.
- Long-running jobs do not block API responsiveness.
- Admin can identify failing workflow patterns.

## MVP Boundary

### Include in First Useful Release

- `/workflows` route.
- Operations Console default view.
- Draft/publish lifecycle.
- Manual trigger.
- Schedule trigger.
- Linear step sequence.
- Step catalog.
- `rag.query`
- `agent.run`
- `notify.in_app`
- Simple no-results skip condition.
- Run history and run detail.
- Logs/events.
- Artifacts.
- Retry failed run.
- Disable/enable.
- Permissions.
- Audit.
- Budget cap.
- Timezone-aware schedule preview.

### Defer

- Arbitrary visual DAG/canvas.
- Loops.
- Nested workflows.
- Human approvals.
- External webhooks.
- API triggers.
- Marketplace-style workflow sharing.
- Arbitrary user code.
- Distributed worker pool.
- Complex per-step secret editing.

## Testing Strategy

### Backend Unit Tests

Cover:

- Workflow definition validation.
- Publish/version immutability.
- Permission enforcement.
- Schedule preview.
- Next-run calculation.
- Misfire policies.
- Idempotency key duplicate prevention.
- Run state transitions.
- Step registry validation.
- Retry behavior.
- Budget cap enforcement.
- Artifact redaction.

### Backend Integration Tests

Cover:

- CRUD lifecycle through internal API.
- Manual run end to end with mocked RAG/Agent.
- Scheduled due trigger creates exactly one run.
- Backend restart simulation with stale lock recovery.
- Failure path persists events/errors.
- Cancellation between steps.
- Audit records for lifecycle and run actions.

### Frontend Tests

Cover:

- Navigation shows Workflows only when enabled.
- Overview loading/empty/error states.
- Workflow list filtering.
- Run now confirmation.
- Disable confirmation.
- Builder validation errors.
- Schedule preview rendering.
- Run timeline states.
- Artifact preview.

### E2E/UAT

Core UAT scripts:

1. Create Nightly RAG Summary from template, publish, run manually, verify artifact.
2. Configure daily 02:00 schedule, preview next runs, enable, verify queued run when due.
3. Force RAG step failure, verify failed run and retry action.
4. Disable workflow, verify schedule no longer runs.
5. Edit workflow draft, publish version 2, verify old run still references version 1.

### Verification Commands

Backend:

```bash
sudo docker compose -f ../docker-compose.test.yml run --rm enclava-backend-test pytest
```

Frontend:

```bash
npm run check:colors
npm run check:plumbing
npm run lint
npm run build
```

Container verification after app implementation:

```bash
sudo docker compose up -d --build
sudo docker compose ps
```

Smoke checks:

- `/workflows` renders.
- `/api-internal/v1/workflows` requires auth.
- Workflow module appears enabled in settings/modules.
- Manual run writes a persisted run row.
- Scheduled run does not duplicate on refresh/restart.

## Rollout Plan

### Feature Flags

Add a config flag if the platform already has a feature flag convention:

- `WORKFLOWS_ENABLED=true`
- `WORKFLOW_SCHEDULER_ENABLED=true`

If no feature flag system exists, gate by module enablement and avoid showing navigation before the route is complete.

### Migration Safety

Rules:

- Add workflow tables without modifying existing RAG/Agent/Extract tables in early phases.
- Keep existing `workflow` module permissions compatible.
- Use nullable fields for future trigger types.
- Keep versioned definitions immutable after publish.
- Avoid deleting historical runs when workflows are archived.

### Backward Compatibility

The existing module endpoint behavior can remain for status and basic module smoke tests. Production workflow operations should move to dedicated internal APIs.

If plugins already reference `workflow:execute` or `workflow:read`, preserve those permission names and add finer-grained permissions rather than replacing them.

## Observability and Operations

Metrics:

- Active workflows.
- Queued/running/succeeded/failed runs.
- Runs by trigger type.
- Step duration percentiles.
- Failure rate by step type.
- Scheduler lag.
- Duplicate schedule prevention count.
- Budget blocked runs.

Admin views:

- Failed workflows in last 24 hours.
- Long-running workflows.
- Workflows disabled due to repeated failure.
- Top workflows by cost.

Alerts:

- Scheduler not polling.
- Queue lag above threshold.
- Repeated failures for same workflow.
- Stale running lock.

Retention:

- Keep workflow definitions and versions indefinitely unless archived/deleted by policy.
- Keep run metadata long term.
- Retain verbose events/logs for a configurable period.
- Retain artifacts according to artifact type and project data retention policy.

## Risks and Mitigations

### Risk: Workflow Engine Becomes Too Broad

Mitigation:

- Keep v1 linear and typed.
- Require concrete use cases before adding branches/loops/webhooks.
- Treat Step Registry as extension boundary.

### Risk: Scheduled Runs Duplicate

Mitigation:

- Use DB locks.
- Use idempotency keys per trigger fire time.
- Add concurrency tests.

### Risk: Users Cannot Tell What Happened

Mitigation:

- Run detail timeline is required in MVP.
- Persist step inputs/outputs/errors with redaction.
- Store artifacts separately with previews.

### Risk: Costs Become Unbounded

Mitigation:

- Workflow and run budget caps.
- Step timeout.
- Agent max token settings.
- Pre-step budget checks.

### Risk: Workflows Bypass Permissions

Mitigation:

- Check permissions at authoring and execution.
- Store execution principal.
- Audit all lifecycle and run actions.

### Risk: Builder Becomes Clunky

Mitigation:

- Default to operations console.
- Builder uses step list plus properties panel.
- Templates handle common cases.
- Avoid freeform canvas until branches are necessary.

## Open Product Decisions

1. Should scheduled workflows run as the workflow owner, as a system principal with owner attribution, or as a dedicated service account?
2. Should budget caps default on for all workflows, and what should the default cap be?
3. Which notification channels should MVP support: in-app only, email if available, or both?
4. Should artifacts be visible to all users with workflow read permission or only explicit recipients/owners?
5. Should failed scheduled workflows auto-disable after repeated failures?
6. Should workflow templates be editable seed definitions or fixed product presets?
7. Which exact timezone should the UI default to: browser timezone, user profile timezone, or UTC?

## Recommended Next Action

Convert this plan into a GSD milestone with phase artifacts:

1. Product/spec phase for MVP boundary and open decisions.
2. Backend persistence/API phase.
3. Manual execution phase.
4. Scheduler/operations UX phase.
5. Builder/templates phase.
6. Connector/extract integration phase.
7. Hardening/release phase.

The first implementation milestone should target the Nightly RAG Summary end to end because it proves the core value: schedule plus data checkpoint plus agent/RAG step plus artifact plus operational history.
