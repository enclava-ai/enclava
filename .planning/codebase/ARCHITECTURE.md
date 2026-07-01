<!-- refreshed: 2026-07-01 -->
# Architecture

**Analysis Date:** 2026-07-01

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router UI                    │
├──────────────────┬──────────────────┬───────────────────────┤
│  Pages           │  Components      │  Client Contexts       │
│  `frontend/src/app` │ `frontend/src/components` │ `frontend/src/contexts` │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Frontend API proxies and shared client helpers      │
│          `frontend/src/app/api`, `frontend/src/lib`          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI application shell                  │
│                   `backend/app/main.py`                     │
├─────────────────────────────┬───────────────────────────────┤
│  Internal API               │  Public API                    │
│  `/api-internal/v1`         │  `/api/v1`                     │
│  `backend/app/api/internal_v1` │ `backend/app/api/public_v1` │
└──────────────┬──────────────┴──────────────┬────────────────┘
               │                             │
               ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│     Domain routes, dynamic modules, services, connectors     │
│     `backend/app/api/v1`, `backend/app/modules`,             │
│     `backend/app/services`, `backend/app/connectors`         │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│ PostgreSQL via SQLAlchemy    │ │ Vector/external providers   │
│ `backend/app/models`         │ │ Qdrant, LLM providers, MCP  │
│ `backend/app/db/database.py` │ │ `backend/app/services/*`    │
└─────────────────────────────┘ └─────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app shell | Creates the app, configures middleware, exception handlers, startup/shutdown lifecycle, and mounts internal/public routers. | `backend/app/main.py` |
| Internal API router | Exposes JWT-authenticated frontend management routes under `/api-internal/v1`. | `backend/app/api/internal_v1/__init__.py` |
| Public API router | Exposes external API key/JWT routes under `/api/v1`, including OpenAI-compatible endpoints. | `backend/app/api/public_v1/__init__.py` |
| Domain API routes | Own request/response models and HTTP orchestration for auth, LLM, RAG, Extract, budgets, plugins, tools, users, and settings. | `backend/app/api/v1` |
| Dynamic module manager | Discovers `module.yaml`, sorts dependencies, initializes modules, registers permissions, and mounts module routers. | `backend/app/services/module_manager.py` |
| Module implementations | Package optional platform capabilities with manifests, permissions, lifecycle hooks, and optional routers. | `backend/app/modules` |
| Service layer | Encapsulates business logic, provider clients, plugin management, budget checks, usage recording, document processing, and analytics. | `backend/app/services` |
| SQLAlchemy data layer | Defines async/sync engines, session factories, declarative base, UTC timestamp helper, and request-scoped DB dependency. | `backend/app/db/database.py` |
| ORM models | Define persistent tables, relationships, indexes, and enums for users, keys, usage, RAG, Extract, plugins, tools, and responses. | `backend/app/models` |
| Schemas | Hold shared Pydantic contracts used by API endpoints and services. | `backend/app/schemas` |
| Frontend app | Renders authenticated dashboard/admin/product pages with provider contexts and shared navigation. | `frontend/src/app`, `frontend/src/components` |
| Frontend API layer | Provides Next.js route proxies and browser fetch helpers for backend internal/public APIs. | `frontend/src/app/api`, `frontend/src/lib/api-client.ts` |
| Deployment edge | Runs frontend, backend, databases, vector storage, and reverse proxy in containers. | `docker-compose.yml`, `nginx/nginx.conf` |

## Pattern Overview

**Overall:** Modular monolith with a FastAPI service backend, Next.js frontend, dynamic backend modules, and service/provider adapters.

**Key Characteristics:**
- Keep HTTP routing thin where possible: routes in `backend/app/api/v1` should validate inputs, apply auth/dependencies, call services, and map exceptions to HTTP responses.
- Use async SQLAlchemy sessions from `backend/app/db/database.py` for new request-path code; the sync engine exists for legacy/startup paths.
- Use module manifests in `backend/app/modules/*/module.yaml` for dynamically loaded capabilities and dependency ordering.
- Keep provider-specific behavior behind service/provider abstractions such as `backend/app/services/llm/providers/base.py`, `backend/app/connectors/base.py`, and plugin services in `backend/app/services/plugin_*.py`.
- Frontend pages and components consume `AuthProvider`, `ModulesProvider`, `PluginProvider`, and `ToastProvider` from `frontend/src/app/layout.tsx`.

## Layers

