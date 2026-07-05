---
phase: 06-connector-and-extract-integration
plan: "02"
status: completed
completed: 2026-07-05
commit: pending
---

# Plan 06-02 Summary: Extract Template Workflow Step

## What Changed

Backend:

- Added `ExtractService.run_template_for_workflow()` for running Extract templates over workflow-selected document summaries without file upload.
- Persisted normal `ExtractJob` and `ExtractResult` records for workflow Extract runs while leaving transaction ownership with the workflow runtime.
- Added `ExtractRunTemplateHandler` for `extract.run_template` with artifact output, step events, cost reporting, previous-step document input, RAG-filter document input, and actionable failure handling.
- Added `last_successful_run` filtering for RAG-backed Extract steps so weekly reports can process only documents indexed after the previous successful workflow run.
- Enabled `extract.run_template` in the authoritative step catalog with template, source, collection, connector, since, max document, and context config.
- Made Weekly Extraction Report authorable and seeded it as a scheduled Extract workflow.
- Added validation for Extract source config and JSON context payloads.

Frontend:

- Added Extract template list typing in the shared API client.
- Loaded Extract template options in the workflow builder.
- Added default config, step key generation, and template seeding for `extract.run_template`.
- Added a typed Extract properties editor with template select, document source mode, previous-step source fields, RAG collection/connector filters, since mode, max document input, context JSON, and retry attempts.
- Improved run timeline artifact display with a bounded JSON preview for Extract artifacts.

Tests:

- Added `backend/tests/unit/services/test_workflow_extract_steps.py`.
- Updated builder API tests so Extract is enabled, Weekly Extraction Report is authorable, and a filled weekly report definition validates.

## Verification

- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test pytest --no-cov -q tests/unit/services/test_workflow_extract_steps.py tests/unit/services/test_workflow_connector_steps.py tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_step_handlers.py tests/unit/services/test_workflow_run_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test black --check app/modules/extract/services/extract_service.py app/services/workflows/registry.py app/services/workflows/steps.py app/services/workflows/templates.py app/services/workflows/service.py tests/unit/services/test_workflow_extract_steps.py tests/unit/services/test_workflow_builder_api.py`
- `sudo docker compose -f docker-compose.test.yml run --rm enclava-backend-test isort --check-only app/modules/extract/services/extract_service.py app/services/workflows/registry.py app/services/workflows/steps.py app/services/workflows/templates.py app/services/workflows/service.py tests/unit/services/test_workflow_extract_steps.py tests/unit/services/test_workflow_builder_api.py`
- `cd frontend && npm run lint`
- `cd frontend && npm run check:colors`
- `cd frontend && npm run check:plumbing`
- `cd frontend && npm run build`
- `git diff --check -- . ':!CLAUDE.md' ':!design-proposal'`
- `sudo docker compose up -d --build`
- `sudo docker compose up -d --force-recreate enclava-nginx`
- `curl -fsS http://localhost:1080/health`
- `curl -fsSI 'http://localhost:1080/workflows/new?template=weekly-extraction-report'`
- Authenticated live smoke: connector and Extract catalog entries enabled, Weekly Extraction Report authorable, filled weekly Extract definition validates through the Next workflow proxy, and `/api/v1/extract/templates` returns JSON through nginx.

## Notes

- Generic Extract report output can still be marked `completed_with_errors` by the existing invoice-oriented validator; the workflow handler treats that as a completed step unless the Extract service returns a failed/error status.
- `extract.run_template` writes `extract_result` artifacts and stores validation errors/warnings in step output for run-detail inspection.
- RAG filter source uses `indexed_at` for `last_successful_run` cutoff behavior.
