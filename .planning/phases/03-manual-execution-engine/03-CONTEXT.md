# Phase 3: Manual Execution Engine - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning
**Mode:** Autonomous smart discuss

<domain>
## Phase Boundary

Phase 3 makes published workflows manually runnable and inspectable. It adds durable run creation, safe run claiming, ordered step execution, persisted step state, events, artifacts, retry/cancel controls, redacted run detail, budget metadata, and a compact run timeline surface. It does not add scheduling, due-run polling, schedule preview, operations console navigation, builder UI, connector/extract steps, approvals, or external API/event triggers.

</domain>

<decisions>
## Implementation Decisions

### Runtime Persistence
- Keep Postgres as the source of truth for run state, continuing the Phase 2 model direction.
- Add a small additive migration only for runtime fields that Phase 2 intentionally left out: worker lock metadata, cancellation request metadata, retry ancestry, redaction policy, and budget/cost counters.
- Preserve `workflow_runs`, `workflow_step_runs`, `workflow_artifacts`, and `workflow_events` as the durable runtime surface. Do not create a separate job table.
- Store published version JSON snapshots as the execution source, not mutable drafts.

### Runner Semantics
- Manual run creation requires a visible workflow with a current published version. Disabled workflows may be run manually for test/operator use; archived workflows remain hidden unless explicitly requested by service internals.
- Claiming uses database row locking (`FOR UPDATE SKIP LOCKED` where supported) and short lock metadata so multiple backend processes cannot execute the same queued run.
- Execution is v1 linear order over the already-validated step list. Dependency graph expansion, parallel branches, loops, and approvals are deferred.
- A cancellation request should stop before the next step when possible and mark the run/remaining pending steps cancelled. It does not interrupt an in-flight provider call in Phase 3.
- Retry creates a new run from the same workflow version and links to the previous failed/cancelled run. Historical runs remain immutable enough for auditability.

### Step Semantics
- `rag.query` searches a RAG collection and returns document-like results. It must support injected/fake services in tests and use existing RAG service/module patterns in production.
- `condition.no_results_skip` can mark remaining downstream steps skipped when a configured previous output path is empty.
- `agent.run` invokes a configured agent or injected fake agent dependency, persists usage metadata where available, and stores a summary artifact.
- `notify.in_app` creates in-app notification records or uses the notification service when available; tests should not require real external delivery.

### API And UI
- Continue using dedicated internal workflow routes under `/api-internal/v1/workflows`.
- Add manual run, run detail, retry, cancel, and execute/claim support to the internal workflow router.
- Keep frontend work compact and direct-linkable. Do not add Workflows to primary navigation until Phase 4's operations console.
- Run detail should expose timeline, step state, events, artifacts, duration, redacted input/output, retry ancestry, cancellation status, and budget/cost metadata.

### Security, Budget, Redaction
- Reuse Phase 2 owner/admin/read/manage visibility. Manual run creation requires ownership/admin/manage, not just read.
- Persist redacted IO by default using the workflow runtime redaction policy. Strict redaction hides all step input/output payloads except safe summaries and artifact metadata.
- Budget checks are MVP guardrails: enforce `runtime.budget_limit_cents` against estimated cost before expensive steps where possible, and persist actual usage/cost metadata returned by agent/LLM paths. Deep global budget reconciliation remains owned by the existing LLM/budget services.

### The Agent's Discretion
- Choose exact helper class names and file layout based on existing `app.services.workflows` patterns.
- Prefer deterministic service-level tests with injected fake RAG/agent/notification dependencies over live provider calls.
- Add frontend only where needed for a coherent run timeline; avoid a full operations console.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/workflow.py` now defines workflow definition, version, trigger, run, step run, artifact, and event models.
- `backend/app/services/workflows/service.py` handles lifecycle CRUD, validation, publish, permission filtering, and audit logging.
- `backend/app/services/workflows/registry.py` defines the MVP step catalog: `rag.query`, `agent.run`, `notify.in_app`, and `condition.no_results_skip`.
- `backend/app/modules/agent/main.py` exposes agent chat helpers that can be reused or wrapped by an execution dependency.
- `backend/app/services/rag_service.py` and `backend/app/api/v1/rag.py` show RAG collection and search patterns.
- `backend/app/services/notification_service.py` and `backend/app/models/notification.py` define notification persistence/delivery behavior.
- `frontend/src/lib/api-client.ts`, `frontend/src/app/api/*/route.ts`, and existing pages/components show frontend fetch/proxy conventions.

### Established Patterns
- Backend focused tests run in Docker with `pytest --no-cov` because repository-wide coverage thresholds fail selected suites.
- Internal APIs depend on `get_db` and `get_current_user` and usually return `{"success": true, ...}` response envelopes.
- Backend formatting gates are `black --check` and `isort --check-only`.
- Frontend verification uses `npm run lint`, `npm run check:colors`, `npm run check:plumbing`, and `npm run build` when UI files change.

### Integration Points
- Add new runtime service modules under `backend/app/services/workflows/` instead of placing runner logic in the API router.
- Extend `backend/app/api/internal_v1/workflows.py` rather than adding another router prefix.
- Extend `backend/app/schemas/workflow.py` with run request/detail/timeline schemas.
- Add frontend API helpers and a direct run detail route only after backend detail responses are stable.

</code_context>

<specifics>
## Specific Ideas

- Keep manual run API ergonomic: `POST /api-internal/v1/workflows/{workflow_id}/runs` can create a queued run and optionally execute it immediately for the current backend process.
- Add a service method such as `execute_run(run_id)` for deterministic tests and future worker/scheduler use.
- Step result handlers should return a structured result with `output`, `artifacts`, `events`, `usage`, and `skip_remaining` rather than mutating DB directly.
- Run detail should be useful even if execution fails halfway through.

</specifics>

<deferred>
## Deferred Ideas

- Scheduler, due-run polling, schedule board, misfire policy enforcement, and concurrency policy enforcement are Phase 4.
- Workflow list/operations console navigation is Phase 4.
- Builder UI and template authoring are Phase 5.
- Connector sync and Extract step handlers are Phase 6.
- Branches, approvals, pause/resume, and API/event trigger foundations are Phase 7.

</deferred>