**Frontend Pages:**
- Purpose: Render routes, collect user input, and compose feature-specific components.
- Location: `frontend/src/app`
- Contains: App Router `page.tsx`, `layout.tsx`, and route handlers under `frontend/src/app/api`.
- Depends on: `frontend/src/components`, `frontend/src/contexts`, `frontend/src/lib`.
- Used by: Browser users through Next.js.

**Frontend Components:**
- Purpose: Reusable UI for auth, admin, RAG, Extract, LLM playground, plugins, and shared UI primitives.
- Location: `frontend/src/components`
- Contains: Domain components and shadcn-style primitives in `frontend/src/components/ui`.
- Depends on: React, Tailwind, Radix primitives, `frontend/src/lib/api-client.ts`.
- Used by: Pages in `frontend/src/app`.

**Frontend State and API Helpers:**
- Purpose: Centralize auth/module/plugin state and backend fetch behavior.
- Location: `frontend/src/contexts`, `frontend/src/lib`
- Contains: `frontend/src/components/providers/auth-provider.tsx`, `frontend/src/contexts/ModulesContext.tsx`, `frontend/src/contexts/PluginContext.tsx`, `frontend/src/lib/api-client.ts`, `frontend/src/lib/token-manager.ts`.
- Depends on: Browser storage, backend `/api-internal/v1` and `/api/v1` routes.
- Used by: Pages/components and Next.js route handlers.

**Backend Application Shell:**
- Purpose: Own app lifecycle, middleware, exception handlers, router mounting, and health/root endpoints.
- Location: `backend/app/main.py`
- Contains: `lifespan()`, startup dependency checks, middleware setup, exception handlers, router mounting.
- Depends on: Settings, cache, database, module manager, analytics, metrics, audit, plugin, connector services.
- Used by: Uvicorn and Docker backend container.

**Backend API Routers:**
- Purpose: Define HTTP contracts and route composition for frontend/internal and public/external clients.
- Location: `backend/app/api`
- Contains: `backend/app/api/v1`, `backend/app/api/internal_v1`, `backend/app/api/public_v1`, `backend/app/api/health.py`, `backend/app/api/rag_debug.py`.
- Depends on: `backend/app/core/security.py`, `backend/app/db/database.py`, `backend/app/services`, `backend/app/models`, `backend/app/schemas`.
- Used by: FastAPI app in `backend/app/main.py`.

**Dynamic Modules:**
- Purpose: Add platform features with lifecycle, permissions, manifests, and optional routers.
- Location: `backend/app/modules`
- Contains: `backend/app/modules/agent`, `backend/app/modules/rag`, `backend/app/modules/extract`, `backend/app/modules/workflow`.
- Depends on: `backend/app/services/base_module.py`, `backend/app/services/module_manager.py`, domain services.
- Used by: `backend/app/services/module_manager.py` during startup and hot reload.

**Services and Providers:**
- Purpose: Implement business logic and external/provider integrations outside route handlers.
- Location: `backend/app/services`, `backend/app/connectors`
- Contains: LLM orchestration, RAG operations, budget enforcement, plugin registry/gateway/sandbox, connector sync, tool execution, usage recording.
- Depends on: Models, database sessions, settings, external SDK/client libraries.
- Used by: API routes, modules, tasks, and tests.

**Persistence:**
- Purpose: Store application state in PostgreSQL and vector/document state in RAG storage.
- Location: `backend/app/models`, `backend/app/db`, `backend/alembic`, `backend/storage`
- Contains: SQLAlchemy ORM models, Alembic migrations, database session dependency, RAG document storage.
- Depends on: SQLAlchemy, asyncpg/psycopg2, configured database URL.
- Used by: Services, API routes, modules, and migrations.

**Background Tasks:**
- Purpose: Run scheduled or long-lived workers outside direct request handling.
- Location: `backend/app/tasks`
- Contains: `backend/app/tasks/connector_sync.py`, `backend/app/tasks/response_archival.py`.
- Depends on: Async session factory, models, connector services.
- Used by: FastAPI lifespan startup/shutdown.

## Data Flow

### Primary Frontend Management Request Path

1. Browser renders a page such as `frontend/src/app/dashboard/page.tsx` inside providers from `frontend/src/app/layout.tsx:73`.
2. Contexts/helpers attach JWTs from `frontend/src/lib/token-manager.ts` through `frontend/src/lib/api-client.ts:16`.
3. The frontend calls `/api-internal/v1/*` directly or through Next.js proxies in `frontend/src/app/api`.
4. FastAPI receives the request through the router mounted in `backend/app/main.py:389`.
5. The relevant internal router delegates to domain routes registered in `backend/app/api/internal_v1/__init__.py`.
6. Domain routes use dependencies such as `get_current_user` and `get_db` from `backend/app/core/security.py` and `backend/app/db/database.py:221`.
7. Services in `backend/app/services` mutate or query ORM models in `backend/app/models`.
8. Route handlers return JSON to the frontend helper, which updates React state/components.

