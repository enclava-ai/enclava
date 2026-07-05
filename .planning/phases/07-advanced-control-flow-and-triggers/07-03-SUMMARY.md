---
phase: 07-advanced-control-flow-and-triggers
plan: "03"
status: completed
completed: 2026-07-05
commit: pending
requirements-completed: [WF-UX-01, WF-RUN-03, WF-SEC-01, WF-SEC-02]
---

# Plan 07-03 Summary: API and Event Trigger Foundations

## What Changed

Backend:

- Added `WorkflowTriggerFireRequest`, `WorkflowTriggerFireRunResult`, and `WorkflowTriggerFireResponse` contracts.
- Added service validation for API trigger `api_slug` and event trigger `event_name` so malformed trigger names appear through the existing builder validation response before publish.
- Added `WorkflowTriggerFireService` for authenticated API/event trigger firing.
- Trigger fire requests require caller-provided idempotency keys and derive per-trigger run keys such as `api:{trigger_id}:{key}` and `event:{trigger_id}:{key}`.
- API/event triggers create normal queued `WorkflowRun` rows with trigger id, trigger type, input payload, redaction policy, budget limit, run events, and audit logs.
- Duplicate idempotency keys return duplicate run metadata without creating another run.
- Disabled/inactive workflow triggers return skipped metadata without creating runs.
- Added optional synchronous `execute_now` support through the existing runtime service.
- Added authenticated internal fire endpoints:
  - `/api-internal/v1/workflows/triggers/api/{api_slug}/fire`
  - `/api-internal/v1/workflows/triggers/events/{event_name}/fire`

Frontend:

- Extended the workflow builder trigger selector with API and Event options.
- Added compact API slug and Event name inputs in the existing trigger panel.
- Updated trigger switching so schedule, API, event, and manual types clear irrelevant fields.
- Added Next proxy actions and typed API client helpers for firing API/event triggers without direct internal fetch plumbing.

## Verification

- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_contracts.py tests/unit/services/test_workflow_trigger_fire.py tests/unit/services/test_workflow_trigger_api.py tests/unit/services/test_workflow_builder_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/schemas/workflow.py app/services/workflows/service.py app/services/workflows/triggers.py app/services/workflows/__init__.py app/api/internal_v1/workflows.py tests/unit/services/test_workflow_contracts.py tests/unit/services/test_workflow_trigger_fire.py tests/unit/services/test_workflow_trigger_api.py tests/unit/services/test_workflow_builder_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/schemas/workflow.py app/services/workflows/service.py app/services/workflows/triggers.py app/services/workflows/__init__.py app/api/internal_v1/workflows.py tests/unit/services/test_workflow_contracts.py tests/unit/services/test_workflow_trigger_fire.py tests/unit/services/test_workflow_trigger_api.py tests/unit/services/test_workflow_builder_api.py`
- `cd frontend && npm run lint`
- `cd frontend && npm run check:colors`
- `cd frontend && npm run check:plumbing`
- `cd frontend && npm run build`
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'`
- `sudo docker compose up -d --build`
- `sudo docker compose up -d --force-recreate enclava-nginx`
- `curl -fsS http://localhost:1080/health`
- `curl -fsSI http://localhost:1080/workflows/new`
- Authenticated live smoke through `/api/workflows`: API trigger workflow created/published/enabled, first fire created one run, repeat idempotency key returned duplicate metadata, and event trigger fire created two matching workflow runs.

## Notes

- This intentionally does not add public unauthenticated webhooks, outbound webhook calls, external event subscriptions, or a general event bus.
- The first UX surface is deliberately small: trigger type plus the one required identifier field.
