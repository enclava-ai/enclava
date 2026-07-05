# Plan 04-01 Summary: Scheduler Backend

## Completed

- Added `croniter` and scheduler contracts for schedule preview, due-run summaries, tick responses, and scheduler status.
- Validated schedule trigger cron expressions and IANA timezones through the workflow definition contract.
- Added durable schedule next-run calculation when schedule workflows are published/enabled.
- Implemented `WorkflowSchedulerService` for cron preview, due-trigger polling with row locks, idempotent scheduled run creation, misfire handling, concurrency policy enforcement, audit/events, and bounded queued-run execution.
- Added an in-process FastAPI lifespan scheduler task that starts/stops alongside the existing connector scheduler.
- Added internal APIs for schedule preview, scheduler status, and permission-protected manual scheduler ticks.
- Added scheduler service and API tests covering valid/invalid preview, `next_run_at`, idempotency, `skip_if_running`, `queue_after_current`, `skip`, `catch_up`, worker execution, and API permissions.

## Verification

- Passed: `sudo docker compose -f docker-compose.test.yml build enclava-backend-test`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_scheduler_api.py tests/unit/services/test_workflow_runtime.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_lifecycle_service.py tests/unit/services/test_workflow_contracts.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/schemas/workflow.py app/services/workflows app/api/internal_v1/workflows.py app/tasks/workflow_scheduler.py app/main.py tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_scheduler_api.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/schemas/workflow.py app/services/workflows app/api/internal_v1/workflows.py app/tasks/workflow_scheduler.py app/main.py tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_scheduler_api.py`

## Files Changed

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

## Notes

- Duplicate schedule ticks check idempotency before concurrency so an already-created fire time is reported as duplicate, not skipped because its queued run is active.
- Schedule previews return timezone-aware UTC timestamps for frontend-safe parsing, while persisted scheduler fields stay naive UTC per the existing database convention.
- `queue_after_current` and `allow_parallel` create queued scheduled runs even when other runs exist; `skip_if_running` skips only new fire times with no existing idempotent run.
- The scheduler worker uses the same `WorkflowRuntimeService.execute_run` path as manual execution, preserving run/step/event/artifact history semantics.

---
*Plan completed: 2026-07-05*
