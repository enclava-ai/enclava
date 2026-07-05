---
phase: 05-builder-templates-and-validation
plan: "01"
status: completed
completed: 2026-07-05
requirements: [WF-UX-04, WF-BUILD-01, WF-BUILD-02, WF-BUILD-03]
---

# Plan 05-01 Summary: Catalog and Validation APIs

## Outcome

Builder-ready catalog, template detail, and validation APIs are now available. Backend validation is registry-aware, and publish blocks unsupported or disabled future step types.

## Implemented

- Added catalog availability metadata: `category`, `enabled`, and `disabled_reason`.
- Added disabled catalog entries for `connector.sync` and `extract.run_template` so future templates can be visible without being publishable.
- Added typed validation errors with `path`, `message`, `severity`, `code`, `step_key`, and `step_index`.
- Extended `WorkflowService.validate_workflow_payload` to report unknown step types, disabled step types, and missing required config fields from catalog schemas.
- Added internal builder endpoints:
  - `GET /api-internal/v1/workflows/steps/catalog`
  - `GET /api-internal/v1/workflows/steps/catalog/{step_type}`
  - `POST /api-internal/v1/workflows/steps/validate`
  - `GET /api-internal/v1/workflows/templates/{template_id}`
- Added frontend proxy resources and typed `workflowApi` helpers for catalog, template detail/catalog, and definition validation.
- Added backend tests for catalog availability, template detail, validation errors, and disabled-template publish blocking.

## Verification

- `pytest --no-cov -q tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_api.py tests/unit/services/test_workflow_contracts.py` passed: 14 tests.
- `black --check` passed for touched workflow backend files and tests.
- `isort --check-only` passed for touched workflow backend files and tests.
- `npm run lint` passed.
- `npm run check:colors` passed.
- `npm run check:plumbing` passed.
- `npm run build` passed.
- `git diff --check` passed for touched files.

## Notes

- Draft save remains permissive enough for future disabled templates; publish is strict.
- Connector and Extract templates can stay discoverable in Phase 5 while execution waits for Phase 6 step handlers.
