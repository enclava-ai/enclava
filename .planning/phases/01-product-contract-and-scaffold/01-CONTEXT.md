# Phase 1: Product Contract and Scaffold - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 converts the workflow implementation plan into code-facing contracts without changing shipped workflow runtime behavior. It should add schemas, enums, sample definitions, a step registry shell, service interfaces, and module adapter integration points that downstream phases can build on.

</domain>

<decisions>
## Implementation Decisions

### Infrastructure Scope
- Keep this phase scaffold-only: no database migration, no scheduler, no persisted run execution, and no frontend route.
- Preserve the existing workflow module smoke behavior and dependency order.
- Add contracts in shared backend locations where later API and service phases can reuse them.
- Add tests that validate representative workflow definitions and registry/template behavior.

### Contract Shape
- Model workflows as trigger plus runtime policy plus ordered typed steps.
- Support manual and schedule trigger contracts immediately; reserve event and API trigger types without implementing execution.
- Keep v1 definitions linear while allowing `depends_on` validation for future DAG support.
- Include budget, timeout, retry, redaction, concurrency, and misfire policy fields in the contract.

### Integration Points
- Keep `backend/app/modules/workflow/main.py` as the module-system adapter.
- Introduce a lightweight workflow service facade that exposes validation, template listing, and step catalog lookup.
- Expose template seeds for Nightly RAG Summary, Connector Intake Triage, and Weekly Extraction Report.
- Do not rely on the generic module execute endpoint for future production APIs.

### the agent's Discretion
All naming, file organization, and validation details can follow existing backend conventions as long as the public contracts stay close to `.planning/WORKFLOWS_IMPLEMENTATION_PLAN.md`.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Backend shared Pydantic contracts live under `backend/app/schemas/`.
- Business logic services live under `backend/app/services/`.
- Dynamic modules live under `backend/app/modules/*` with `main.py`, `module.yaml`, and optional helper files.
- Existing workflow module is `backend/app/modules/workflow/main.py`.

### Established Patterns
- Backend code uses Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, and pytest.
- Backend app imports use the `app.*` package root.
- Tests live under `backend/tests/` and can import app modules directly after test path setup.
- New code should preserve existing module manager behavior and avoid breaking module smoke tests.

### Integration Points
- `backend/app/modules/workflow/main.py` should consume the new service facade without changing the existing status/execute response shape.
- `backend/app/modules/workflow/__init__.py` can export new contracts for module-local use.
- Phase 2 can later add persistence and dedicated APIs using the schemas and service facade introduced here.

</code_context>

<specifics>
## Specific Ideas

- First useful vertical slice remains Nightly RAG Summary.
- MVP step types should include `rag.query`, `agent.run`, `notify.in_app`, and `condition.no_results_skip`.
- Connector and Extract templates can exist in scaffold form before their step handlers are implemented.

</specifics>

<deferred>
## Deferred Ideas

- Database models and migrations.
- Dedicated internal workflow APIs.
- Real run execution.
- Scheduling loop and locks.
- Frontend Workflows route.
- Connector and Extract execution handlers.
- Human approvals, external webhooks, API triggers, loops, and nested workflows.

</deferred>
