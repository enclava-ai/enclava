# Plan 01-01 Summary: Workflow Domain Contracts

## Completed

- Added shared workflow Pydantic contracts in `backend/app/schemas/workflow.py`.
- Added workflow lifecycle, trigger, run, step run, concurrency, misfire, and redaction enums.
- Added runtime policy, retry policy, trigger definition, step definition, workflow definition, step catalog, and template models.
- Added validation for schedule trigger required fields, namespaced step types, stable step keys, duplicate step keys, and v1 linear dependency order.
- Added focused unit coverage for valid and invalid workflow definition shapes.

## Verification

- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov tests/unit/services/test_workflow_contracts.py tests/test_modules.py::TestModuleIntegration::test_module_dependencies tests/test_modules.py::TestModuleAPI::test_modules_api_response_structure`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/schemas/workflow.py app/services/workflows app/modules/workflow/main.py tests/unit/services/test_workflow_contracts.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/schemas/workflow.py app/services/workflows app/modules/workflow/main.py tests/unit/services/test_workflow_contracts.py`

## Files Changed

- `backend/app/schemas/workflow.py`
- `backend/tests/unit/services/test_workflow_contracts.py`

## Notes

- The initial pytest run without `--no-cov` had all selected tests pass but failed the repository-wide coverage threshold because only a focused subset ran.

---
*Plan completed: 2026-07-05*
