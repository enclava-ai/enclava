---
status: clean
phase: 07-advanced-control-flow-and-triggers
depth: standard
files_reviewed: 29
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
created: 2026-07-05
---

# Code Review: Phase 7 Advanced Control Flow and Triggers

## Scope

### Plan 07-01 Branch Control Step

- `backend/app/services/workflows/registry.py`
- `backend/app/services/workflows/service.py`
- `backend/app/services/workflows/steps.py`
- `backend/app/services/workflows/runtime.py`
- `backend/tests/unit/services/test_workflow_branch_steps.py`
- `backend/tests/unit/services/test_workflow_builder_api.py`
- `backend/tests/unit/services/test_workflow_run_api.py`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/components/workflows/WorkflowStepList.tsx`
- `frontend/src/components/workflows/WorkflowStepProperties.tsx`
- `frontend/src/components/workflows/WorkflowRunTimeline.tsx`

## Result

No blocking bugs, security issues, or code quality findings remain at standard depth.

## Review Notes

- Branch validation blocks unknown operators, missing value operands, unknown targets, self-targets, earlier targets, and duplicate target entries before publish.
- Runtime targeted skips create normal skipped step rows and `step_skipped` events with source branch and reason data.
- Existing `condition.no_results_skip` behavior remains compatible with the prior run-level skipped status path.
- Branch events and skip events avoid persisting the evaluated input value in event data.
- The builder UI remains linear and form-driven; no graph, connector, minimap, or canvas component was introduced.
- Branch target controls only list later steps and serialize target arrays in definition config.
- Run detail continues to use the existing bounded payload preview and now shows skipped step reasons inline.

## Verification Considered

- Backend branch, runtime, run API, and builder API tests passed.
- Backend formatting and import checks passed.
- Frontend lint, color guard, plumbing guard, and production build passed.
- Live containers were rebuilt with `sudo docker compose up -d --build`, nginx was force-recreated, and live health/page/authenticated branch smokes passed after the final UI change.

## Plan 07-02 Approval Pause/Resume Review

### Additional Scope

- `backend/alembic/versions/036_add_workflow_approvals.py`
- `backend/app/models/workflow.py`
- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/registry.py`
- `backend/app/services/workflows/service.py`
- `backend/app/services/workflows/steps.py`
- `backend/app/services/workflows/runtime.py`
- `backend/app/api/internal_v1/workflows.py`
- `backend/tests/unit/services/test_workflow_approval_steps.py`
- `backend/tests/unit/services/test_workflow_builder_api.py`
- `backend/tests/unit/services/test_workflow_run_api.py`
- `frontend/src/app/api/workflows/runs/[runId]/route.ts`
- `frontend/src/app/workflows/runs/[runId]/page.tsx`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/components/workflows/WorkflowRunTimeline.tsx`
- `frontend/src/components/workflows/WorkflowStepList.tsx`
- `frontend/src/components/workflows/WorkflowStepProperties.tsx`
- `frontend/src/lib/api-client.ts`

### Result

No blocking bugs, security issues, or code quality findings remain at standard depth.

### Review Notes

- Approval resolution is guarded by workflow ownership/admin, `workflow.manage`, `workflow.approve`, or explicit approver assignment.
- Approval records are durable and serialized directly on run detail, avoiding event-scraping in the UI.
- Approve resumes from a stored next-step index with persisted prior outputs, preventing earlier steps from re-running.
- Reject completes the workflow as `skipped` and persists skipped step rows for remaining ordered steps.
- Paused-run cancellation cancels pending approvals so stale approvals are not actionable.
- Review found one edge case: branch-targeted skips selected before an approval pause were initially in-memory only. Runtime now persists targeted skip state in pause metadata, and `test_approval_resume_preserves_prior_branch_skips` covers the interaction.

### Verification Considered

- Backend approval, runtime, run API, and builder API tests passed: 25 tests.
- Backend formatting and import checks passed.
- Frontend lint, color guard, plumbing guard, and production build passed.
- Live containers were rebuilt with `sudo docker compose up -d --build`, nginx was force-recreated, and live health/page/authenticated approval smokes passed.