### Public OpenAI-Compatible LLM Request Path

1. External clients call `/api/v1/chat/completions`, `/api/v1/models`, or `/api/v1/embeddings` mounted by `backend/app/api/public_v1/__init__.py:27`.
2. `backend/app/api/v1/openai_compat.py` adapts OpenAI-compatible requests to the internal LLM route functions in `backend/app/api/v1/llm.py`.
3. LLM routes validate Pydantic request models in `backend/app/api/v1/llm.py:247`, authenticate API keys through `backend/app/services/api_key_auth.py`, and check budget/usage through `backend/app/services/async_budget_enforcement.py`.
4. Requests are converted into service models from `backend/app/services/llm/models.py` and dispatched to `llm_service` from `backend/app/services/llm/service.py:78`.
5. `LLMService` selects a provider from `backend/app/services/llm/providers`, calls the provider, records usage through `backend/app/services/usage_recording.py`, and returns normalized responses.

### RAG Document Flow

1. UI components such as `frontend/src/components/rag/document-upload.tsx` call RAG endpoints through helpers/proxies.
2. FastAPI routes in `backend/app/api/v1/rag.py` validate collection/document inputs and apply ACL helpers from `backend/app/utils/collection_access.py`.
3. `RAGService` from `backend/app/services/rag_service.py` coordinates SQLAlchemy models such as `backend/app/models/rag_collection.py` and `backend/app/models/rag_document.py`.
4. The RAG module in `backend/app/modules/rag/main.py` handles conversion, chunking, embeddings, and Qdrant operations.
5. Query/stat endpoints may read live vector state through `backend/app/services/qdrant_stats_service.py`.

### Dynamic Module Startup Flow

1. FastAPI lifespan calls `module_manager.initialize(app)` in `backend/app/main.py:169`.
2. `ModuleManager` discovers manifests under `backend/app/modules/*/module.yaml` via `backend/app/services/module_config_manager.py`.
3. Dependencies are topologically sorted in `backend/app/services/module_manager.py:233`.
4. Each module is imported from `app.modules.{name}.main`, initialized, and permission-registered in `backend/app/services/module_manager.py:265`.
5. Module routers are registered with FastAPI when exposed by the module implementation, such as agent routes in `backend/app/modules/agent/main.py:976`.

### Plugin and Connector Flow

1. Plugin management requests enter through `backend/app/api/v1/plugin_registry.py` and internal/public router composition.
2. Plugin services in `backend/app/services/plugin_registry.py`, `backend/app/services/plugin_autodiscovery.py`, `backend/app/services/plugin_configuration_service.py`, `backend/app/services/plugin_gateway.py`, and `backend/app/services/plugin_sandbox.py` own discovery, persistence, configuration, gateway behavior, and execution controls.
3. Connector management requests enter through `backend/app/api/v1/connectors.py`.
4. Connector-specific implementations live in `backend/app/connectors/github.py`, `backend/app/connectors/linear.py`, `backend/app/connectors/notion.py`, and `backend/app/connectors/slack.py`.
5. Scheduled sync is started/stopped by FastAPI lifespan through `backend/app/tasks/connector_sync.py`.

**State Management:**
- Backend request state is dependency-injected through FastAPI and SQLAlchemy async sessions from `backend/app/db/database.py`.
- Backend singleton-style services exist for cross-request managers such as `module_manager`, `llm_service`, `core_cache`, document processor, plugin discovery state, and connector scheduler.
- Frontend global state uses React Context providers in `frontend/src/app/layout.tsx`.
- Client auth tokens are managed by `frontend/src/lib/token-manager.ts` and attached by `frontend/src/lib/api-client.ts`.

## Key Abstractions

**FastAPI Router Boundary:**
- Purpose: Separate internal frontend APIs from public external APIs while reusing domain route modules.
- Examples: `backend/app/api/internal_v1/__init__.py`, `backend/app/api/public_v1/__init__.py`, `backend/app/api/v1/llm.py`.
- Pattern: `APIRouter` composition with prefixes and tags.

