---
phase: 07-advanced-control-flow-and-triggers
plan: "02"
status: completed
completed: 2026-07-05
commit: pending
requirements-completed: [WF-UX-01, WF-RUN-03, WF-SEC-01, WF-SEC-02]
---

# Plan 07-02 Summary: Approval Pause and Resume

## What Changed

Backend:

- Added durable `workflow_approvals` persistence with approval status, prompt content, approver user ids, resolution comments, resolver, and timestamps.
- Added `WorkflowApprovalStatus`, `WorkflowApprovalSummary`, and `WorkflowApprovalAction` API contracts.
- Added enabled `approval.request` step catalog metadata and `ApprovalRequestHandler`.
- Extended workflow run detail serialization with first-class `approvals`.
- Added runtime pause/resume semantics for approval requests:
  - approval steps pause runs as `paused`;
  - approve resolves the pending approval and resumes from the stored next step index;
  - reject resolves the pending approval, skips remaining steps, and completes the run as `skipped`;
  - cancellation of paused runs cancels pending approvals.
- Added approval authorization for admins, workflow owners, `workflow.manage`, `workflow.approve`, and explicitly assigned approvers.
- Persisted targeted branch skip state across approval pauses so branches before approvals still skip intended later steps after resume.
- Added internal API endpoints for `/runs/{run_id}/approve` and `/runs/{run_id}/reject`.
- Added runtime, builder validation, and run API coverage for approval pause/resume, rejection, permissions, cancellation, serialization, and branch/approval interaction.

Frontend:

- Added Approval Request defaults and step key generation in the Step Builder.
- Added compact Approval properties editor for title/body templates, approver user ids, requester self-approval, and approve/reject labels.
- Added Approval step row metadata in the existing linear step list.
- Extended the Next workflow run proxy and API client with `approve` and `reject` actions.
- Added run-detail approval rendering and Approve/Reject controls for paused runs.

## Verification

- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_approval_steps.py tests/unit/services/test_workflow_runtime.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_builder_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/models/workflow.py app/schemas/workflow.py app/services/workflows/registry.py app/services/workflows/service.py app/services/workflows/steps.py app/services/workflows/runtime.py app/api/internal_v1/workflows.py tests/unit/services/test_workflow_approval_steps.py tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_run_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/models/workflow.py app/schemas/workflow.py app/services/workflows/registry.py app/services/workflows/service.py app/services/workflows/steps.py app/services/workflows/runtime.py app/api/internal_v1/workflows.py tests/unit/services/test_workflow_approval_steps.py tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_run_api.py`
- `cd frontend && npm run lint`
- `cd frontend && npm run check:colors`
- `cd frontend && npm run check:plumbing`
- `cd frontend && npm run build`
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'`
- `sudo docker compose up -d --build`
- `sudo docker compose up -d --force-recreate enclava-nginx`
- `curl -fsS http://localhost:1080/health`
- `curl -fsSI http://localhost:1080/workflows/new`
- Authenticated live smoke through `/api/workflows`: approval catalog enabled, approval definition validates, workflow creates/publishes, one run approves to `succeeded`, and one run rejects to `skipped`.

## Notes

- Approval rejection is modeled as an explicit skipped workflow outcome, not a technical failure.
- Approval prompt content is stored on the approval record and surfaced in run detail; events carry concise approval ids/status metadata.
- API/event trigger foundations remain deferred to Plan 07-03.
