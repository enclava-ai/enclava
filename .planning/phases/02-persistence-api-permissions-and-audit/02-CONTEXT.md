# Phase 2: Persistence, API, Permissions, and Audit - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning
**Mode:** Autonomous smart discuss

<domain>
## Phase Boundary

Phase 2 turns the Phase 1 workflow contracts into durable workflow definition lifecycle behavior. It covers database schema, SQLAlchemy models, lifecycle service methods, authenticated internal APIs, permission checks, and audit events for create, update, publish, enable, disable, archive, list, and detail. It does not execute workflow steps, schedule due runs, or build frontend workflow screens.

</domain>

<decisions>
## Implementation Decisions

### Persistence Shape
- Use the existing `workflow_definitions` table as the workflow lifecycle anchor because the consolidated migration already creates it in deployed databases.
- Add migration-forward tables for `workflow_versions`, `workflow_triggers`, `workflow_runs`, `workflow_step_runs`, `workflow_artifacts`, and `workflow_events` without dropping legacy `workflow_executions` or `workflow_step_logs`.
- Store published workflow versions as immutable JSON snapshots validated by `WorkflowDefinitionDocument`.
- Keep scheduler/runtime fields nullable and inert in Phase 2 so Phase 3 and Phase 4 can activate them without reworking lifecycle storage.

### Lifecycle Semantics
- Draft workflow definitions are mutable; published versions are immutable and version-numbered per workflow.
- `publish` validates the current draft, writes a new `WorkflowVersion`, updates the workflow's published pointer, and refreshes trigger rows from the version snapshot.
- `enable` requires a published version; `disable` and `archive` are lifecycle state changes only.
- Archive is soft-delete style behavior. No hard deletion API is part of Phase 2.

### API And Permissions
- Production workflow behavior uses dedicated internal routes under `/api-internal/v1/workflows`, not the generic module execute endpoint.
- Read operations require authenticated user context and return workflows owned by the user unless the user is admin/superuser.
- Mutating lifecycle actions require admin/superuser or explicit workflow manage permission.
- API responses should be stable JSON contracts that can support the Operations Console and future builder without exposing raw secrets.

### Audit
- Lifecycle actions write `audit_logs` records with resource type `workflow`, resource id, actor, old/new state where relevant, and action-specific details.
- Audit write failures must not silently corrupt lifecycle changes; use the existing transactional `log_audit_event` helper so workflow state and audit records commit together.
- Run-request audit is deferred to Phase 3 because Phase 2 does not create runs from user actions.

### the agent's Discretion
- Choose exact helper names and response schema layout based on existing FastAPI, SQLAlchemy, and test patterns.
- Add compatibility aliases only where they reduce risk with existing legacy workflow columns.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/schemas/workflow.py` contains Phase 1 Pydantic definition, trigger, runtime, step, catalog, and template contracts.
- `backend/app/services/workflows/service.py` is the current workflow service facade and should be extended rather than replaced.
- `backend/app/api/internal_v1/__init__.py` aggregates authenticated frontend/internal routers.
- `backend/app/services/audit_service.py` exposes `log_audit_event` for transactional audit writes.
- `backend/app/core/security.py` exposes `get_current_user`, role dictionaries, superuser flags, and permission lists.

### Established Patterns
- New backend features use SQLAlchemy models under `backend/app/models`, Alembic migration files under `backend/alembic/versions`, and async `AsyncSession` queries.
- Internal API endpoints usually depend on `get_db` and `get_current_user`, return `{"success": true, ...}` shapes, and use local helpers for admin checks when needed.
- Existing migrations are additive and tolerate live databases with previous columns/tables.
- Tests run in Docker with `pytest --no-cov` for focused suites because repository-wide coverage thresholds fail selected tests.

### Integration Points
- Add workflow models to `backend/app/models/__init__.py` so `Base.metadata.create_all` and imports register them.
- Include a new workflow router in `backend/app/api/internal_v1/__init__.py` with prefix `/workflows`.
- Keep `WorkflowModule` status/catalog/template behavior compatible; it can report persisted workflow counts once lifecycle service exists.

</code_context>

<specifics>
## Specific Ideas

- The first durable workflow can be created from the existing Nightly RAG Summary template after Phase 2 APIs exist.
- Existing legacy workflow tables in `000_consolidated_ground_truth_schema.py` should be treated as historical compatibility, not the final v1.1 runtime contract.
- Avoid a full permission framework rewrite; Phase 2 should enforce workflow permissions locally and leave broad RBAC improvements out of scope.

</specifics>

<deferred>
## Deferred Ideas

- Manual run creation, runner state transitions, retries, cancellation, budget checks, and step execution are Phase 3.
- Scheduler due-run creation, next-run calculation, misfire policy, and concurrency policy enforcement are Phase 4.
- Builder UI, workflow navigation, templates UI, and schedule preview UI are Phase 5.
- External API/event triggers and approvals are Phase 7.

</deferred>