**Request-Scoped Database Session:**
- Purpose: Provide an async SQLAlchemy session per request with rollback on errors.
- Examples: `backend/app/db/database.py:221`, route dependencies in `backend/app/api/v1/rag.py:129`.
- Pattern: FastAPI `Depends(get_db)` with `async_session_factory`.

**Dynamic Module Contract:**
- Purpose: Load platform capabilities from manifests and a shared base class.
- Examples: `backend/app/services/base_module.py`, `backend/app/modules/rag/module.yaml`, `backend/app/modules/extract/main.py`.
- Pattern: `BaseModule` lifecycle plus `module.yaml` metadata and `get_required_permissions()`.

**Provider Adapter:**
- Purpose: Normalize external LLM/provider behavior behind a common service.
- Examples: `backend/app/services/llm/providers/base.py`, `backend/app/services/llm/providers/privatemode.py`, `backend/app/services/llm/providers/redpill.py`.
- Pattern: `LLMService` owns provider registry and dispatch.

**Connector Adapter:**
- Purpose: Encapsulate source-specific sync/auth behavior for knowledge connectors.
- Examples: `backend/app/connectors/base.py`, `backend/app/connectors/github.py`, `backend/app/connectors/registry.py`.
- Pattern: Registry plus connector implementations.

**Frontend Provider Contexts:**
- Purpose: Share auth, module, plugin, theme, and toast state across pages.
- Examples: `frontend/src/components/providers/auth-provider.tsx`, `frontend/src/contexts/ModulesContext.tsx`, `frontend/src/contexts/PluginContext.tsx`.
- Pattern: Client-side React Context wrappers nested in `frontend/src/app/layout.tsx`.

## Entry Points

**Backend ASGI app:**
- Location: `backend/app/main.py`
- Triggers: Uvicorn import of `app.main:app` or direct `python -m app.main`.
- Responsibilities: Startup/shutdown lifecycle, middleware, router mounting, exception handling, health endpoints.

**Backend public API:**
- Location: `backend/app/api/public_v1/__init__.py`
- Triggers: Requests under `/api/v1`.
- Responsibilities: External auth, OpenAI-compatible LLM APIs, RAG, tools, MCP servers, responses, conversations, prompts, Extract.

**Backend internal API:**
- Location: `backend/app/api/internal_v1/__init__.py`
- Triggers: Requests under `/api-internal/v1`.
- Responsibilities: Frontend management routes for auth, modules, settings, analytics, admin, plugins, providers, connectors, debug, usage.

**Module loading:**
- Location: `backend/app/services/module_manager.py`
- Triggers: FastAPI lifespan startup and hot reload.
- Responsibilities: Discover, order, initialize, permission-register, and mount modules.

**Frontend app root:**
- Location: `frontend/src/app/layout.tsx`
- Triggers: Next.js App Router render.
- Responsibilities: Metadata, fonts, theme, auth/module/plugin/toast providers, navigation, page container.

**Frontend home route:**
- Location: `frontend/src/app/page.tsx`
- Triggers: Browser request to `/`.
- Responsibilities: Redirect authenticated users to `/dashboard`, show unauthenticated entry page.

**Next.js API route proxies:**
- Location: `frontend/src/app/api`
- Triggers: Browser/server calls to `/api/*` in the frontend app.
- Responsibilities: Proxy or adapt requests to backend internal/public APIs using `INTERNAL_API_URL` or backend container URLs.

**Alembic migrations:**
- Location: `backend/alembic/env.py`, `backend/alembic/versions`
- Triggers: Alembic CLI/migration container.
- Responsibilities: Database schema migration for SQLAlchemy models.

## Architectural Constraints

- **Threading:** The backend uses FastAPI's async event loop for request handling and startup tasks; file watching uses `watchdog.Observer` with thread-to-event-loop scheduling in `backend/app/services/module_manager.py`.
- **Database sessions:** Use `AsyncSession` from `backend/app/db/database.py` for new request and service code; `SessionLocal` is retained for legacy/startup paths.
- **Global state:** Singleton/module-level managers exist in `backend/app/services/module_manager.py`, `backend/app/services/llm/service.py`, `backend/app/core/cache.py`, `backend/app/services/document_processor.py`, and frontend contexts under `frontend/src/contexts`.
- **Router split:** Public external routes belong under `/api/v1` via `backend/app/api/public_v1/__init__.py`; frontend-only management routes belong under `/api-internal/v1` via `backend/app/api/internal_v1/__init__.py`.
- **Module dependencies:** Module load order is determined by `dependencies` in `backend/app/modules/*/module.yaml`; avoid importing dependent modules before the manager initializes them.
- **Secrets:** `.env` and `.env.example` are present at repo root; do not read or commit secret values. Reference variable names through code/config only.
- **Generated/build artifacts:** Do not treat `frontend/.next`, `frontend/node_modules`, `backend/htmlcov`, `coverage-reports`, `test-reports`, or caches as source architecture.

