---
phase: 06-connector-and-extract-integration
type: research
created: 2026-07-05
status: active
---

# Phase 6 Research Notes

## Existing Workflow Runtime Fit

`WorkflowRuntimeService` already has the right extension points:

- `WorkflowRuntimeDependencies.connector_service` and `.extract_service` exist but are unused.
- `create_default_step_handlers(dependencies)` is the one place to add new handlers.
- `WorkflowStepResult` can return:
  - `output_data` for downstream templates.
  - `artifacts` for run detail.
  - `events` for timeline messages.
  - cost estimates/actuals for Extract usage.
- Runtime failure behavior already persists failed step runs and failed run errors.

Therefore Phase 6 should add handlers, adapters, and UI config only. It should not alter run state machinery unless a small data point is required for adapter output.

## Connector Sync Research

Relevant code:

- `backend/app/services/connector_sync_service.py`
- `backend/app/models/connector_source.py`
- `backend/app/api/v1/connectors.py`
- `backend/app/tasks/connector_sync.py`
- `backend/app/models/rag_document.py`

Findings:

- `ConnectorSyncService.run_sync(connector_id)` already performs a full/incremental sync synchronously and returns `ConnectorSyncJob`.
- It commits internally, then refreshes the job.
- `_upsert_document` returns only a boolean, not the created `RagDocument`.
- Newly indexed connector documents can be identified by connector id plus index time, but that is weaker than returning the actual created row ids from the sync operation.
- Existing API `POST /connectors/{id}/sync` intentionally fires a background task. Workflow execution should call a service method directly to keep the step deterministic.

Recommended adapter:

- Add a small result dataclass, for example `ConnectorWorkflowSyncResult`, with:
  - `job`
  - `connector`
  - `documents`
  - `docs_indexed`
  - `docs_failed`
  - `status`
  - `error_message`
- Extend `ConnectorSyncService` with a workflow-facing method, for example `run_sync_for_workflow(connector_id, max_records=50)`.
- Track created `RagDocument` ids inside `_do_sync`/`_upsert_document` rather than relying only on timestamp queries.
- Keep `run_sync(connector_id)` backward-compatible for existing connector scheduler/API behavior.

Output shape for `connector.sync`:

```json
{
  "connector_id": "12",
  "connector_name": "Engineering Notion",
  "job_id": 88,
  "status": "success",
  "count": 3,
  "docs_indexed": 3,
  "docs_failed": 0,
  "items": [
    {
      "document_id": 101,
      "title": "Roadmap",
      "filename": "abc123.md",
      "source_url": "https://...",
      "external_id": "abc123",
      "external_updated_at": "2026-07-05T20:00:00Z"
    }
  ]
}
```

## Extract Research

Relevant code:

- `backend/app/modules/extract/services/extract_service.py`
- `backend/app/modules/extract/templates/manager.py`
- `backend/app/models/extract_job.py`
- `backend/app/models/extract_result.py`
- `backend/app/models/rag_document.py`
- `frontend/src/components/extract/*`

Findings:

- Current Extract service is optimized for uploaded PDF/image files.
- Workflow use cases are document-set/report style and should operate on existing platform documents.
- Existing Extract templates contain prompts and optional output schemas. They can still drive structured extraction over text if the adapter builds messages from selected document text.
- `ExtractJob` requires `user_id`, file metadata, `template_id`, and status. It can represent workflow-generated report jobs with synthetic filename/original filename such as `workflow-{run_id}-{step_key}.json`.
- `ExtractResult` can persist parsed JSON, validation errors/warnings, and final status.

Recommended adapter:

- Add a workflow-facing Extract adapter, preferably in the Extract service boundary, for example:
  - `run_template_for_workflow(db, template_id, documents, context, current_user, workflow_run_id, step_key)`.
- Load template with `TemplateManager`.
- Build a text prompt from selected documents and template prompts.
- Call existing LLM service with JSON response format where possible.
- Persist an `ExtractJob` and final `ExtractResult`.
- Return compact result data and cost details to the workflow handler.

Document source options:

- `from_step`: read document ids/items from a previous step output, primarily `connector.sync.items` or `rag.query.documents`.
- `rag_filter`: query `RagDocument` by `collection_id`, optional `connector_id`, and since mode such as last successful run.

Output shape for `extract.run_template`:

```json
{
  "template_id": "weekly_report",
  "job_id": "uuid",
  "status": "completed",
  "summary": "3 documents processed",
  "document_count": 3,
  "result": { "risk_items": [] },
  "validation_errors": [],
  "validation_warnings": [],
  "cost_cents": 4
}
```

## Frontend Research

Relevant code:

- `frontend/src/components/workflows/WorkflowBuilder.tsx`
- `frontend/src/components/workflows/WorkflowStepList.tsx`
- `frontend/src/components/workflows/WorkflowStepProperties.tsx`
- `frontend/src/components/workflows/WorkflowTemplatePicker.tsx`
- `frontend/src/components/workflows/WorkflowRunTimeline.tsx`
- `frontend/src/lib/api-client.ts`

Findings:

- Builder adds steps from enabled catalog entries only. Backend enabling is enough to reveal connector/extract step types.
- Properties panel is currently explicit per step type; connector/extract should follow that pattern.
- Template seeding has a central `seedStepFromTemplate` function for placeholder clearing.
- Artifact UI can be improved without changing the run detail API because artifact `data` is already serialized as a redacted payload.

Recommended UI additions:

- Add typed `connectorApi.listConnectors()` helper.
- Add typed `ExtractTemplateSummary`/`extractApi.listTemplates()` response types where useful.
- Add connector and extract option loading to `WorkflowBuilder`.
- Add `ConnectorSyncEditor` and `ExtractTemplateEditor` in `WorkflowStepProperties`.
- Add concise artifact data preview for JSON/summary/extract artifacts in `WorkflowRunTimeline`.

## Risks

- Connector service commits internally; tests must ensure workflow run state still persists correctly after connector sync commits.
- Extract over existing text documents may differ from current uploaded-image behavior; the adapter should be explicit in naming and tests.
- Existing connectors may require real external credentials. Unit tests must use fake connector/extract services or controlled DB rows rather than external APIs.
- Builder dropdowns must handle empty connector/template lists gracefully without hiding validation errors.
