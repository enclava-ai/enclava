# Coding Conventions

**Analysis Date:** 2026-07-01

## Naming Patterns

**Files:**
- Backend Python uses snake_case modules under `backend/app/`, for example `backend/app/services/usage_recording.py`, `backend/app/services/provider_pricing_sync.py`, and `backend/app/api/v1/openai_compat.py`.
- Backend tests use pytest discovery names `test_*.py` under `backend/tests/`, configured in `backend/pyproject.toml`.
- Frontend React components use PascalCase filenames for components, for example `frontend/src/components/playground/ChatPlayground.tsx` and `frontend/src/components/chat/SourcesList.tsx`.
- Frontend utility and type files use kebab-case or short descriptive names, for example `frontend/src/lib/api-client.ts`, `frontend/src/lib/error-utils.ts`, `frontend/src/types/mcp-server.ts`, and `frontend/src/lib/utils.ts`.
- Next.js App Router files use framework names like `page.tsx` and `layout.tsx` under route directories such as `frontend/src/app/analytics/page.tsx` and `frontend/src/app/admin/layout.tsx`.

**Functions:**
- Backend functions and methods use snake_case, including FastAPI dependencies in `backend/app/services/dependencies.py` such as `get_llm_service`, `get_module_manager`, and `get_plugin_discovery`.
- Backend async operations use `async def` and are awaited directly, for example startup checks in `backend/app/main.py` and fixtures in `backend/tests/conftest.py`.
- Frontend functions and hooks use camelCase, for example `getAuthHeader`, `makeError`, and `request` in `frontend/src/lib/api-client.ts`.
- React components use PascalCase function names, for example `SourcesList` in `frontend/src/components/chat/SourcesList.tsx` and `ToastProvider` in `frontend/src/contexts/ToastContext.tsx`.
- React hooks use the `use*` prefix, for example `useToast` in `frontend/src/contexts/ToastContext.tsx`.

**Variables:**
- Backend local variables use snake_case, for example `retry_delay`, `background_tasks`, and `async_session_factory` in `backend/app/main.py`.
- Backend constants and environment-derived settings use uppercase names, for example `TEST_DATABASE_URL` in `backend/tests/conftest.py`.
- Frontend local variables use camelCase, for example `queryParams`, `contentType`, and `hasRelevanceScore` in `frontend/src/lib/api-client.ts` and `frontend/src/components/chat/SourcesList.tsx`.
- Frontend constants exported as objects use uppercase where they model constant sets, for example `ERROR_CODES` in `frontend/src/lib/error-utils.ts`.

**Types:**
- Backend Pydantic models and SQLAlchemy models use PascalCase classes, for example `UserRegisterRequest`, `TokenResponse`, and `UserResponse` in `backend/app/api/v1/auth.py`.
- Backend custom exceptions use PascalCase ending in `Error` where appropriate, for example `AuthenticationError`, `AuthorizationError`, and `BudgetExceededError` in `backend/app/utils/exceptions.py`.
- Frontend TypeScript interfaces and component props use PascalCase, for example `AppError` in `frontend/src/lib/api-client.ts`, `ChatMessageSource` in `frontend/src/components/chat/SourcesList.tsx`, and `ToastProps` in `frontend/src/contexts/ToastContext.tsx`.

## Code Style

**Formatting:**
- Backend formatting is Black with 88-character line length and Python 3.11 target in `backend/pyproject.toml`.
- Backend imports are sorted with isort using the Black profile, `known_first_party = ["app", "tests"]`, and grouped multiline imports in `backend/pyproject.toml`.
- Backend linting uses Flake8 with `max-line-length = 88` in `backend/.flake8`; several legacy ignores are configured there, including `E501`, `F401`, `F841`, and `W503`.
- Frontend formatting is idiomatic TypeScript/React with semicolons generally omitted in source files such as `frontend/src/lib/api-client.ts` and `frontend/src/contexts/ToastContext.tsx`; config files such as `frontend/eslint.config.mjs` use semicolons.
- Frontend styling uses Tailwind class strings directly in JSX and the `cn` helper from `frontend/src/lib/utils.ts` for class composition.

**Linting:**
- Backend lint commands are documented in `CLAUDE.md`: run `black app/ tests/`, `isort app/ tests/`, `flake8 app/ tests/`, and `mypy app/` from `backend/`.
- Backend mypy is strict for application code in `backend/pyproject.toml`: untyped and incomplete function definitions are disallowed, untyped decorators are disallowed, implicit optionals are disabled, and strict equality is enabled.
- Backend mypy relaxes test typing for `tests.*` in `backend/pyproject.toml`; tests may use untyped fixtures and mocks.
- Frontend lint command is `npm run lint` from `frontend/`, defined as `eslint . --max-warnings=0` in `frontend/package.json`.
- Frontend ESLint uses Next core web vitals, TypeScript ESLint, and React hooks rules in `frontend/eslint.config.mjs`.
- Frontend TypeScript uses `strict: true`, `isolatedModules: true`, and `forceConsistentCasingInFileNames: true` in `frontend/tsconfig.json`.

## Import Organization

**Order:**
1. Python standard library imports first, as in `backend/app/main.py` and `backend/tests/conftest.py`.
2. Third-party imports next, for example FastAPI, SQLAlchemy, pytest, httpx, and Pydantic in `backend/app/api/v1/auth.py` and `backend/tests/conftest.py`.
3. First-party imports last, using the `app.*` package in backend files such as `backend/app/main.py`.
4. Frontend imports external packages first, then project alias imports such as `@/components/*` and `@/lib/*`, as in `frontend/src/app/layout.tsx`.
5. Frontend relative imports are used for same-directory component tests, for example `./SourcesList` in `frontend/src/components/chat/SourcesList.test.tsx`.

