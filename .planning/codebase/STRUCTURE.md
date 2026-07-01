# Codebase Structure

**Analysis Date:** 2026-07-01

## Directory Layout

```text
enclava/
├── backend/                 # FastAPI backend, tests, migrations, configs, storage
│   ├── app/                 # Backend application package
│   │   ├── api/             # FastAPI route composition and domain routers
│   │   ├── connectors/      # Knowledge connector adapters
│   │   ├── core/            # Settings, security, cache, logging, permissions
│   │   ├── db/              # SQLAlchemy engines/session dependencies
│   │   ├── middleware/      # Request middleware for analytics, audit, rate limiting, debug
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── modules/         # Dynamically discovered platform modules
│   │   ├── schemas/         # Shared Pydantic schemas
│   │   ├── services/        # Business logic, providers, plugins, tools, usage, RAG, LLM
│   │   ├── tasks/           # Background schedulers/workers
│   │   └── utils/           # Shared backend helpers/exceptions
│   ├── alembic/             # Database migration environment and versions
│   ├── configs/             # Backend JSON config profiles
│   ├── scripts/             # Backend operational scripts
│   ├── storage/             # Runtime document storage
│   ├── tests/               # Backend unit, integration, e2e, performance tests
│   ├── Dockerfile           # Development backend image
│   ├── Dockerfile.prod      # Production backend image
│   ├── Dockerfile.migrate   # Migration image
│   └── pyproject.toml       # Python project and tooling config
├── frontend/                # Next.js frontend
│   ├── public/              # Static public assets
│   ├── src/
│   │   ├── app/             # Next.js App Router pages, layouts, API route proxies
│   │   ├── components/      # Domain and shared UI components
│   │   ├── contexts/        # React Context providers
│   │   ├── hooks/           # Shared React hooks
│   │   ├── lib/             # API clients, utilities, token/config helpers
│   │   └── types/           # Shared TypeScript types
│   ├── Dockerfile           # Frontend image
│   ├── package.json         # Frontend dependencies/scripts
│   ├── next.config.js       # Next.js config
│   ├── tailwind.config.js   # Tailwind config
│   └── tsconfig.json        # TypeScript config
├── nginx/                   # Reverse proxy configs
├── plugins/                 # Plugin packages/runtime plugin source
├── docs/                    # Project docs and plans
├── design-proposal/         # Design proposal artifacts
├── .github/workflows/       # GitHub Actions workflows
├── .planning/codebase/      # GSD codebase maps
├── docker-compose.yml       # Local multi-service runtime
├── docker-compose.prod.yml  # Production compose runtime
├── docker-compose.test.yml  # Test compose runtime
├── README.md                # Project overview/setup
└── CLAUDE.md                # Agent/project guidance
```

## Directory Purposes

**`backend/app/api`:**
- Purpose: Own HTTP route modules and route composition.
- Contains: Internal/public router aggregators, v1 domain routers, debug/health routes.
- Key files: `backend/app/api/internal_v1/__init__.py`, `backend/app/api/public_v1/__init__.py`, `backend/app/api/v1/llm.py`, `backend/app/api/v1/rag.py`, `backend/app/api/v1/extract.py`, `backend/app/api/v1/plugin_registry.py`.

**`backend/app/api/v1/endpoints`:**
- Purpose: House endpoint groups that are newer or resource-specific under v1.
- Contains: Conversations, MCP servers, prompts, responses, tool calling, tools, user management.
- Key files: `backend/app/api/v1/endpoints/responses.py`, `backend/app/api/v1/endpoints/mcp_servers.py`, `backend/app/api/v1/endpoints/tool_calling.py`.

**`backend/app/connectors`:**
- Purpose: Implement source-specific connector adapters for external systems.
- Contains: Base connector contracts, registry, GitHub, Linear, Notion, Slack connectors.
- Key files: `backend/app/connectors/base.py`, `backend/app/connectors/registry.py`, `backend/app/connectors/github.py`.

**`backend/app/core`:**
- Purpose: Cross-cutting backend infrastructure.
- Contains: Runtime settings, cache, security/auth, permissions, logging, threat detection.
- Key files: `backend/app/core/config.py`, `backend/app/core/security.py`, `backend/app/core/cache.py`, `backend/app/core/permissions.py`, `backend/app/core/logging.py`.