## Anti-Patterns

### Bypassing the Service Layer

**What happens:** Route handlers grow direct provider/database/business logic instead of delegating to `backend/app/services`.
**Why it's wrong:** It duplicates logic, weakens tests, and makes public/internal route reuse harder.
**Do this instead:** Keep route code in `backend/app/api/v1` focused on HTTP concerns and put reusable domain behavior in service modules such as `backend/app/services/rag_service.py`, `backend/app/services/llm/service.py`, or `backend/app/services/usage_recording.py`.

### Adding Public Routes to Internal Router Only

**What happens:** New externally consumed functionality is registered only in `backend/app/api/internal_v1/__init__.py` or only through frontend proxies.
**Why it's wrong:** External clients calling `/api/v1` cannot access the endpoint, and API docs diverge.
**Do this instead:** Register external-facing APIs in `backend/app/api/public_v1/__init__.py`; reserve `backend/app/api/internal_v1/__init__.py` for frontend/admin management flows.

### Direct Frontend Fetch Duplication

**What happens:** Components hand-roll `fetch()` calls and auth/error handling instead of using `frontend/src/lib/api-client.ts` or focused helpers.
**Why it's wrong:** Auth headers, error mapping, and response parsing drift across pages.
**Do this instead:** Add reusable methods to `frontend/src/lib/api-client.ts` or a focused helper under `frontend/src/lib`, then consume it from components/pages.

### Creating Modules Without Manifests

**What happens:** New module folders omit `module.yaml` or do not expose a discoverable module instance/factory.
**Why it's wrong:** `ModuleManager` discovers and orders modules from manifests under `backend/app/modules`.
**Do this instead:** Add `backend/app/modules/{name}/module.yaml` plus `backend/app/modules/{name}/main.py` with a `BaseModule` implementation and a `{name}_module` or `module` discovery hook.

## Error Handling

**Strategy:** Central FastAPI exception handlers provide stable JSON errors, while domain routes convert expected service/domain failures to `HTTPException` or custom app exceptions.

**Patterns:**
- Use `CustomHTTPException` from `backend/app/utils/exceptions.py` when a structured application error code/details payload is needed.
- Let FastAPI `HTTPException` represent expected request errors; `backend/app/main.py` maps it to `{"error": "HTTP_ERROR", ...}`.
- Validation errors are sanitized by `backend/app/main.py` without echoing user input.
- Database dependency `get_db` in `backend/app/db/database.py` rolls back on HTTP, SQLAlchemy, and unexpected errors.
- Frontend fetch errors are normalized into `AppError` objects by `frontend/src/lib/api-client.ts`.

## Cross-Cutting Concerns

**Logging:** Backend logging is configured through `backend/app/core/logging.py`; modules use `log_module_event`, services use module loggers, and frontend route proxies sometimes log operational details.
**Validation:** Backend validates request contracts through Pydantic models colocated in route modules or `backend/app/schemas`; frontend has utility validation in `frontend/src/lib/validation.ts`.
**Authentication:** Backend JWT auth is in `backend/app/core/security.py`; API key auth/scopes are in `backend/app/services/api_key_auth.py`; frontend auth state is in `frontend/src/components/providers/auth-provider.tsx`.
**Authorization:** Platform/module permissions are registered through `backend/app/services/permission_manager.py`; collection ACLs are enforced via `backend/app/utils/collection_access.py`.
**Rate limiting:** Backend rate limiting is set up in `backend/app/main.py` through `backend/app/middleware/rate_limiting.py`.
**Analytics and audit:** Middleware and services live in `backend/app/middleware/analytics.py`, `backend/app/services/analytics.py`, `backend/app/middleware/audit_middleware.py`, and `backend/app/services/audit_service.py`.
**Metrics:** Metrics setup is called from `backend/app/main.py` and implemented in `backend/app/services/metrics.py` with internal route exposure in `backend/app/api/internal_v1/metrics.py`.
**Configuration:** Backend settings come from `backend/app/core/config.py`; frontend environment-dependent URL helpers live in `frontend/src/lib/url-utils.ts`; Docker and nginx compose runtime topology from root `docker-compose*.yml` and `nginx`.

---

*Architecture analysis: 2026-07-01*
