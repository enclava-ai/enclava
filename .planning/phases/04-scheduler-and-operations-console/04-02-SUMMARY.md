# Plan 04-02 Summary: Operations Console

## Completed

- Added workflow operations schemas for health states, totals, workflow rows, and run summaries.
- Added `WorkflowOperationsService` for permission-scoped operations rows with owner, tags, trigger, next run, latest run, active run, latest failure, run counts, failure counts, cost totals, and budget metadata.
- Added internal operations APIs:
  - `GET /api-internal/v1/workflows/operations`
  - `GET /api-internal/v1/workflows/operations/recent-runs`
  - `GET /api-internal/v1/workflows/operations/failures`
- Added backend tests for empty state, visibility, run-now reflection, failed health, missed schedule health, and failure feeds.
- Added `/api/workflows` Next proxy for operations and run-now calls.
- Added nginx routing for `/api/workflows` so live browser traffic reaches the Next proxy instead of the backend `/api/` catch-all.
- Added typed frontend workflow operations client helpers.
- Added `/workflows` route with a health-first operations console, totals, filters, search, workflow table, latest-run links, empty template seeds, and row-level run-now action.
- Added `workflow` module navigation mapping so Workflows appears in the primary menu when the workflow module is enabled.

## Verification

- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_operations_api.py tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_api.py tests/unit/services/test_workflow_run_api.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/schemas/workflow.py app/services/workflows app/api/internal_v1/workflows.py tests/unit/services/test_workflow_operations_api.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/schemas/workflow.py app/services/workflows app/api/internal_v1/workflows.py tests/unit/services/test_workflow_operations_api.py`
- Passed: `cd frontend && npm run lint`
- Passed: `cd frontend && npm run check:colors`
- Passed: `cd frontend && npm run check:plumbing`
- Passed: `cd frontend && npm run build`

## Files Changed

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

## Notes

- The Workflows landing route is intentionally an operations console, not a builder. Builder entry points remain deferred to Phase 5.
- Run-now refetches operations data after a successful run and links the latest run to the existing `/workflows/runs/[runId]` detail page.
- Health states are derived from persisted workflow/run/trigger state so the console does not need special frontend-only status rules.
- Live smoke testing caught the nginx `/api/` catch-all before release; `/api/workflows` now mirrors the existing frontend API exceptions.

---
*Plan completed: 2026-07-05*