**`backend/app/db`:**
- Purpose: Database engine/session management and SQLAlchemy base.
- Contains: Async/sync engine setup, session factories, request dependency, timestamp helper.
- Key files: `backend/app/db/database.py`.

**`backend/app/middleware`:**
- Purpose: Request/response middleware concerns.
- Contains: Analytics, audit, debugging, rate limiting.
- Key files: `backend/app/middleware/analytics.py`, `backend/app/middleware/rate_limiting.py`, `backend/app/middleware/audit_middleware.py`.

**`backend/app/models`:**
- Purpose: SQLAlchemy ORM persistence model definitions.
- Contains: User/auth models, usage/budget models, RAG models, plugin models, tool models, Extract models, response/conversation models.
- Key files: `backend/app/models/user.py`, `backend/app/models/api_key.py`, `backend/app/models/rag_collection.py`, `backend/app/models/rag_document.py`, `backend/app/models/plugin.py`, `backend/app/models/response.py`.

**`backend/app/modules`:**
- Purpose: Dynamically discoverable platform capability modules.
- Contains: Each module directory with `module.yaml` and `main.py`.
- Key files: `backend/app/modules/rag/module.yaml`, `backend/app/modules/rag/main.py`, `backend/app/modules/agent/module.yaml`, `backend/app/modules/agent/main.py`, `backend/app/modules/extract/main.py`, `backend/app/modules/workflow/main.py`.

**`backend/app/schemas`:**
- Purpose: Shared Pydantic contracts outside route-local schemas.
- Contains: Audit, pricing, responses, roles, tools, usage stats, user schemas.
- Key files: `backend/app/schemas/responses.py`, `backend/app/schemas/user.py`, `backend/app/schemas/tool.py`, `backend/app/schemas/pricing.py`.

**`backend/app/services`:**
- Purpose: Business logic and integration orchestration.
- Contains: LLM service/providers, RAG/document processing, budgets, usage, plugin services, tool services, module manager, connector sync, analytics/audit/metrics.
- Key files: `backend/app/services/llm/service.py`, `backend/app/services/rag_service.py`, `backend/app/services/module_manager.py`, `backend/app/services/plugin_registry.py`, `backend/app/services/tool_execution_service.py`, `backend/app/services/usage_recording.py`.

**`backend/app/services/llm`:**
- Purpose: LLM domain package.
- Contains: Service coordinator, provider configuration, domain models, exceptions, resilience, metrics, streaming tracker, provider adapters.
- Key files: `backend/app/services/llm/service.py`, `backend/app/services/llm/models.py`, `backend/app/services/llm/config.py`, `backend/app/services/llm/providers/base.py`, `backend/app/services/llm/providers/privatemode.py`, `backend/app/services/llm/providers/redpill.py`.

**`backend/app/tasks`:**
- Purpose: Background and scheduled work.
- Contains: Connector sync scheduler and response archival.
- Key files: `backend/app/tasks/connector_sync.py`, `backend/app/tasks/response_archival.py`.

**`backend/alembic`:**
- Purpose: Database migrations.
- Contains: Alembic env/script template and versioned migration files.
- Key files: `backend/alembic/env.py`, `backend/alembic/versions/000_consolidated_ground_truth_schema.py`.

**`backend/tests`:**
- Purpose: Backend verification.
- Contains: Unit, integration, API, e2e, performance tests, fixtures, test clients.
- Key files: `backend/tests/conftest.py`, `backend/tests/unit`, `backend/tests/integration`, `backend/tests/e2e`.

**`frontend/src/app`:**
- Purpose: Next.js App Router routes.
- Contains: Page routes, layouts, admin pages, dashboard/settings pages, API route proxies.
- Key files: `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/api`.

**`frontend/src/app/api`:**
- Purpose: Next.js server-side API route proxies/adapters.
- Contains: Auth proxies, RAG proxies, plugin/settings proxies, internal compatibility routes.
- Key files: `frontend/src/app/api/auth/login/route.ts`, `frontend/src/app/api/rag/documents/route.ts`, `frontend/src/app/api/v1/settings/route.ts`, `frontend/src/app/api/v1/plugins/installed/route.ts`.

