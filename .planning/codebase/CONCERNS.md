# Codebase Concerns

**Analysis Date:** 2026-07-01

## Tech Debt

**Large feature modules with mixed responsibilities:**
- Issue: Several files combine API orchestration, business rules, state transformation, UI rendering, and operational concerns in one module.
- Files: `backend/app/modules/rag/main.py`, `backend/app/services/rag_service.py`, `backend/app/modules/agent/main.py`, `backend/app/services/llm/service.py`, `frontend/src/app/admin/users/page.tsx`, `frontend/src/components/agent/AgentConfigManager.tsx`, `frontend/src/app/admin/pricing/page.tsx`, `frontend/src/app/admin/audit/page.tsx`
- Impact: Small changes have a large regression surface. The RAG module is especially fragile because MIME detection, document conversion, chunking, indexing, search, statistics, and compatibility helpers share one 2,597-line file.
- Fix approach: Split by responsibility before adding new behavior. For RAG, keep `backend/app/api/v1/rag.py` as the route layer, move conversion/MIME logic into `backend/app/services/document_processor.py`, vector operations into a dedicated Qdrant adapter, and preserve `backend/app/services/rag_service.py` as orchestration only.

**Compatibility shims inside production services:**
- Issue: Production services include legacy/test compatibility paths such as `_NullRAGSession`, `_EmptyQuery`, `_maybe_await`, and sync-style `db_session` fallbacks.
- Files: `backend/app/services/rag_service.py`, `backend/app/core/security.py`
- Impact: Runtime code accepts invalid construction states and mixes sync and async database assumptions, which can hide integration bugs until production paths exercise real `AsyncSession` behavior.
- Fix approach: Keep compatibility shims in test fixtures or adapters under `backend/tests/fixtures/`. Require real `AsyncSession` construction for production `RAGService` and remove legacy query-style branches from service methods.

**Frontend proxy route duplication:**
- Issue: Many Next route handlers forward requests to the backend with local header/error handling instead of using one shared proxy helper.
- Files: `frontend/src/app/api/rag/documents/route.ts`, `frontend/src/app/api/v1/settings/route.ts`, `frontend/src/app/api/v1/settings/[category]/route.ts`, `frontend/src/app/api/v1/llm/models/route.ts`, `frontend/src/app/api/v1/plugins/[pluginId]/config/route.ts`
- Impact: Auth forwarding, error redaction, timeouts, and response parsing drift between routes. Upload handling already contains route-specific debug behavior that leaks implementation details.
- Fix approach: Add a shared proxy helper under `frontend/src/lib/` for backend URL construction, auth forwarding, timeout handling, and sanitized error responses. Use route files only for endpoint-specific request shaping.

**Debug/demo code reachable in source tree:**
- Issue: Demo and diagnostic pages contain production-shaped token and RAG flows with verbose logs.
- Files: `frontend/src/app/rag-demo/page.tsx`, `frontend/src/app/test-auth/page.tsx`, `frontend/src/app/api/rag/debug/collections/route.ts`, `frontend/src/app/api/rag/debug/search/route.ts`
- Impact: Debug pages increase attack surface and make it easier to depend on non-product APIs. Logs disclose auth state and token expiry metadata in the browser console.
- Fix approach: Gate debug/demo routes by environment and role, or move them out of shipped app routes. Keep diagnostic endpoints behind backend authorization and do not expose them through public frontend route handlers.

## Known Bugs

**Plugin import allowlist conflicts with blocklist:**
- Symptoms: `PluginImportHook.validate_import()` checks `ALLOWED_MODULES` before `BLOCKED_MODULES`, and `sqlalchemy` appears in both sets.
- Files: `backend/app/services/plugin_sandbox.py`
- Trigger: A plugin imports `sqlalchemy`; the allowlist match returns before the blocklist can reject it.
- Workaround: None detected.

