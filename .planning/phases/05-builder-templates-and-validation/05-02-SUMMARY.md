---
phase: 05-builder-templates-and-validation
plan: "02"
status: completed
completed: 2026-07-05
requirements: [WF-UX-04, WF-BUILD-01, WF-BUILD-02]
---

# Plan 05-02 Summary: Builder UI and Lifecycle Actions

## Outcome

Users can now open a protected workflow builder, configure trigger/runtime fields, manage an ordered step sequence, edit typed step properties, validate drafts, save drafts, publish, enable, and run a test when the workflow is active.

## Implemented

- Added protected builder routes:
  - `/workflows/new`
  - `/workflows/[workflowId]/edit`
- Kept `/workflows` operations-first and added a compact `New workflow` entry plus row-level edit actions.
- Extended the Next workflow proxy and `workflowApi` with detail, create, update, publish, enable/disable typed responses, and unsaved schedule preview.
- Added `WorkflowBuilder` with:
  - metadata controls for name, description, and tags.
  - manual/schedule trigger controls with cron, timezone, misfire policy, and explicit preview.
  - runtime policy controls for concurrency, timeout, budget, and redaction.
  - sticky bottom action bar for validation, save draft, publish, enable, and run test.
- Added ordered `WorkflowStepList` with select, add, remove, move up/down, retry/permission metadata, and validation counts.
- Added `WorkflowStepProperties` typed editors for:
  - `rag.query`
  - `condition.no_results_skip`
  - `agent.run`
  - `notify.in_app`
- Added `WorkflowValidationSummary` to group backend validation errors and focus the matching step.
- Publish calls backend validation first and does not call publish when blocking validation errors are returned.
- Enable uses the existing confirmation dialog and requires an existing published version.

## Verification

- `npm run lint` passed.
- `npm run check:colors` passed.
- `npm run check:plumbing` passed.
- `npm run build` passed.
- `git diff --check` passed for touched tracked files.
- `sudo docker compose up -d --build` rebuilt backend, frontend, and migrate images.
- `sudo docker compose up -d --force-recreate enclava-nginx` recreated the public proxy.
- `curl -fsS http://localhost:1080/health` returned healthy.
- `curl -fsSI http://localhost:1080/workflows/new` returned `200 OK`.
- Authenticated proxy smoke checks passed for step catalog, builder validation, unsaved schedule preview, and missing-`workflow_id` publish guard.
- Migrations remained at `035_workflow_run_runtime (head)`.

## Notes

- `npx tsc --noEmit` is not currently a reliable project gate: it is blocked by existing repo-wide TypeScript issues including Next 16 route-handler validator mismatches, missing test-runner globals, and plugin/auth type errors. The required lint, plumbing, color, production build, and live smoke gates passed.
- Save draft remains permissive for incomplete required step config so users can draft progressively; publish remains backend-authoritative and blocking.
