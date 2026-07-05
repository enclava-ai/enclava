# Phase 5 Pattern Map

## Backend Patterns

### Workflow APIs

- Analog: `backend/app/api/internal_v1/workflows.py`
- Pattern:
  - Router-level dependency injection with `get_db` and `get_current_user`.
  - Service exceptions mapped through `_map_service_error`.
  - Responses use `{"success": True, ...}` and `model_dump(mode="json")`.
  - Mutating lifecycle endpoints commit on success and roll back on mapped errors.

### Workflow service

- Analog: `backend/app/services/workflows/service.py`
- Pattern:
  - Public service methods do validation/permission/audit and return schema models.
  - `_require_manage` protects lifecycle mutations.
  - `validate_definition()` remains the Pydantic normalization boundary.
  - `validate_workflow_payload()` is the right place to extend API-friendly validation errors.

### Step registry

- Analog: `backend/app/services/workflows/registry.py`
- Pattern:
  - `StepRegistry` returns deep copies.
  - Default catalog is declared as data, not dynamic runtime discovery.
  - Catalog entries already carry config schema, output schema, permissions, retry support, test support, and cost kind.

### Tests

- Analogs:
  - `backend/tests/unit/services/test_workflow_api.py`
  - `backend/tests/unit/services/test_workflow_scheduler_api.py`
  - `backend/tests/unit/services/test_workflow_schedule_board_api.py`
- Pattern:
  - Use ASGI `AsyncClient` with dependency overrides.
  - Use `_actor()` style user dict helpers.
  - Assert response status plus serialized JSON fields.
  - Use fake runtime dependencies when testing run behavior.

## Frontend Patterns

### Workflow proxy

- Analog: `frontend/src/app/api/workflows/route.ts`
- Pattern:
  - Use `proxyAuthenticatedRequest`.
  - Forward Authorization and cookies.
  - Keep client components on `workflowApi`, not raw fetch.
  - Route by `resource` for GET and `action` for POST.

### Workflow tabs and operations

- Analogs:
  - `frontend/src/app/workflows/page.tsx`
  - `frontend/src/components/workflows/WorkflowOperationsConsole.tsx`
  - `frontend/src/components/workflows/WorkflowScheduleBoard.tsx`
- Pattern:
  - Components load through `workflowApi`.
  - Use `useToast` for action feedback.
  - Use existing table/card/status badge primitives.
  - Use compact, operational labels.

### Run detail

- Analog: `frontend/src/components/workflows/WorkflowRunTimeline.tsx`
- Pattern:
  - Keep timeline and artifacts compact.
  - Use formatted timestamps and redacted payload display.
  - Use icon actions with `sr-only` text.

### UI primitives

- Existing controls to reuse:
  - `Button`
  - `Input`
  - `Textarea`
  - `Select`
  - `Switch`
  - `Checkbox`
  - `Tabs`
  - `StatusBadge`
  - `EmptyState`
  - `ConfirmDialog`

## Planned New Files

- `frontend/src/app/workflows/new/page.tsx`
- `frontend/src/app/workflows/[workflowId]/edit/page.tsx`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/components/workflows/WorkflowStepList.tsx`
- `frontend/src/components/workflows/WorkflowStepProperties.tsx`
- `frontend/src/components/workflows/WorkflowValidationSummary.tsx`
- `frontend/src/components/workflows/WorkflowTemplatePicker.tsx`
- `backend/tests/unit/services/test_workflow_builder_api.py`