**Plugin CPU and memory limits are not consistently enforceable:**
- Symptoms: `SandboxLimits.max_memory_mb` defaults to `-1`, CPU limit checks only warn, and monitoring uses process-level metrics rather than isolated plugin execution.
- Files: `backend/app/services/plugin_sandbox.py`
- Trigger: A plugin performs CPU-heavy or memory-heavy work inside the platform process.
- Workaround: Set explicit limits when constructing `PluginSandbox`, but CPU checks still do not stop execution.

**Plugin token revocation fails open when Redis is unavailable:**
- Symptoms: Revocation checks return valid when Redis is missing or blacklist lookup fails, despite comments describing fail-secure behavior.
- Files: `backend/app/services/plugin_security.py`
- Trigger: Redis outage or blacklist read error during `verify_plugin_token()`.
- Workaround: None detected. Operational monitoring for Redis reduces exposure but does not enforce revocation.

## Security Considerations

**Browser-local refresh tokens:**
- Risk: Access and refresh tokens are stored in `window.localStorage` under `auth_tokens`, making a successful XSS enough to steal a long-lived refresh token.
- Files: `frontend/src/lib/token-manager.ts`, `frontend/src/app/rag-demo/page.tsx`
- Current mitigation: Token expiry is tracked client-side and refresh is automatic.
- Recommendations: Move refresh tokens to `HttpOnly`, `Secure`, `SameSite` cookies and keep only short-lived access tokens in memory. Remove direct localStorage token sync from feature pages.

**Verbose upload and RAG route logging:**
- Risk: Console logs disclose filenames, form fields, backend URLs, response bodies, content types, request body objects, auth-header presence, stack traces, collection names, and token expiry metadata.
- Files: `frontend/src/lib/file-download.ts`, `frontend/src/app/api/rag/documents/route.ts`, `frontend/src/app/rag-demo/page.tsx`
- Current mitigation: Logs avoid printing the raw authorization header value in the inspected snippets.
- Recommendations: Replace console logging with environment-gated structured logging. Never log upload payloads, backend error bodies containing user content, token expiry metadata, or stack traces in frontend route responses.

**Development encryption-key fallback logs key material:**
- Risk: When `PLUGIN_ENCRYPTION_KEY` is absent, a generated Fernet key is stored under `/data/plugin_keys/encryption.key` and the base64 key is printed in a warning.
- Files: `backend/app/services/plugin_security.py`
- Current mitigation: The code labels this as a development fallback.
- Recommendations: Require `PLUGIN_ENCRYPTION_KEY` outside local development, do not log generated key material, and ensure `/data/plugin_keys/encryption.key` permissions are restricted.

**Permissive CORS and inline CSP allowances:**
- Risk: Backend CORS permits all methods and headers with credentials, while the configured CSP allows inline scripts and inline styles.
- Files: `backend/app/main.py`, `backend/app/core/config.py`
- Current mitigation: `settings.CORS_ORIGINS` derives explicit origins from `BASE_URL`; production security validation rejects debug mode and weak JWT secrets.
- Recommendations: Narrow CORS methods/headers to required values and remove `'unsafe-inline'` from `API_CSP_HEADER` before relying on browser-side token storage or admin pages.

## Performance Bottlenecks

**RAG processing is CPU and I/O heavy in request-facing modules:**
- Problem: Document conversion, MIME sniffing, NLP/tokenization, chunking, embedding, and indexing are concentrated in the RAG module/service path.
- Files: `backend/app/modules/rag/main.py`, `backend/app/services/rag_service.py`, `backend/app/services/document_processor.py`
- Cause: Large uploads and expensive document conversion run through shared service code; defaults allow processing up to 300 seconds and embedding/indexing timeouts up to 120 seconds.
- Improvement path: Keep uploads fast by persisting metadata and enqueueing processing through `backend/app/services/document_processor.py`; expose processing state through `backend/app/api/v1/rag.py`.

**Startup performs multiple dependency and discovery steps:**
- Problem: Application startup checks Redis/database, initializes module manager, starts document processing, initializes plugins, and starts connector sync before the app is fully ready.
- Files: `backend/app/main.py`
- Cause: The lifespan handler centralizes dependency checks and service startup.
- Improvement path: Keep critical database checks blocking, but move plugin discovery, connector sync, and non-critical providers to background readiness states with health endpoints that expose degraded status.

