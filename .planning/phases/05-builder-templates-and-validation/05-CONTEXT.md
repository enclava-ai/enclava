# Phase 5 Context: Builder, Templates, and Validation

## Current State

- Phase 4 completed a production Workflows route with Overview, Runs, Schedules, and Templates tabs.
- Backend workflow lifecycle APIs already support create, update, publish, enable, disable, archive, list, detail, run now, schedule preview, run detail, retry, cancel, scheduler status, operations rows, schedule board, and template summaries.
- `WorkflowService` already owns workflow definition validation, lifecycle persistence, audit logging, template lookup, and default step registry access.
- `create_default_step_registry()` already exposes MVP implemented step types: `rag.query`, `agent.run`, `notify.in_app`, and `condition.no_results_skip`.
- `templates.py` already seeds Nightly RAG Summary, Connector Intake Triage, and Weekly Extraction Report, but connector/extract execution remains Phase 6 scope.
- Frontend workflow code currently has operations components and an authenticated `/api/workflows` proxy, but no typed builder UI.

## Phase 5 Goal

Users can author common workflows without editing JSON.

## Locked Decisions

### D-01 Builder model
- Workflow authoring uses a linear trigger-plus-ordered-steps builder, not a canvas.
- The primary builder layout is: trigger strip at top, ordered step list in the center/left, properties panel on the right, validation/action bar at the bottom.

### D-02 Route posture
- `/workflows` remains operations-first.
- Builder entry points are `New workflow`, `Edit draft`, and template actions.
- Builder UI must not replace the Overview tab as the first screen.

### D-03 Validation ownership
- Backend validation remains authoritative.
- Frontend validation is a fast feedback layer that displays backend path/step errors; it must not silently publish a definition that backend validation rejects.

### D-04 Step catalog ownership
- The backend step registry is the source of truth for step type labels, descriptions, JSON config schema, output schema, required permissions, retry support, test support, cost kind, and availability.
- The frontend renders builder forms from known MVP step types plus the catalog metadata; it must not hard-code permission or availability truth independently.

### D-05 Template scope
- Nightly RAG Summary is the first end-to-end authoring template for Phase 5.
- Connector Intake Triage and Weekly Extraction Report remain visible as templates, but steps requiring `connector.sync` or `extract.run_template` must be marked unavailable until Phase 6 runtime support exists.

### D-06 Lifecycle and audit
- Draft save, publish, enable, and disable continue through `WorkflowService` lifecycle APIs.
- Phase 5 must not introduce a separate builder persistence path that bypasses audit or permission checks.

### D-07 Scheduling
- Schedule editing uses cron plus IANA timezone and the existing schedule preview service.
- The builder displays the next five preview times before publish or enable for scheduled workflows.

### D-08 UX density
- Builder UI should feel like an operational tool: compact, scannable, and form-driven.
- Use existing components (`Button`, `Input`, `Textarea`, `Select`, `Tabs`, `StatusBadge`, `ConfirmDialog`, `EmptyState`, `Card` only for individual repeated items) and semantic tokens.
- Avoid visible instructional text beyond concise labels, empty states, validation messages, and tooltips/titles.

## Requirements

- WF-UX-04: Workflow authoring uses a typed trigger-plus-ordered-steps builder with a properties panel and validation summary.
- WF-BUILD-01: The step registry exposes available step types, config schemas, input/output schemas, permissions, retry support, and cost hints to the frontend.
- WF-BUILD-02: Builder validates required trigger and step fields before publish and shows actionable per-step errors.
- WF-BUILD-03: Templates exist for Nightly RAG Summary, Connector Intake Triage, and Weekly Extraction Report.
- WF-BUILD-04: The first end-to-end template is Nightly RAG Summary with schedule, RAG query, no-results skip, agent summary, artifact, and notification behavior.

## Canonical References

### Planning
- `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md` - Workflow product definition, builder UX direction, APIs, and phase scope.
- `.planning/REQUIREMENTS.md` - v1.1 requirement IDs and traceability.
- `.planning/phases/04-scheduler-and-operations-console/04-VERIFICATION.md` - Current operations route and scheduler verification baseline.

### Backend
- `backend/app/schemas/workflow.py` - Pydantic domain contracts.
- `backend/app/services/workflows/service.py` - Lifecycle, validation, templates, catalog, permissions, audit.
- `backend/app/services/workflows/registry.py` - Step catalog source of truth.
- `backend/app/services/workflows/templates.py` - Template seed definitions.
- `backend/app/services/workflows/scheduler.py` - Schedule preview and next-run calculation.
- `backend/app/api/internal_v1/workflows.py` - Dedicated workflow API surface.
- `backend/tests/unit/services/test_workflow_api.py` - Lifecycle API test patterns.
- `backend/tests/unit/services/test_workflow_scheduler_api.py` - Schedule preview test patterns.

### Frontend
- `frontend/src/app/workflows/page.tsx` - Operations-first Workflows route.
- `frontend/src/app/api/workflows/route.ts` - Authenticated workflow proxy.
- `frontend/src/lib/api-client.ts` - Typed client and workflow API helpers.
- `frontend/src/components/workflows/WorkflowOperationsConsole.tsx` - Operations page patterns.
- `frontend/src/components/workflows/WorkflowScheduleBoard.tsx` - Schedule action and preview patterns.
- `frontend/src/components/ui/*` - Existing component library.

## Scope Fence

In scope:
- Step catalog and validation APIs for builder use.
- Builder routes/components for draft save, publish, enable, and validation.
- Template picker and Nightly RAG Summary authoring path.
- Disabled/coming-later treatment for connector/extract templates until Phase 6.

Out of scope:
- Canvas/DAG authoring.
- Branches, approvals, loops, external API/event triggers.
- Connector sync and Extract step runtime implementations.
- Distributed workers or scheduler architecture changes.

---
*Created: 2026-07-05*