**`frontend/src/components`:**
- Purpose: Reusable UI and domain components.
- Contains: Admin, agent, auth, chat, connectors, extract, LLM, playground, plugins, RAG, settings, and UI primitives.
- Key files: `frontend/src/components/ui/navigation.tsx`, `frontend/src/components/providers/auth-provider.tsx`, `frontend/src/components/rag/document-upload.tsx`, `frontend/src/components/plugins/PluginManager.tsx`.

**`frontend/src/contexts`:**
- Purpose: React global state providers.
- Contains: Module, plugin, and toast contexts.
- Key files: `frontend/src/contexts/ModulesContext.tsx`, `frontend/src/contexts/PluginContext.tsx`, `frontend/src/contexts/ToastContext.tsx`.

**`frontend/src/lib`:**
- Purpose: Frontend API clients, auth token helpers, URL helpers, validation, and utility functions.
- Contains: `apiClient`, token manager, proxy auth, config, download, error, performance helpers.
- Key files: `frontend/src/lib/api-client.ts`, `frontend/src/lib/token-manager.ts`, `frontend/src/lib/proxy-auth.ts`, `frontend/src/lib/url-utils.ts`.

**`nginx`:**
- Purpose: Reverse proxy configuration.
- Contains: Runtime nginx config for normal and test environments.
- Key files: `nginx/nginx.conf`, `nginx/nginx.test.conf`.

**`plugins`:**
- Purpose: Plugin package/source area used by backend plugin discovery and registry features.
- Contains: Plugin directories and manifests when installed or developed locally.
- Key files: `plugins` directory; plugin runtime models/services are in `backend/app/models/plugin.py` and `backend/app/services/plugin_*.py`.

**`.planning/codebase`:**
- Purpose: GSD-generated codebase reference documents.
- Contains: Architecture, structure, stack, integration, quality, testing, and concern maps when generated.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app, lifecycle, middleware, exception handlers, router mounting.
- `frontend/src/app/layout.tsx`: Next.js root layout and provider composition.
- `frontend/src/app/page.tsx`: Frontend root page and authenticated redirect behavior.
- `backend/alembic/env.py`: Alembic migration entry.
- `docker-compose.yml`: Local multi-container entry for backend/frontend/dependencies.
- `nginx/nginx.conf`: Reverse proxy entry.

**Configuration:**
- `backend/app/core/config.py`: Backend settings object and environment-driven config.
- `backend/pyproject.toml`: Python dependencies and tooling.
- `frontend/package.json`: Frontend dependencies and scripts.
- `frontend/next.config.js`: Next.js runtime/build config.
- `frontend/tailwind.config.js`: Tailwind theme/content config.
- `frontend/tsconfig.json`: TypeScript compiler and path alias config.
- `backend/alembic.ini`: Alembic CLI config.
- `.env`: Present; contains environment configuration and must not be read or quoted.
- `.env.example`: Present; template for environment configuration.

**Core Logic:**
- `backend/app/api/v1/llm.py`: LLM HTTP API orchestration.
- `backend/app/services/llm/service.py`: LLM provider coordinator.
- `backend/app/api/v1/rag.py`: RAG HTTP API orchestration.
- `backend/app/services/rag_service.py`: RAG business logic and persistence coordination.
- `backend/app/modules/rag/main.py`: RAG module vector/document processing.
- `backend/app/api/v1/extract.py`: Extract HTTP API.
- `backend/app/modules/extract/services/extract_service.py`: Extract processing service.
- `backend/app/services/module_manager.py`: Dynamic module discovery/load/register lifecycle.
- `backend/app/services/plugin_registry.py`: Plugin registry logic.
- `backend/app/api/v1/connectors.py`: Connector management HTTP API.
- `backend/app/tasks/connector_sync.py`: Connector sync scheduler.

**Data and Persistence:**
- `backend/app/db/database.py`: Database engine/session factories and `get_db`.
- `backend/app/models`: SQLAlchemy ORM models.
- `backend/alembic/versions`: Migration history.
- `backend/storage/rag_documents`: Runtime RAG document storage.

**Frontend UI:**
- `frontend/src/components/ui`: Shared UI primitives.
- `frontend/src/components/admin`: Admin screens.
- `frontend/src/components/rag`: RAG management UI.
- `frontend/src/components/extract`: Extract UI.
- `frontend/src/components/llm`: LLM provider/usage UI.
- `frontend/src/components/plugins`: Plugin UI.
- `frontend/src/components/playground`: LLM playground UI.

