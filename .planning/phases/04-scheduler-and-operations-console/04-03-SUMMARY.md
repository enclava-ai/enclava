---
phase: 04-scheduler-and-operations-console
plan: "03"
status: completed
completed: 2026-07-05
requirements: [WF-UX-05, WF-SCHED-01, WF-SCHED-03, WF-SCHED-04, WF-SEC-02]
---

# Plan 04-03 Summary: Schedule Board and Controls

## Outcome

Phase 4 now has a complete operations surface for scheduled workflows. The Workflows page exposes Overview, Runs, Schedules, and Templates tabs; scheduled workflows can be reviewed, previewed, enabled, disabled, run manually, retried, and opened from operations views.

## Implemented

- Added schedule board schemas and backend operations APIs for schedule groups, schedule health, upcoming fire times, recent run filters, and template summaries.
- Added existing workflow schedule preview endpoint using the persisted current schedule trigger.
- Extended the frontend workflow API proxy and typed client helpers for runs, schedules, templates, lifecycle actions, and schedule preview.
- Added Workflows page tabs:
  - Overview: existing operations console.
  - Runs: recent run history with workflow/status filters and retry/open actions.
  - Schedules: schedule board with health, next run, preview, enable/disable, run-now, and latest-run actions.
  - Templates: compact template summaries.
- Added tests covering schedule board grouping, disabled health, lifecycle audit records, run filters, and template summaries.

## Verification

- `pytest --no-cov -q tests/unit/services/test_workflow_schedule_board_api.py` passed: 4 tests.
- `pytest --no-cov -q tests/unit/services/test_workflow_schedule_board_api.py tests/unit/services/test_workflow_operations_api.py tests/unit/services/test_workflow_scheduler_api.py tests/unit/services/test_workflow_scheduler.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_api.py` passed: 25 tests.
- Backend formatting checks passed with `black --check` and `isort --check-only`.
- Frontend checks passed: `npm run lint`, `npm run check:colors`, `npm run check:plumbing`, and `npm run build`.
- `git diff --check` passed for touched workflow files.

## Notes

- Enable/disable actions reuse lifecycle APIs, so audit behavior stays centralized.
- Schedule board visibility uses the same workflow visibility boundary as the operations summary.
- The board intentionally remains table-first and health-first; freeform workflow building remains Phase 5 scope.
