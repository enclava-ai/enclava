# Phase 5 Research: Builder, Templates, and Validation

## Implementation Findings

### Backend catalog and validation

- The current catalog API exists as `GET /api-internal/v1/workflows/catalog`, but it returns raw `WorkflowStepCatalogEntry` objects and does not expose per-step detail aliases from the implementation plan (`/steps/catalog` and `/steps/catalog/{step_type}`).
- The existing validation endpoint accepts a raw definition and returns Pydantic errors. It does not yet add registry-aware errors for unknown step types, disabled future step types, or missing required config fields declared in `config_schema.required`.
- `WorkflowDefinitionDocument` already validates trigger requirements, cron/timezone validity, unique step keys, and dependency ordering.
- Registry-aware validation can be implemented without a new dependency by checking JSON schema `required` keys for top-level config fields. Full JSON Schema evaluation can be deferred unless builder needs nested validation.
- Connector and Extract templates already exist but include `connector.sync` and `extract.run_template`, which are not implemented by the Phase 3 runtime. The catalog should expose these as disabled entries so templates can be visible without implying they are executable.

### Frontend builder architecture

- Keep a single `workflowApi` in `frontend/src/lib/api-client.ts` for now; the codebase does not yet have a separate `frontend/src/lib/api/workflows.ts` module.
- Reuse the existing `/api/workflows` proxy rather than adding direct backend fetches from client components.
- A route-level builder keeps operations clean:
  - `/workflows/new` for new draft/template authoring.
  - `/workflows/[workflowId]/edit` for editing an existing draft.
- The current UI library provides the needed controls: `Input`, `Textarea`, `Select`, `Switch`, `Checkbox`, `Tabs`, `Button`, `StatusBadge`, `ConfirmDialog`, and table/card primitives.
- The builder should own draft state in React and submit normalized `WorkflowDefinitionDocument` payloads to backend validation before save/publish.

### Template path

- Nightly RAG Summary can be authored with existing implemented step handlers:
  - `rag.query`
  - `condition.no_results_skip`
  - `agent.run`
  - `notify.in_app`
- Existing frontend APIs can provide agent options through `agentApi.listAgents`.
- RAG collection routes exist under `/api/rag/collections`; the builder can add a small helper to read collections for the Nightly template.
- Publish/enable/run-now already exist through backend services, but the frontend proxy needs builder action routing for create, update, publish, validate, full template catalog, and schedule preview.

## Validation Architecture

### Source gates

- Backend unit tests must prove:
  - catalog includes implemented MVP step types and disabled future step types;
  - step detail lookup returns 404 or 422 for unknown step type;
  - validation returns path-specific errors for missing trigger fields, missing step config, unknown step type, and disabled step type;
  - Nightly RAG Summary template validates and can publish;
  - Connector/Extract templates remain visible but cannot publish while their disabled steps are present.

### Frontend gates

- `npm run lint`
- `npm run check:colors`
- `npm run check:plumbing`
- `npm run build`
- Builder components must avoid direct client `fetch` calls and native browser dialogs.
- Text in compact controls must stay inside buttons/select triggers on mobile and desktop.

### Live gates

- Rebuild containers after each implementation plan.
- Smoke `/health`, `/workflows`, `/workflows/new`, and authenticated `/api/workflows?resource=catalog` or equivalent after builder routes land.

## Risks

- Builder clunkiness: mitigated by linear step list, compact properties panel, and a persistent validation/action bar.
- Duplicate validation logic: mitigated by backend-authoritative validation and frontend display of backend error paths.
- Template false promises: mitigated by disabled catalog entries for connector/extract until Phase 6.
- Route complexity: mitigated by keeping operations default and isolating builder routes.

## Recommended Plan Split

- 05-01: backend catalog/validation APIs and frontend client/proxy plumbing.
- 05-02: builder route, draft editing UI, save/publish/enable flows.
- 05-03: template picker and Nightly RAG Summary authoring/test path.
