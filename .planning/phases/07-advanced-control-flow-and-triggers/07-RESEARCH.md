# Phase 7 Research: Advanced Control Flow and Triggers

## Implementation Findings

### Current runtime shape

- `WorkflowRuntimeService.execute_run()` currently iterates `definition.steps` in order and executes every step unless a handler returns `skip_remaining=True`.
- `condition.no_results_skip` is the only control-flow step. It skips all later steps and marks the whole run `skipped`.
- Step handlers already share `WorkflowStepResult`, `WorkflowStepContext`, `_resolve_path`, `_resolve_context_path`, and event/artifact result patterns.
- Targeted branching can be added by extending `WorkflowStepResult` with a list of later step keys to skip, then making `execute_run()` carry a `skipped_step_keys` set while it continues forward through the ordered list.
- This keeps Postgres as source of truth and avoids graph scheduling, dynamic jumps, loops, or a second engine.

### Branch config shape

- The builder and runtime both benefit from a flat config instead of nested graph edges:
  - `input_step_key`
  - `path`
  - `operator`
  - `value`
  - `matched_label`
  - `not_matched_label`
  - `matched_skip_step_keys`
  - `not_matched_skip_step_keys`
- Flat fields fit current registry schemas, validation path messages, and form update helpers in `WorkflowStepProperties.tsx`.
- Operators should stay small: `exists`, `empty`, `non_empty`, `equals`, `not_equals`, `contains`, `greater_than`, `greater_than_or_equal`, `less_than`, `less_than_or_equal`, `truthy`, and `falsy`.
- Publish validation must reject branch targets that are missing, refer to the branch itself, or refer to earlier steps.

### Builder impact

- The existing `WorkflowStepList` can display branch rows as standard step cards. It only needs optional compact metadata if useful.
- `WorkflowStepProperties` already has typed editors for `condition.no_results_skip`, connector, Extract, RAG, agent, and notification steps. Add `BranchConditionEditor` using the same layout.
- There is no dedicated multiselect primitive in the current workflow builder. A compact checkbox list of later steps is the safest target selector for branch skip targets.
- Keep `/workflows` operations-first; branch authoring only changes `/workflows/new` and `/workflows/[workflowId]/edit`.

### Run detail impact

- `WorkflowRunTimeline` already displays step status, events, artifacts, and bounded JSON output previews.
- Targeted branch skips should create skipped step rows with a reason so operators can see that a step was intentionally skipped by a branch.
- Branch step output can include matched state and selected path without adding a custom run-detail visualization in Plan 07-01.

## Validation Architecture

### Backend gates

- Unit tests must prove a matched branch skips only configured later steps while later unskipped steps still execute.
- Unit tests must prove a not-matched branch uses `not_matched_skip_step_keys`.
- Unit tests must prove branch targets are persisted as skipped step runs and branch events are present in run detail.
- Builder API validation tests must prove missing `input_step_key`, unknown operator, missing comparison value, missing target step, self-target, and earlier-step target return path-specific errors.
- Existing run API tests must keep passing.

### Frontend gates

- `npm run lint`
- `npm run check:colors`
- `npm run check:plumbing`
- `npm run build`
- Branch UI must avoid canvas or graph rendering and must not introduce direct client `fetch` outside `api-client.ts`.
- Branch editor text must remain short enough for mobile select triggers and buttons.

### Live gates

- Rebuild containers after implementation.
- Force-recreate nginx after rebuild.
- Smoke `/health` and `/workflows/new`.
- Authenticated smoke: branch catalog entry enabled and a filled branch definition validates through the Next workflow proxy.

## Risks

- Hidden workflow behavior: mitigated by persisted skipped step runs and branch events.
- Branch cycles: mitigated by validation that branch targets can only be later steps.
- UI clunkiness: mitigated by a typed branch editor inside the existing properties panel and no graph preview.
- Sensitive value exposure: mitigated by storing concise branch output and relying on existing redacted run detail serialization.

## Recommended Plan Split

- 07-01: Add minimal branch semantics and readable branch UI.
- 07-02: Add approval request step, pause/resume run state, approval permissions, and audit.
- 07-03: Add API/event trigger foundations with auth, idempotency, and docs surface.
