---
phase: 07-advanced-control-flow-and-triggers
plan: "01"
status: completed
completed: 2026-07-05
commit: pending
requirements-completed: [WF-UX-01, WF-RUN-03, WF-SEC-01, WF-SEC-02]
---

# Plan 07-01 Summary: Branch Control Step

## What Changed

Backend:

- Added `condition.branch` to the workflow step catalog as an enabled Control step.
- Added `BranchConditionHandler` with typed operators, prior-output path resolution, branch output, and `branch_evaluated` events.
- Added targeted skip support through `WorkflowStepResult.skip_step_keys` and `skip_reason`.
- Updated the runtime to persist skipped target steps as `WorkflowStepRunStatus.SKIPPED` rows with `step_skipped` events and branch source/reason data while continuing later unskipped steps.
- Added branch validation for required config, supported operators, required values, target arrays, target existence, target direction, self-targets, and duplicate target entries.
- Added runtime, validation, and run API coverage for branch execution and serialized run details.

Frontend:

- Added Branch defaults and stable step key generation in the workflow builder.
- Added a compact Branch properties editor inside the existing linear builder.
- Branch authoring supports source step/path, operator, conditional value, matched/not-matched labels, and later-step skip target checkboxes.
- Added compact Branch row metadata in the step list without introducing graph/canvas UI.
- Added inline skip reasons to existing run timeline skipped step rows, backed by persisted skip events.

## Commits

- `0acfa75` - `feat(07-01): add branch workflow runtime`
- `56677cf` - `feat(07-01): add branch builder editor`
- `6a90dcc` - `feat(07-01): show branch skip reasons`

## Verification

- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_branch_steps.py tests/unit/services/test_workflow_step_handlers.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_builder_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/services/workflows/registry.py app/services/workflows/service.py app/services/workflows/steps.py app/services/workflows/runtime.py tests/unit/services/test_workflow_branch_steps.py tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_run_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/services/workflows/registry.py app/services/workflows/service.py app/services/workflows/steps.py app/services/workflows/runtime.py tests/unit/services/test_workflow_branch_steps.py tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_run_api.py`
- `cd frontend && npm run lint`
- `cd frontend && npm run check:colors`
- `cd frontend && npm run check:plumbing`
- `cd frontend && npm run build`
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'`
- `sudo docker compose up -d --build`
- `sudo docker compose up -d --force-recreate enclava-nginx`
- `curl -fsS http://localhost:1080/health`
- `curl -fsSI http://localhost:1080/workflows/new`
- Authenticated live smoke: `condition.branch` catalog entry is enabled and a filled branch workflow definition validates through `/api/workflows`.

## Notes

- Branches are forward-only skip selectors over the existing ordered step list.
- Branch events intentionally omit the evaluated value to avoid leaking prior step output in events.
- Approval requests, pause/resume, API triggers, and event triggers remain deferred to later Phase 7 plans.
