# Phase 7: Advanced Control Flow and Triggers - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 adds only the advanced workflow behavior proven necessary by real use cases. Plan 07-01 is limited to minimal conditional branching and readable branch UI. It must preserve the existing typed linear builder and sequential runtime model; it must not introduce a canvas, graph scheduler, loops, nested workflows, arbitrary expressions, or a second workflow engine.

</domain>

<decisions>
## Implementation Decisions

### Branch Semantics

- Add a typed `condition.branch` step as the Phase 7 branching primitive, not a freeform DAG or canvas node system.
- Branches are binary for the first useful release: condition matched vs condition not matched.
- Branch conditions read prior workflow outputs through the existing step-key/path pattern used by `condition.no_results_skip` and notification templates.
- Supported operators should stay small and explainable: empty/non-empty, equals/not equals, contains, numeric comparison, and boolean truthiness.

### Runtime Behavior

- Keep execution forward-only and deterministic. A branch may skip configured later step keys or step groups; it may not jump backward, loop, or dynamically create steps.
- Extend runtime results with targeted skip metadata rather than replacing the ordered execution loop.
- Skipped branch steps should persist `WorkflowStepRun` rows with status `skipped`, events, and a clear skip reason so run detail remains auditable.
- Branch output should include the evaluated value, operator, matched state, selected path label, and skipped step keys.

### Builder UX

- Branch UI stays inside the current linear Step Builder: branch steps appear as ordinary rows with compact badges for matched path and target/skipped steps.
- Properties panel should expose source step, path, operator, comparison value when needed, true-path label, false-path label, and step targets through selects/multiselect-style controls.
- Validation messages remain backend-authored and path-specific; frontend UI only mirrors them and focuses the relevant branch step.
- No visible tutorial text, no graph preview, and no drag-only editing. Use concise labels and existing `Select`, `Input`, `StatusBadge`, and icon-button patterns.

### Validation and Governance

- Backend validation is authoritative for branch config, target step existence, target direction, and unsupported operators.
- Branch targets must refer only to later steps in the ordered definition to avoid cycles.
- Publish should fail if a branch references missing steps, earlier steps, itself, or malformed comparison values.
- Branch events and skipped step events must remain available in run detail and follow existing redaction behavior.

### Phase Sequencing

- Plan 07-01 delivers branch semantics and UI only.
- Human approvals, pause/resume states, approval audit, approval permissions, API triggers, event triggers, and external webhook semantics are deferred to Plans 07-02 and 07-03.
- Phase 7 must build on the existing workflow lifecycle, runtime, scheduler, operations console, builder, connector, and Extract step support without broad refactors.

### the agent's Discretion

The agent may choose the exact internal config shape if it remains typed, serializable in the existing workflow definition schema, easy to validate, and compatible with the current builder properties-panel model.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/app/schemas/workflow.py` defines the workflow document, step, retry, trigger, runtime policy, run status, and validation response contracts.
- `backend/app/services/workflows/runtime.py` owns the ordered execution loop, step runs, artifacts, events, retries, skip-remaining behavior, cancellation, budget checks, and run completion.
- `backend/app/services/workflows/steps.py` already has `condition.no_results_skip`, `_resolve_path`, `_resolve_context_path`, `WorkflowStepResult`, and `WorkflowStepEventSpec` patterns that branch behavior should extend.
- `backend/app/services/workflows/registry.py` is the authoritative step catalog for builder labels, schemas, permissions, cost hints, retry support, and enabled state.
- `backend/app/services/workflows/service.py` owns definition validation, catalog validation, template placeholder blocking, lifecycle operations, permissions, and audit logging.
- `frontend/src/components/workflows/WorkflowBuilder.tsx`, `WorkflowStepList.tsx`, `WorkflowStepProperties.tsx`, `WorkflowValidationSummary.tsx`, and `WorkflowRunTimeline.tsx` are the current builder/run-detail integration points.
- Existing UI primitives include `Button`, `Input`, `Textarea`, `Select`, `StatusBadge`, `ConfirmDialog`, semantic tokens, and lucide icons.

### Established Patterns

- Workflow authoring is a compact trigger-plus-ordered-steps builder, not a canvas.
- Backend validation is the source of truth; frontend validation displays backend path/step errors and blocks publish through service validation.
- Runtime step handlers return `WorkflowStepResult` with structured output, artifacts, events, cost, and skip metadata.
- Run detail renders persisted steps, events, artifacts, errors, and bounded JSON previews.
- Frontend API access routes through `apiClient` and the existing Next workflow proxy where needed.

### Integration Points

- Add a branch catalog entry in `create_default_step_registry()`.
- Add branch config validation in `WorkflowService._catalog_validation_errors()`.
- Add a `BranchConditionHandler` in `create_default_step_handlers()`.
- Extend `WorkflowStepResult` and `WorkflowRuntimeService.execute_run()` to track targeted step skips.
- Add branch config defaults and key generation in `WorkflowBuilder`.
- Add branch properties UI in `WorkflowStepProperties`.
- Update `WorkflowStepList` and/or `WorkflowRunTimeline` only where useful to make branch paths readable without turning the builder into a graph.

</code_context>

<specifics>
## Specific Ideas

- First real branch examples should cover practical workflow use cases: skip escalation if no high-priority connector items, notify only when Extract validation errors exist, or skip summarization when RAG results are empty.
- Keep branch copy operational and compact: `Input`, `Path`, `Operator`, `Value`, `When matched`, `When not matched`.
- Prefer explicit skipped target steps over implicit graph edges for Plan 07-01 because it fits the existing ordered runtime and UI.

</specifics>

<deferred>
## Deferred Ideas

- Visual DAG/canvas authoring.
- Multi-branch switch/case editors beyond binary matched/not matched behavior.
- Arbitrary expression language or user code execution.
- Loops, backward jumps, nested workflows, and dynamic step creation.
- Human approvals and pause/resume behavior until Plan 07-02.
- API/event trigger foundations until Plan 07-03.

</deferred>
