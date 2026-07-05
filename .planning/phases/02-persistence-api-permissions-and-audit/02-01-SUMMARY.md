# Plan 02-01 Summary: Workflow Persistence Models

## Completed

- Added `backend/app/models/workflow.py` with durable workflow definitions, versions, triggers, runs, step runs, artifacts, and events.
- Preserved the legacy `workflow_definitions` table shape by mapping existing columns and adding lifecycle fields additively.
- Added minimal legacy mappings for `workflow_executions` and `workflow_step_logs` so test metadata ordering remains compatible with existing foreign keys.
- Added Alembic migration `034_add_workflow_lifecycle` to extend workflow storage without dropping legacy workflow tables.
- Registered workflow models through `backend/app/models/__init__.py`.
- Added focused persistence tests for definition/version/trigger relationships and immutable version snapshots.

## Verification

- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_persistence.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test alembic upgrade head`
- Included in final focused suite: 21 passed.

## Files Changed

- `backend/app/models/workflow.py`
- `backend/app/models/__init__.py`
- `backend/alembic/versions/034_add_workflow_lifecycle.py`
- `backend/tests/unit/services/test_workflow_persistence.py`

## Notes

- Runtime behavior is still inert in this plan. Run execution, scheduling, and worker claiming are intentionally deferred to later phases.

---
*Plan completed: 2026-07-05*
