---
status: clean
phase: 06-connector-and-extract-integration
depth: standard
files_reviewed: 9
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
created: 2026-07-05
---

# Code Review: Phase 6 Connector Integration

## Scope

### Plan 06-01 Connector Sync Workflow Step

- `backend/app/services/connector_sync_service.py`
- `backend/app/services/workflows/registry.py`
- `backend/app/services/workflows/steps.py`
- `backend/app/services/workflows/templates.py`
- `backend/tests/unit/services/test_workflow_connector_steps.py`
- `backend/tests/unit/services/test_workflow_builder_api.py`
- `frontend/src/lib/api-client.ts`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/components/workflows/WorkflowStepProperties.tsx`

## Result

No blocking bugs, security issues, or code quality findings remain at standard depth.

## Review Notes

- Existing connector scheduler/API behavior still calls `run_sync(connector_id)` with the same public signature.
- Workflow execution uses `run_sync_for_workflow()` so connector sync changes and workflow run state commit together under the runtime transaction.
- Workflow output serializes connector job status as plain strings and omits credential fields.
- Connector step config references connector IDs only.
- Connector sync failures raise `WorkflowStepExecutionError`, which existing runtime code persists on the failed step and run.
- Builder authoring loads connector options through the typed API client and stores only `connector_id`, `since`, and `max_records`.
- Connector Intake Triage is available; Weekly Extraction Report remains unavailable until Extract support lands.

## Verification Considered

- Backend connector workflow tests and existing workflow runtime tests passed.
- Backend formatting and import checks passed.
- Frontend lint, color guard, plumbing guard, and production build passed.
- Live containers were rebuilt with `sudo docker compose up -d --build`, nginx was force-recreated, and live health/page/authenticated workflow smokes passed.
