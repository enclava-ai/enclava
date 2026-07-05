# Plan 03-01 Summary: Runtime Persistence Core

## Completed

- Added additive workflow run runtime fields for retry ancestry, worker lock metadata, cancellation metadata, run redaction policy, and budget/cost counters.
- Added Alembic migration `035_workflow_run_runtime`.
- Added run, step run, artifact, event, redacted payload, and action schemas.
- Added `WorkflowRuntimeService` for manual run creation, queued-run claiming, run detail serialization, state transitions, event append, artifact creation, cancellation requests, audit records, duration calculation, and payload redaction.
- Exported runtime service errors and dependencies through `app.services.workflows`.
- Added runtime core tests for published-version snapshots, claim exclusivity, event/artifact persistence, cancellation, and redaction policies.

## Verification

- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_runtime.py tests/unit/services/test_workflow_lifecycle_service.py tests/unit/services/test_workflow_persistence.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test alembic upgrade head`
- Passed: backend `black --check` and `isort --check-only` on touched runtime files.

## Files Changed

- `backend/app/models/workflow.py`
- `backend/alembic/versions/035_add_workflow_run_runtime_fields.py`
- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/runtime.py`
- `backend/app/services/workflows/__init__.py`
- `backend/tests/unit/services/test_workflow_runtime.py`

## Notes

- Runtime detail reloads now use `populate_existing=True` so immediate API responses include newly persisted steps and artifacts after a run executes in the same session.

---
*Plan completed: 2026-07-05*