**Frontend API and State:**
- `frontend/src/lib/api-client.ts`: Shared browser API client and domain helper methods.
- `frontend/src/lib/token-manager.ts`: Frontend token storage/refresh helpers.
- `frontend/src/lib/proxy-auth.ts`: Server-side backend proxy fetch helper.
- `frontend/src/components/providers/auth-provider.tsx`: Auth context provider.
- `frontend/src/contexts/ModulesContext.tsx`: Module status context.
- `frontend/src/contexts/PluginContext.tsx`: Plugin context.

**Testing:**
- `backend/tests/unit`: Backend unit tests.
- `backend/tests/integration`: Backend integration tests.
- `backend/tests/e2e`: Backend end-to-end tests.
- `backend/tests/performance`: Performance tests and analysis.
- `frontend/src/components/chat/SourcesList.test.tsx`: Frontend component test example.

## Naming Conventions

**Files:**
- Backend Python modules use snake_case: `backend/app/services/usage_recording.py`, `backend/app/models/api_key.py`.
- Backend domain routes use resource names: `backend/app/api/v1/api_keys.py`, `backend/app/api/v1/prompt_templates.py`.
- Backend module folders use lowercase feature names: `backend/app/modules/rag`, `backend/app/modules/agent`, `backend/app/modules/extract`.
- Each dynamic module should include `module.yaml` and `main.py`: `backend/app/modules/workflow/module.yaml`, `backend/app/modules/workflow/main.py`.
- Frontend pages use App Router names: `page.tsx`, `layout.tsx`, `route.ts`.
- Frontend React components use PascalCase: `frontend/src/components/plugins/PluginManager.tsx`, `frontend/src/components/admin/UserManagement.tsx`.
- Frontend utility files use kebab-case or descriptive lower-case: `frontend/src/lib/api-client.ts`, `frontend/src/lib/token-manager.ts`.
- UI primitive filenames are lowercase or kebab-case: `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/dropdown-menu.tsx`.

**Directories:**
- Backend package directories use lowercase snake_case where needed: `backend/app/api/internal_v1`, `backend/app/services/builtin_tools`.
- Frontend route directories mirror URL paths: `frontend/src/app/admin/users`, `frontend/src/app/settings`, `frontend/src/app/dashboard`.
- Frontend dynamic route segments use bracket notation: `frontend/src/app/dashboard/api-keys/[id]/stats/page.tsx`, `frontend/src/app/api/v1/plugins/[pluginId]/route.ts`.
- Test directories are grouped by test type: `backend/tests/unit`, `backend/tests/integration`, `backend/tests/e2e`, `backend/tests/performance`.

## Where to Add New Code

**New Backend API Feature:**
- Public/external route: Add a route module under `backend/app/api/v1` or `backend/app/api/v1/endpoints`, then include it in `backend/app/api/public_v1/__init__.py`.
- Frontend/internal management route: Add or reuse a route module under `backend/app/api/v1`, then include it in `backend/app/api/internal_v1/__init__.py`.
- Business logic: Put reusable logic in `backend/app/services/{feature}.py` or a feature package under `backend/app/services/{feature}`.
- Data model: Add SQLAlchemy model in `backend/app/models/{feature}.py` and migration in `backend/alembic/versions`.
- Schemas: Add shared Pydantic contracts to `backend/app/schemas/{feature}.py` when they are used across routes/services.
- Tests: Add focused tests under `backend/tests/unit` for services and `backend/tests/integration` or `backend/tests/integration/api` for API behavior.

**New Dynamic Backend Module:**
- Implementation: Create `backend/app/modules/{module_name}/main.py`.
- Manifest: Create `backend/app/modules/{module_name}/module.yaml` with `name`, `enabled`, `dependencies`, `provides`, `consumes`, endpoints, and permissions.
- Base class: Implement `BaseModule` from `backend/app/services/base_module.py`.
- Discovery hook: Expose `{module_name}_module` or `module` in `main.py`, or a matching `{Name}Module` class.
- Permissions: Return permissions through `get_required_permissions()` and include matching manifest permissions.
- Tests: Add module tests under `backend/tests/unit` or `backend/tests/integration` depending on external dependencies.

