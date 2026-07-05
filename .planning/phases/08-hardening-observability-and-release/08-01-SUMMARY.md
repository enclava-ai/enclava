---
phase: 08-hardening-observability-and-release
plan: "01"
status: completed
completed_at: "2026-07-05T23:54:00.000Z"
requirements: [WF-OBS-01, WF-REL-01]
---

# Phase 8 Plan 08-01 Summary

## Delivered

- Added `WorkflowMaintenanceService` for stale-lock recovery and retention maintenance.
- Added manage-only internal APIs for admin metrics, stale-lock recovery, and retention.
- Added scheduler stale-lock recovery before due-run creation and queue execution.
- Added admin metrics for scheduler lag, stale locks, long-running runs, run status counts, 24-hour failure rate, recent failures, and top workflows by cost.
- Added frontend API/proxy support and an optional compact admin metrics strip in the existing Operations Console.
- Added operator documentation at `docs/workflows/operations.md`.

## Safety Decisions

- Expired `running` locks are marked `failed` with a `run_stale_lock_recovered` event and audit record.
- Recovery does not re-enter the runner and does not create replacement runs, avoiding duplicate side effects from partially completed workflows.
- Retention deletes only old workflow events and clears old artifact payload/storage URI data; definitions, versions, runs, step runs, approvals, and audit logs remain durable.
- Admin metrics, retention, and stale recovery require admin/superuser or `workflow.manage`.

## Verification

- `pytest --no-cov -q tests/unit/services/test_workflow_maintenance.py tests/unit/services/test_workflow_operations_api.py tests/unit/services/test_workflow_scheduler.py` passed: 16 passed.
- Backend `black --check` passed for touched workflow files and tests.
- Backend `isort --check-only` passed for touched workflow files and tests.
- `npm run lint` passed.
- `npm run check:colors` passed.
- `npm run check:plumbing` passed.
- `npm run build` passed with the existing `NEXT_PUBLIC_BASE_URL not set in production` warning.
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'` passed.
- Rebuilt live containers with `sudo docker compose up -d --build`.
- Recreated nginx with `sudo docker compose up -d --force-recreate enclava-nginx`.
- Live smoke passed:
  - `curl -fsS http://localhost:1080/health`
  - `curl -fsSI http://localhost:1080/workflows`
  - Authenticated admin metrics endpoint returned scheduler/stale-lock/cost fields.
  - Authenticated stale-lock recovery returned a structured result.
  - Authenticated retention dry-run returned counts without deletion.

## Notes

- Docker storage was full during verification; stopped containers and build cache were pruned before rerunning tests and rebuilding.
- Phase 8 Plan 08-02 should broaden release coverage around backend, frontend, and E2E/UAT criteria.
