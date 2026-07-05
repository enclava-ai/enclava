---
status: clean
phase: 07-advanced-control-flow-and-triggers
depth: standard
files_reviewed: 42
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

## Plan 07-03 API/Event Trigger Foundations Review

### Additional Scope

- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/service.py`
- `backend/app/services/workflows/triggers.py`
- `backend/app/services/workflows/__init__.py`
- `backend/app/api/internal_v1/workflows.py`
- `backend/tests/unit/services/test_workflow_contracts.py`
- `backend/tests/unit/services/test_workflow_trigger_fire.py`
- `backend/tests/unit/services/test_workflow_trigger_api.py`
- `backend/tests/unit/services/test_workflow_builder_api.py`
- `frontend/src/app/api/workflows/route.ts`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/lib/api-client.ts`

### Result

No blocking bugs, security issues, or code quality findings remain at standard depth.

### Review Notes

- Trigger fire routes are authenticated internal APIs and continue to use the existing Next proxy for browser callers.
- API/event fire authorization is limited to workflow owners, admins, `workflow.manage`, or `workflow.trigger`.
- Idempotency is enforced per trigger, so two workflows can receive the same event key while duplicate retries for the same trigger return existing run metadata.
- Triggered runs use normal `workflow_runs`, `workflow_events`, audit rows, redaction policy, and budget metadata.
- Disabled/inactive workflows return skipped metadata instead of silently creating runs.
- Historical non-current version triggers are ignored so event/API fire responses do not include stale published versions.
- Builder support stays compact in the existing trigger panel and does not introduce webhook secrets, subscriptions, an event bus, or canvas UI.

### Verification Considered

- Backend contract, trigger service, trigger API, and builder API tests passed: 25 tests.
- Backend formatting and import checks passed.
- Frontend lint, color guard, plumbing guard, and production build passed.
- Live containers were rebuilt with `sudo docker compose up -d --build`, nginx was force-recreated, and live health/page/authenticated API/event trigger smokes passed.
