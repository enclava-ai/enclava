---
phase: 06-connector-and-extract-integration
type: context
created: 2026-07-05
status: active
---

# Phase 6 Context: Connector and Extract Integration

## Objective

Make workflows coordinate existing platform modules beyond RAG and Agent by enabling two near-term workflow step types:

- `connector.sync`: synchronously run an existing connector sync and expose newly indexed records to downstream workflow steps.
- `extract.run_template`: run an Extract template over selected existing documents and persist extraction output as workflow artifacts.

This phase must extend the existing workflow runtime, not introduce a second workflow engine.

## Current Baseline

Workflow runtime:

- `backend/app/services/workflows/registry.py` already exposes `connector.sync` and `extract.run_template` in the step catalog, but both are disabled with Phase 6 messages.
- `backend/app/services/workflows/steps.py` currently implements handlers for `rag.query`, `agent.run`, `notify.in_app`, and `condition.no_results_skip`.
- `backend/app/services/workflows/runtime.py` already persists step runs, step errors, workflow artifacts, workflow events, duration, retry state, and redacted run detail payloads.
- `backend/app/services/workflows/templates.py` already defines Connector Intake Triage and Weekly Extraction Report templates, but both are unavailable for authoring.
- The builder renders only enabled catalog entries in `WorkflowStepList` and typed editors in `WorkflowStepProperties`.

Connector module:

- `backend/app/services/connector_sync_service.py` provides `ConnectorSyncService.run_sync(connector_id)`.
- `run_sync` is synchronous from the caller perspective and returns a `ConnectorSyncJob`.
- Sync jobs are persisted in `connector_sync_jobs`.
- Indexed connector content is persisted as `RagDocument` rows with `connector_source_id`, `external_id`, `external_updated_at`, `converted_content`, `source_url`, and metadata.
- The current connector API manual trigger starts a background task, which is not suitable for workflow execution because downstream steps need the sync output in the same run.

Extract module:

- `backend/app/modules/extract/services/extract_service.py` is centered on uploaded file processing.
- `ExtractService.process_document` creates `ExtractJob` and `ExtractResult` records and uses Extract templates, validation, cost tracking, and LLM calls.
- Workflow use cases need execution over selected existing documents, not necessarily new uploads.
- `TemplateManager` can list and load active Extract templates.

Frontend:

- `frontend/src/lib/api-client.ts` has `extractApi.listTemplates()` and `ragApi.listCollections()`.
- Connector management pages already call `/api-internal/v1/connectors` through `apiClient`; there is not yet a typed builder helper.
- `WorkflowRunTimeline` already shows step errors and artifact chips, but artifact list only displays artifact name/type/date, not data previews.

## Non-Goals

- No canvas or visual DAG.
- No loops, nested workflows, arbitrary code, webhook/API trigger expansion, or human approvals.
- No raw secrets in workflow definitions.
- No dependence on the generic module execute endpoint for workflow production behavior.
- No rewrite of connector or Extract modules.

## Integration Principles

- Workflows reference existing connector/template/document IDs only.
- Step handlers return compact structured outputs and persist richer detail as artifacts.
- Module-specific failures become `WorkflowStepExecutionError` messages with enough context to fix the connector, template, document filter, or permissions.
- Builder forms stay typed and compact; users should select a connector/template/filter, not write JSON unless they explicitly need optional context.
- Templates flip to available only after the required runtime and builder support lands.

## Phase Split

Plan `06-01` enables `connector.sync` end to end:

- Connector runtime adapter.
- Handler, catalog, validation, template availability.
- Builder connector picker and default config.
- Connector Intake Triage template authoring and run path.

Plan `06-02` enables `extract.run_template` end to end:

- Extract workflow adapter over selected existing documents.
- Handler, catalog, validation, template availability.
- Builder Extract template/document-source form.
- Extraction artifact preview in run detail.
- Weekly Extraction Report template authoring and run path.