**Admin pages render large workflows as single client components:**
- Problem: Admin users, pricing, audit, API key, and stats pages are 1,000+ line components.
- Files: `frontend/src/app/admin/users/page.tsx`, `frontend/src/app/admin/pricing/page.tsx`, `frontend/src/app/admin/audit/page.tsx`, `frontend/src/app/admin/api-keys/page.tsx`, `frontend/src/app/dashboard/api-keys/[id]/stats/page.tsx`
- Cause: Data fetching, table rendering, dialogs, forms, export logic, and mutations are colocated in page files.
- Improvement path: Extract data hooks, table sections, dialogs, and form schemas into `frontend/src/components/` and `frontend/src/lib/` modules. Add focused component tests around extracted units.

## Fragile Areas

**Plugin sandbox and registry:**
- Files: `backend/app/services/plugin_sandbox.py`, `backend/app/services/plugin_security.py`, `backend/app/services/plugin_registry.py`, `backend/app/services/plugin_autodiscovery.py`
- Why fragile: Plugin code executes near platform internals, and the sandbox combines AST checks, import hooks, resource monitoring, encryption, token issuance, and Redis revocation.
- Safe modification: Treat plugin execution as hostile. Add regression tests for blocked imports, dynamic import bypasses, Redis outage behavior, resource limit enforcement, and token revocation before changing plugin behavior.
- Test coverage: Backend tests include connector and security tests, but no directly observed test file focuses on sandbox bypass or resource enforcement.

**RAG collections and external/vector source synchronization:**
- Files: `backend/app/services/rag_service.py`, `backend/app/modules/rag/main.py`, `backend/app/api/v1/rag.py`
- Why fragile: PostgreSQL and Qdrant are both treated as sources for collection/document state. `get_all_collections()` can synthesize database records from Qdrant names, and API routes contain special handling for external collections.
- Safe modification: Define one source-of-truth contract for collection identity and sync boundaries. Add integration tests covering PostgreSQL-only, Qdrant-only, deleted, and concurrently created collections.
- Test coverage: RAG tests exist under `backend/tests/integration/api/test_rag_endpoints.py`, `backend/tests/integration/test_real_rag_integration.py`, and `backend/tests/unit/services/test_rag_service.py`; concurrency and source-of-truth drift need targeted coverage.

**Authentication/session lifecycle:**
- Files: `backend/app/core/security.py`, `backend/app/api/v1/auth.py`, `frontend/src/lib/token-manager.ts`, `frontend/src/contexts/ModulesContext.tsx`
- Why fragile: JWT creation, refresh rotation, token storage, token event handling, and frontend module fetching are coupled through side effects.
- Safe modification: Make token storage strategy explicit, then update frontend consumers to depend on a single auth state hook instead of reading tokens directly.
- Test coverage: Backend auth tests exist under `backend/tests/integration/api/test_auth_endpoints.py` and `backend/tests/test_auth_security.py`; frontend auth behavior has no broad test coverage beyond one component test elsewhere.

## Scaling Limits

**Frontend test coverage:**
- Current capacity: One frontend test file was detected: `frontend/src/components/chat/SourcesList.test.tsx`.
- Limit: Large admin and route-proxy surfaces can regress without automated UI, auth, or API forwarding tests.
- Scaling path: Add Vitest/React Testing Library or Playwright coverage for `frontend/src/lib/token-manager.ts`, route proxy helpers, admin tables, upload flows, and auth redirects.

**Backend service complexity:**
- Current capacity: Backend tests are present and configured with an 80% coverage threshold in `backend/pyproject.toml`.
- Limit: Coverage alone does not offset high-complexity files such as `backend/app/modules/rag/main.py`, `backend/app/api/v1/llm.py`, `backend/app/api/v1/api_keys.py`, and `backend/app/api/v1/settings.py`.
- Scaling path: Split large files along stable interfaces, then preserve behavior with unit tests for extracted modules and integration tests for public route contracts.

