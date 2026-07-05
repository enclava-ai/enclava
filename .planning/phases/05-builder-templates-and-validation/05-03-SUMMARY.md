---
phase: 05-builder-templates-and-validation
plan: "03"
status: completed
completed: 2026-07-05
requirements: [WF-UX-04, WF-BUILD-02, WF-BUILD-03, WF-BUILD-04]
---

# Plan 05-03 Summary: Template-Assisted Nightly Authoring

## Outcome

The builder now supports template-assisted authoring for Nightly RAG Summary. Nightly can be seeded from the Templates tab, edited without JSON, validated with selected collection/agent/recipient values, published, enabled, and manually run. Connector and Extract templates remain visible but unavailable until Phase 6 runtime support.

## Implemented

- Added template metadata:
  - `required_placeholders`
  - `builder_category`
  - `available_for_authoring`
  - `unavailable_reason`
- Marked Nightly RAG Summary as available for authoring.
- Marked Connector Intake Triage and Weekly Extraction Report unavailable with Phase 6 reasons.
- Added registry validation for empty required config values and unresolved seed placeholders such as `{{collection_id}}`.
- Preserved valid runtime prompt templates such as `{{ input.topic }}`.
- Added `WorkflowTemplatePicker` with compact template cards, Create action for Nightly, and unavailable state for future templates.
- Updated the Templates tab to use the picker.
- Added `ragApi.listCollections` and switched builder collection loading to the public RAG collections proxy.
- Added `template=nightly-rag-summary` builder seeding:
  - steps: `find_new_docs`, `skip_if_empty`, `summarize`, `notify_owner`
  - editable schedule, RAG collection/query, agent, recipients, notification copy, retry, runtime, redaction, and budget controls
  - placeholders converted to editable empty/default fields before validation/save
- Updated builder post-publish state with an Operations link and only shows Run test when the workflow is active.
- Added backend coverage for Nightly template metadata, placeholder blocking, filled authoring validation, publish, enable, and manual run creation.

## Verification

- `pytest --no-cov -q tests/unit/services/test_workflow_builder_api.py tests/unit/services/test_workflow_run_api.py tests/unit/services/test_workflow_step_handlers.py` passed: 14 tests.
- `black --check app/services/workflows/templates.py app/services/workflows/service.py app/services/workflows/operations.py app/schemas/workflow.py tests/unit/services/test_workflow_builder_api.py` passed.
- `isort --check-only app/services/workflows/templates.py app/services/workflows/service.py app/services/workflows/operations.py app/schemas/workflow.py tests/unit/services/test_workflow_builder_api.py` passed.
- `npm run lint` passed.
- `npm run check:colors` passed.
- `npm run check:plumbing` passed.
- `npm run build` passed.
- `git diff --check` passed for touched tracked files.
- `sudo docker compose up -d --build` rebuilt backend, frontend, and migrate images.
- `sudo docker compose up -d --force-recreate enclava-nginx` recreated the public proxy.
- `curl -fsS http://localhost:1080/health` returned healthy.
- `curl -fsSI "http://localhost:1080/workflows/new?template=nightly-rag-summary"` returned `200 OK`.
- Authenticated smoke verified:
  - Nightly template metadata and four-step definition.
  - Connector and Weekly templates unavailable.
  - Raw Nightly seed validation blocks unresolved placeholders.
  - Filled Nightly authoring payload validates successfully.
  - Schedule preview returns five upcoming runs.
- Migrations remained at `035_workflow_run_runtime (head)`.

## Notes

- Template seed placeholders are now distinct from runtime prompt templates. Exact seed tokens like `{{collection_id}}` are blocked in required config fields; runtime expressions with spaces or dotted paths remain valid.
- Phase 6 can enable Connector and Extract authoring by adding runtime handlers and flipping template/catalog availability.
