---
phase: 06-connector-and-extract-integration
plan: "01"
status: completed
completed: 2026-07-05
commit: pending
---

# Plan 06-01 Summary: Connector Sync Workflow Step

## What Changed

Backend:

- Added `ConnectorWorkflowSyncResult` and `ConnectorSyncService.run_sync_for_workflow()` in `backend/app/services/connector_sync_service.py`.
- Preserved existing `ConnectorSyncService.run_sync(connector_id)` behavior for connector scheduler/API callers.
- Added workflow-safe connector document summaries with IDs, titles, source URLs, external IDs, index timestamps, counts, metadata, and bounded content previews.
- Added `ConnectorSyncHandler` for `connector.sync` in `backend/app/services/workflows/steps.py`.
- Enabled `connector.sync` in the authoritative step catalog with `connector_id`, `since`, and `max_records` config.
- Marked Connector Intake Triage as authorable and seeded `since`/`max_records` defaults.
- Kept Weekly Extraction Report unavailable until the Extract plan lands.

Frontend:

- Added typed `connectorApi.listConnectors()` in `frontend/src/lib/api-client.ts`.
- Loaded connector options in `WorkflowBuilder`.
- Added connector template seeding and default config/key mapping.
- Added a typed `ConnectorSyncEditor` with connector select, since mode, max records, and retry attempts.

Tests:

- Added `backend/tests/unit/services/test_workflow_connector_steps.py`.
- Updated builder API tests for connector-enabled and Extract-disabled Phase 6 boundary.

## Verification

- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_connector_steps.py tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_step_handlers.py tests/unit/services/test_workflow_run_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/services/connector_sync_service.py app/services/workflows/registry.py app/services/workflows/steps.py app/services/workflows/templates.py tests/unit/services/test_workflow_connector_steps.py tests/unit/services/test_workflow_builder_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/services/connector_sync_service.py app/services/workflows/registry.py app/services/workflows/steps.py app/services/workflows/templates.py tests/unit/services/test_workflow_connector_steps.py tests/unit/services/test_workflow_builder_api.py`
- `cd frontend && npm run lint`
- `cd frontend && npm run check:colors`
- `cd frontend && npm run check:plumbing`
- `cd frontend && npm run build`
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'`
- `sudo docker compose up -d --build`
- `sudo docker compose up -d --force-recreate enclava-nginx`
- `curl -fsS http://localhost:1080/health`
- `curl -fsSI 'http://localhost:1080/workflows/new?template=connector-intake-triage'`
- Authenticated live smoke: connector catalog enabled, Extract catalog disabled, Connector Intake template available through Next proxy, and filled Connector Intake definition validates.

## Notes

- Workflow connector output contains no raw or encrypted credentials.
- `run_sync_for_workflow()` leaves transaction commit ownership with the workflow runtime.
- Connector `since` is currently stored and surfaced in output; checkpoint behavior remains owned by the connector implementation.
- Extract remains blocked until Plan 06-02.