**New Backend Service/Provider:**
- Implementation: Add service code under `backend/app/services`.
- LLM provider: Add provider adapter under `backend/app/services/llm/providers` and wire creation in `backend/app/services/llm/service.py`.
- Connector: Add connector adapter under `backend/app/connectors` and register it through `backend/app/connectors/registry.py`.
- Plugin behavior: Extend the appropriate `backend/app/services/plugin_*.py` service and persistent model in `backend/app/models/plugin.py` if needed.

**New Frontend Page:**
- Route: Add `frontend/src/app/{route}/page.tsx`.
- Shared layout: Use existing providers from `frontend/src/app/layout.tsx`; add nested `layout.tsx` only for route-specific chrome.
- Components: Put feature components under `frontend/src/components/{feature}`.
- API calls: Add methods to `frontend/src/lib/api-client.ts` or a focused helper under `frontend/src/lib`.
- Types: Add shared TS types to `frontend/src/types` when used by more than one component/helper.

**New Frontend API Proxy:**
- Implementation: Add `frontend/src/app/api/{path}/route.ts`.
- Backend target: Prefer `INTERNAL_API_URL`/`BACKEND_INTERNAL_PORT` for server-to-backend calls, consistent with `frontend/src/lib/proxy-auth.ts`.
- Auth: Forward `Authorization` headers or use `frontend/src/lib/proxy-auth.ts` where applicable.
- Avoid duplication: Prefer existing proxy helpers when adding several similar routes.

**New Frontend Component:**
- Domain component: Add to `frontend/src/components/{feature}`.
- Shared primitive: Add to `frontend/src/components/ui` only when broadly reusable.
- Hooks: Add reusable stateful logic to `frontend/src/hooks`.
- Styling utilities: Use `frontend/src/lib/utils.ts` and existing Tailwind conventions.

**Utilities:**
- Backend shared helpers: `backend/app/utils`.
- Backend cross-cutting infrastructure: `backend/app/core`.
- Frontend shared helpers: `frontend/src/lib`.
- Frontend reusable hooks: `frontend/src/hooks`.

**New Background Job:**
- Implementation: Add to `backend/app/tasks`.
- Startup/shutdown wiring: Register lifecycle start/stop in `backend/app/main.py` if it must run with the API process.
- Database access: Use `async_session_factory` from `backend/app/db/database.py`.

**New Migration:**
- Create a versioned migration in `backend/alembic/versions`.
- Keep ORM model changes in `backend/app/models` synchronized with migration state.
- Do not edit generated migration history for unrelated schema changes.

## Special Directories

**`frontend/.next`:**
- Purpose: Next.js build/dev output.
- Generated: Yes.
- Committed: No.

**`frontend/node_modules`:**
- Purpose: Installed frontend dependencies.
- Generated: Yes.
- Committed: No.

**`backend/htmlcov`:**
- Purpose: Python coverage HTML output.
- Generated: Yes.
- Committed: No.

**`coverage-reports`:**
- Purpose: Coverage artifacts.
- Generated: Yes.
- Committed: No.

**`test-reports`:**
- Purpose: Test result artifacts.
- Generated: Yes.
- Committed: No.

**`backend/.pytest_cache`:**
- Purpose: Pytest cache.
- Generated: Yes.
- Committed: No.

**`backend/__pycache__` and `backend/app/__pycache__`:**
- Purpose: Python bytecode caches.
- Generated: Yes.
- Committed: No.

**`backend/storage`:**
- Purpose: Runtime storage for RAG documents.
- Generated: Runtime data.
- Committed: Depends on environment; avoid committing user/runtime documents.

**`backend/uploads`:**
- Purpose: Runtime upload storage.
- Generated: Runtime data.
- Committed: No for user/runtime uploads.

**`backend/logs` and `logs`:**
- Purpose: Runtime logs.
- Generated: Yes.
- Committed: No.

**`.env`:**
- Purpose: Local environment configuration and secrets.
- Generated: User/environment-specific.
- Committed: No.

**`.env.example`:**
- Purpose: Environment configuration template.
- Generated: No.
- Committed: Yes.

**`.planning`:**
- Purpose: GSD planning and codebase intelligence artifacts.
- Generated: Yes.
- Committed: Project-dependent; codebase docs are intentionally written here.

---

*Structure analysis: 2026-07-01*