**Plugin token blacklist depends on Redis availability:**
- Current capacity: Redis-backed blacklist and plugin/user revocation keys.
- Limit: Revocation checks return valid when Redis is unavailable.
- Scaling path: Decide whether revocation is availability-first or security-first. For security-first deployments, fail closed or require short-lived plugin tokens with database-backed revocation fallback.

## Dependencies at Risk

**Optional document-processing libraries:**
- Risk: RAG behavior changes depending on whether NLTK, spaCy, MarkItDown, and python-docx imports succeed.
- Impact: Document conversion, entity extraction, tokenization, and supported file behavior can differ by environment.
- Migration plan: Add startup diagnostics for optional RAG capabilities and tests for fallback behavior. Pin required document processors in backend dependency files when a format is part of product support.

**Plugin sandbox uses process-level Python controls:**
- Risk: Import hooks and AST checks are not a full isolation boundary for untrusted plugin code.
- Impact: A bypass can affect the main backend process, database access, filesystem, or network behavior.
- Migration plan: Move untrusted plugin execution to a separate worker/container process with OS-level limits and an explicit RPC surface. Keep `backend/app/services/plugin_sandbox.py` as policy validation, not isolation.

## Missing Critical Features

**Central frontend backend-proxy abstraction:**
- Problem: Route handlers repeatedly implement request forwarding, auth header copying, and error handling.
- Blocks: Consistent timeout behavior, audit logging, redaction, and retries across frontend API routes.

**Frontend test harness for app routes and admin workflows:**
- Problem: Only one frontend test file is present despite many client-heavy pages and route handlers.
- Blocks: Safe refactoring of admin pages, token handling, proxy routes, and upload flows.

**Explicit production gating for demo/debug surfaces:**
- Problem: Demo and debug RAG/auth routes are part of the normal app source tree.
- Blocks: Clear deployment assurance that diagnostic endpoints and pages are not reachable in production.

## Test Coverage Gaps

**Plugin sandbox enforcement:**
- What's not tested: Import precedence, dynamic import bypasses, resource limit failure behavior, CPU limit enforcement, Redis outage token revocation behavior, and encryption-key fallback behavior.
- Files: `backend/app/services/plugin_sandbox.py`, `backend/app/services/plugin_security.py`
- Risk: Security regressions in plugin execution can ship unnoticed.
- Priority: High

**Frontend auth and route proxy behavior:**
- What's not tested: localStorage token parsing, refresh failures, logout events, auth header forwarding, upload error redaction, and route proxy timeout/error behavior.
- Files: `frontend/src/lib/token-manager.ts`, `frontend/src/lib/file-download.ts`, `frontend/src/app/api/rag/documents/route.ts`, `frontend/src/app/api/v1/settings/route.ts`
- Risk: Token leaks, broken refresh flows, and inconsistent API responses can reach users.
- Priority: High

**Large admin workflows:**
- What's not tested: User creation/password reset, API key regeneration, pricing edits, audit filtering/export, and usage-stat exports in large page components.
- Files: `frontend/src/app/admin/users/page.tsx`, `frontend/src/app/admin/api-keys/page.tsx`, `frontend/src/app/admin/pricing/page.tsx`, `frontend/src/app/admin/audit/page.tsx`, `frontend/src/app/dashboard/api-keys/[id]/stats/page.tsx`
- Risk: Admin operations can regress during UI changes without focused tests.
- Priority: Medium

**RAG source-of-truth and processing edge cases:**
- What's not tested: Qdrant/PostgreSQL drift, concurrent collection creation, optional library fallback parity, timeout paths, malformed archives, and oversized document behavior.
- Files: `backend/app/modules/rag/main.py`, `backend/app/services/rag_service.py`, `backend/app/api/v1/rag.py`, `backend/app/services/document_processor.py`
- Risk: Document ingestion/search can silently diverge between storage layers or fail differently across environments.
- Priority: High

---

*Concerns audit: 2026-07-01*
