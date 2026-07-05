# Plan 02-03 Summary: Internal Workflow APIs and Audit Integration

## Completed

- Added internal workflow router at `backend/app/api/internal_v1/workflows.py`.
- Registered the router under `/api-internal/v1/workflows`.
- Added authenticated endpoints for catalog, templates, validation, list, create, detail, update, publish, enable, disable, and archive.
- Mapped workflow service errors to stable HTTP statuses for not found, permission denied, and validation failures.
- Kept catalog/templates behavior backed by the Phase 1 workflow service facade.
- Extended the workflow module status action to include persisted workflow counts when a database session is supplied.
- Added API tests for lifecycle endpoint flow, validation/catalog responses, archive hiding, permission failure, and lifecycle audit rows.

## Verification

- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_api.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_persistence.py tests/unit/services/test_workflow_lifecycle_service.py tests/unit/services/test_workflow_api.py tests/unit/services/test_workflow_contracts.py tests/test_modules.py::TestModuleIntegration::test_module_dependencies tests/test_modules.py::TestModuleAPI::test_modules_api_response_structure`
- Passed: backend `black --check` and `isort --check-only` on touched workflow files.

## Files Changed

- `backend/app/api/internal_v1/workflows.py`
- `backend/app/api/internal_v1/__init__.py`
- `backend/app/modules/workflow/main.py`
- `backend/tests/unit/services/test_workflow_api.py`

## Notes

- These APIs prepare the future Workflows UI and runner phases. They do not execute workflow steps or schedule due runs yet.

---
*Plan completed: 2026-07-05*
