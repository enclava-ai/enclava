---
phase: 02-persistence-api-permissions-and-audit
status: clean
reviewed: 2026-07-05T19:25:00Z
depth: standard
---

# Phase 2 Code Review

## Scope

- `backend/app/models/workflow.py`
- `backend/alembic/versions/034_add_workflow_lifecycle.py`
- `backend/app/schemas/workflow.py`
- `backend/app/services/workflows/service.py`
- `backend/app/api/internal_v1/workflows.py`
- `backend/app/modules/workflow/main.py`
- `backend/tests/unit/services/test_workflow_persistence.py`
- `backend/tests/unit/services/test_workflow_lifecycle_service.py`
- `backend/tests/unit/services/test_workflow_api.py`

## Findings

No blocking findings remain.

## Review Notes

- Initial review found that admin-published versions recorded `created_by_user_id` as the workflow owner instead of the actor who published. Fixed in `WorkflowService.publish_definition` and covered by `test_admin_publish_records_actor_on_version`.
- Initial review found that `workflow.manage` permission passed the mutate gate but still failed the owner-only read gate for non-owned workflows. Fixed by normalizing dot/colon workflow permission aliases and applying global read/manage visibility before owner filtering.
- Internal validation endpoint now returns structured validation responses for invalid workflow documents instead of relying on FastAPI body parsing failures.
- Lifecycle API body defaults avoid shared Pydantic model instances.

## Verification After Review Fixes

- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_lifecycle_service.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_persistence.py tests/unit/services/test_workflow_lifecycle_service.py tests/unit/services/test_workflow_api.py tests/unit/services/test_workflow_contracts.py tests/test_modules.py::TestModuleIntegration::test_module_dependencies tests/test_modules.py::TestModuleAPI::test_modules_api_response_structure`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/services/workflows/service.py tests/unit/services/test_workflow_lifecycle_service.py`
- Passed: `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/services/workflows/service.py tests/unit/services/test_workflow_lifecycle_service.py`

## Residual Risk

- Manual run creation and execution semantics are intentionally not implemented until Phase 3.
- Scheduler due-run behavior and next-run calculations are intentionally not implemented until Phase 4.
- The test database needed a schema reset after migration verification because existing migration-created legacy tables are not all mapped by the test fixture's `Base.metadata.drop_all`; this is a test-environment sequencing issue, not a workflow lifecycle failure.
