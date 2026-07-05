---
status: clean
phase: 05-builder-templates-and-validation
depth: standard
files_reviewed: 19
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
created: 2026-07-05
---

# Code Review: Phase 5 Builder, Templates, and Validation

## Scope

### Plan 05-01 Catalog and Validation APIs

- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/registry.py`
- `backend/app/services/workflows/service.py`
- `backend/app/api/internal_v1/workflows.py`
- `backend/tests/unit/services/test_workflow_builder_api.py`
- `frontend/src/app/api/workflows/route.ts`
- `frontend/src/lib/api-client.ts`

### Plan 05-02 Builder UI and Lifecycle Actions

- `frontend/src/app/workflows/page.tsx`
- `frontend/src/app/workflows/new/page.tsx`
- `frontend/src/app/workflows/[workflowId]/edit/page.tsx`
- `frontend/src/app/api/workflows/route.ts`
- `frontend/src/lib/api-client.ts`
- `frontend/src/components/workflows/WorkflowOperationsConsole.tsx`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/components/workflows/WorkflowStepList.tsx`
- `frontend/src/components/workflows/WorkflowStepProperties.tsx`
- `frontend/src/components/workflows/WorkflowValidationSummary.tsx`

### Plan 05-03 Template-Assisted Nightly Authoring

- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/templates.py`
- `backend/app/services/workflows/service.py`
- `backend/app/services/workflows/operations.py`
- `backend/tests/unit/services/test_workflow_builder_api.py`
- `frontend/src/components/workflows/WorkflowTemplatePicker.tsx`
- `frontend/src/components/workflows/WorkflowTemplatesPanel.tsx`
- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/app/workflows/new/page.tsx`
- `frontend/src/app/workflows/[workflowId]/edit/page.tsx`
- `frontend/src/lib/api-client.ts`

## Result

No blocking bugs, security issues, or code quality findings remain at standard depth.

## Review Notes

- Backend validation remains authoritative; frontend gets typed helper methods but does not duplicate publish rules.
- Draft definitions may still contain disabled future steps, but `publish_definition` rejects them through registry-aware validation.
- Connector and Extract catalog entries are visible but disabled until Phase 6 runtime support.
- New frontend proxy resources preserve existing operations, runs, schedules, and template summary behavior.
- Builder lifecycle calls route through the existing Next proxy and internal workflow lifecycle APIs.
- Publish is guarded by backend validation before `publishWorkflow` can be called.
- Enable uses the existing confirmation dialog and requires an already published workflow version.
- Template availability is explicit: Nightly is authorable, connector/extract seeds stay visible but unavailable until Phase 6.
- Required seed placeholders are blocked without rejecting valid runtime prompt templates.
- The Nightly authoring path now has backend coverage for validation, publish, enable, and manual run creation.

## Verification Considered

- `pytest --no-cov -q tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_api.py tests/unit/services/test_workflow_contracts.py`
- `black --check app/schemas/workflow.py app/services/workflows app/api/internal_v1/workflows.py tests/unit/services/test_workflow_builder_api.py`
- `isort --check-only app/schemas/workflow.py app/services/workflows app/api/internal_v1/workflows.py tests/unit/services/test_workflow_builder_api.py`
- `npm run lint`
- `npm run check:colors`
- `npm run check:plumbing`
- `npm run build`
- `git diff --check`
- `sudo docker compose up -d --build`
- `curl -fsS http://localhost:1080/health`
- `curl -fsSI http://localhost:1080/workflows/new`
- Authenticated workflow proxy smoke checks for catalog, validation, schedule preview, and missing-id publish guard.
- Authenticated template smoke checks for Nightly metadata, unavailable future templates, raw placeholder rejection, filled Nightly validation, and five-run schedule preview.
