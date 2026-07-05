# Phase 7 Pattern Map

## Backend Patterns

### Runtime ordered execution

- Analog: `backend/app/services/workflows/runtime.py`
- Pattern:
  - `execute_run()` owns the ordered step loop and run completion.
  - `_execute_step_with_retries()` creates a running `WorkflowStepRun`, builds `WorkflowStepContext`, checks budget, invokes the handler, and persists output.
  - `_mark_remaining_steps_skipped()` shows the current style for persisted skipped step rows and `step_skipped` events.
  - New targeted skip behavior should reuse the same event/status vocabulary instead of adding a new run state.

### Step handlers

- Analog: `backend/app/services/workflows/steps.py`
- Pattern:
  - Handlers are small classes registered in `create_default_step_handlers()`.
  - Config values use `_render_value`, `_resolve_path`, and `_resolve_context_path`.
  - Handler failures raise `WorkflowStepExecutionError`.
  - Handler success returns `WorkflowStepResult` with structured output and events.

### Catalog and validation

- Analogs:
  - `backend/app/services/workflows/registry.py`
  - `backend/app/services/workflows/service.py`
- Pattern:
  - Catalog entries are declared as data in `create_default_step_registry()`.
  - `WorkflowService._catalog_validation_errors()` adds registry-aware errors beyond Pydantic validation.
  - Specialized validation helpers exist for connector and Extract config; branch validation should follow that shape.

### Tests

- Analogs:
  - `backend/tests/unit/services/test_workflow_step_handlers.py`
  - `backend/tests/unit/services/test_workflow_run_api.py`
  - `backend/tests/unit/services/test_workflow_builder_api.py`
- Pattern:
  - Use fake services and `_queued_run()` helpers for runtime behavior.
  - Assert serialized `WorkflowRunStatus`, `WorkflowStepRunStatus`, outputs, artifacts, and event types.
  - Builder validation tests use API/service validation response paths and exact codes.

## Frontend Patterns

### Builder state and step defaults

- Analog: `frontend/src/components/workflows/WorkflowBuilder.tsx`
- Pattern:
  - Step defaults are centralized in `defaultConfigForType()`.
  - Template seeding is centralized in `seedStepFromTemplate()`.
  - Step keys are generated through `nextStepKey()`.
  - Step property updates are local until validation/save/publish routes serialize the definition.

### Step list

- Analog: `frontend/src/components/workflows/WorkflowStepList.tsx`
- Pattern:
  - Step rows are compact cards, selected with `border-primary bg-accent-soft`.
  - Row metadata uses small text and `StatusBadge`.
  - Move/remove controls are icon buttons with `title` and `sr-only` text.

### Properties panel

- Analog: `frontend/src/components/workflows/WorkflowStepProperties.tsx`
- Pattern:
  - One typed editor per known step type.
  - Shared helpers handle select empty values, optional numbers, field errors, and retry attempts.
  - Previous-step options are derived from `allSteps.slice(0, stepIndex)`.
  - Branch target options should be derived from `allSteps.slice(stepIndex + 1)`.

## Planned New Symbols

- `BranchConditionHandler`
- `WorkflowStepResult.skip_step_keys`
- `WorkflowStepResult.skip_reason`
- `_evaluate_branch_condition`
- `_compare_branch_values`
- `_branch_step_validation_errors`
- `_append_invalid_config_error`
- `BranchConditionEditor`
- `normalizeBranchTargets`
- `toggleBranchTarget`
- `backend/tests/unit/services/test_workflow_branch_steps.py`
