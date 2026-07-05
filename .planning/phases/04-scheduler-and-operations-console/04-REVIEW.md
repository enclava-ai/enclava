---
status: clean
phase: 04-scheduler-and-operations-console
depth: standard
files_reviewed: 21
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
created: 2026-07-05
---

# Code Review: Phase 4 Scheduler and Operations Console

## Scope

### Plan 04-01 Scheduler Backend

- `backend/requirements.txt`
- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/scheduler.py`
- `backend/app/services/workflows/service.py`
- `backend/app/services/workflows/__init__.py`
- `backend/app/api/internal_v1/workflows.py`
- `backend/app/tasks/workflow_scheduler.py`
- `backend/app/main.py`
- `backend/tests/unit/services/test_workflow_scheduler.py`
- `backend/tests/unit/services/test_workflow_scheduler_api.py`

### Plan 04-02 Operations Console

- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/operations.py`
- `backend/app/services/workflows/__init__.py`
- `backend/app/api/internal_v1/workflows.py`
- `backend/tests/unit/services/test_workflow_operations_api.py`
- `frontend/src/components/ui/navigation.tsx`
- `frontend/src/lib/api-client.ts`
- `frontend/src/app/api/workflows/route.ts`
- `frontend/src/app/workflows/page.tsx`
- `frontend/src/components/workflows/WorkflowOperationsConsole.tsx`
- `nginx/nginx.conf`

## Result

No blocking bugs, security issues, or code quality findings remain at standard depth.

## Review Notes

- Preview API timestamps were changed during review to return timezone-aware UTC datetimes so frontend parsing does not reinterpret naive UTC as local time.
- Scheduled run creation checks idempotency before `skip_if_running`, preventing duplicate ticks from being mislabeled as concurrency skips.
- Scheduler tick APIs require workflow manage/admin-style access for manual execution.
- Due-run creation uses persisted trigger rows, row locks, and schedule idempotency keys; runtime execution still goes through `WorkflowRuntimeService.execute_run`.
- Operations rows reuse the same workflow visibility boundary as workflow lifecycle reads.
- The console derives health from persisted workflow/run/trigger state and blocks run-now for inactive workflows.
- The Workflows route is an operations console first; builder UX remains deferred to Phase 5.
- The live nginx `/api/` catch-all is bypassed for `/api/workflows`, matching the existing frontend API exception pattern.

## Verification Considered

- `pytest --no-cov -q tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_scheduler_api.py`
- `pytest --no-cov -q tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_scheduler_api.py tests/unit/services/test_workflow_runtime.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_lifecycle_service.py tests/unit/services/test_workflow_contracts.py`
- `pytest --no-cov -q tests/unit/services/test_workflow_operations_api.py tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_api.py tests/unit/services/test_workflow_run_api.py`
- `black --check` on touched backend workflow files and scheduler tests.
- `isort --check-only` on touched backend workflow files and scheduler tests.
- `npm run lint`
- `npm run check:colors`
- `npm run check:plumbing`
- `npm run build`
- Live smoke: `/workflows` returns 200 through nginx; `/api/workflows` reaches the Next proxy after the nginx route exception.