**Path Aliases:**
- Backend imports use the `app` package root after `backend/tests/conftest.py` adds the backend directory to `sys.path`.
- Frontend aliases are configured in `frontend/tsconfig.json`: `@/*`, `@/components/*`, `@/lib/*`, `@/utils/*`, `@/types/*`, `@/hooks/*`, and `@/app/*`.
- Use `@/lib/api-client` for frontend API calls as documented in `CLAUDE.md`; avoid new raw `fetch` wrappers outside the central API client unless the integration requires special transport behavior.

## Error Handling

**Patterns:**
- Backend API code raises FastAPI `HTTPException` for direct route failures, for example route validation and auth failures in `backend/app/api/v1/auth.py`, `backend/app/api/v1/api_keys.py`, and `backend/app/api/v1/connectors.py`.
- Backend shared HTTP error types live in `backend/app/utils/exceptions.py`; use `AuthenticationError`, `AuthorizationError`, `ValidationError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `BudgetExceededError`, `ModuleError`, `PluginError`, and `SecurityError` when route/service behavior needs structured `error_code` and `details`.
- Backend LLM service-specific failures use `backend/app/services/llm/exceptions.py` with `LLMError`, `ProviderError`, `RateLimitError`, `TimeoutError`, and `ValidationError`.
- Backend catches broad external-service failures at integration boundaries, logs context, and re-raises typed errors or HTTP errors. Examples include startup dependency checks in `backend/app/main.py` and provider wrappers under `backend/app/services/llm/providers/`.
- Frontend central request handling in `frontend/src/lib/api-client.ts` maps HTTP statuses to an `AppError` code: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `TIMEOUT`, `NETWORK_ERROR`, or `UNKNOWN`.
- Frontend display-oriented error normalization lives in `frontend/src/lib/error-utils.ts`; use `normalizeError`, `handleHttpError`, and `withRetry` for UI workflows that need retryability or user-facing messages.

## Logging

**Framework:** Backend uses Python `logging` plus `structlog`; frontend allows console output by ESLint configuration but project guidance discourages casual console logging.

**Patterns:**
- Backend modules initialize loggers with either `logging.getLogger(__name__)` or `get_logger(__name__)`, as seen in `backend/app/main.py`, `backend/app/api/v1/auth.py`, and `backend/app/core/logging.py`.
- Use structured `extra={...}` metadata for operational events when useful, as in Redis and database startup checks in `backend/app/main.py`.
- Sensitive log data is centrally redacted by `SensitiveDataRedactor` in `backend/app/core/logging.py`; do not log raw passwords, tokens, API keys, cookies, JWTs, or authorization headers.
- Log expected optional startup or integration failures at `warning` and critical startup blockers at `error`, following `backend/app/main.py`.
- Frontend user-visible notification state goes through toast providers in `frontend/src/contexts/ToastContext.tsx` and UI toaster components in `frontend/src/app/layout.tsx`.

## Comments

**When to Comment:**
- Use module docstrings to state purpose for major backend modules, following `backend/app/main.py`, `backend/app/services/dependencies.py`, and `backend/app/core/logging.py`.
- Use short comments for compatibility shims, test fixtures, and non-obvious setup, following `backend/tests/conftest.py`.
- Avoid comments that restate simple assignments; prefer comments that explain compatibility, security, or integration constraints.
- Frontend comments are used sparingly for public helper sections and test intent, for example `frontend/src/lib/error-utils.ts` and `frontend/src/components/chat/SourcesList.test.tsx`.

**JSDoc/TSDoc:**
- Frontend APIs use block comments for methods in large API wrapper objects, for example `mcpServerApi` and `extractApi` methods in `frontend/src/lib/api-client.ts`.
- Backend uses Python docstrings on fixtures, service dependencies, exception classes, and tests, for example `backend/app/services/dependencies.py` and `backend/tests/unit/core/test_security.py`.

## Function Design

**Size:** Keep new functions focused around a single route handler, dependency, service operation, or UI behavior. Large legacy route/service files exist, so prefer extracting new reusable behavior into service modules such as `backend/app/services/*` instead of adding more private helpers to large route files.

**Parameters:** Use typed parameters in backend app code because mypy disallows untyped defs in `backend/pyproject.toml`. Use FastAPI `Depends` and annotated dependency aliases from `backend/app/services/dependencies.py` for injectable services. Use typed props/interfaces for frontend components, as in `frontend/src/components/chat/SourcesList.tsx`.

**Return Values:** Return Pydantic response models or serializable dict/list structures from backend routes. Return typed promises from frontend API wrappers, using `apiClient.get<T>`, `post<T>`, `put<T>`, and `delete<T>` in `frontend/src/lib/api-client.ts`.

## Module Design

**Exports:** Backend modules generally expose classes/functions directly by module path, for example `backend/app/services/llm/service.py` and `backend/app/services/dependencies.py`. Frontend modules use named exports for reusable utilities and components, for example `export function cn` in `frontend/src/lib/utils.ts` and `export function SourcesList` in `frontend/src/components/chat/SourcesList.tsx`.

**Barrel Files:** Backend package `__init__.py` files exist throughout `backend/app/` and `backend/tests/`, but new code should import from concrete modules unless an existing package-level export is already established. Frontend does not rely on broad barrel exports in the inspected files; import components/utilities from their direct path aliases.

---

*Convention analysis: 2026-07-01*
