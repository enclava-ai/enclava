# Testing Patterns

**Analysis Date:** 2026-07-01

## Test Framework

**Runner:**
- Backend: pytest, configured in `backend/pyproject.toml`.
- Backend async support: pytest-asyncio with `asyncio_mode = "auto"` in `backend/pyproject.toml`.
- Backend test dependencies are listed in `backend/tests/requirements-test.txt`, including pytest, pytest-asyncio, pytest-cov, pytest-mock, pytest-timeout, pytest-postgresql, pytest-benchmark, pytest-html, pytest-json-report, and allure-pytest.
- Frontend: no runnable test framework is configured in `frontend/package.json`. One Jest/React Testing Library-style test exists at `frontend/src/components/chat/SourcesList.test.tsx`, but the file header states required Jest setup is not installed/configured.
- Config: `backend/pyproject.toml`; frontend test config is not detected.

**Assertion Library:**
- Backend uses pytest `assert` statements and `pytest.raises`, as seen in `backend/tests/unit/core/test_security.py`, `backend/tests/unit/services/llm/test_llm_service.py`, and `backend/tests/unit/connectors/test_github_connector.py`.
- Frontend test file uses Jest DOM matchers from `@testing-library/jest-dom` in `frontend/src/components/chat/SourcesList.test.tsx`, but dependencies and config are not present in `frontend/package.json`.

**Run Commands:**
```bash
cd backend && pytest              # Run all backend tests with configured coverage
cd backend && pytest -m unit       # Run backend unit tests marked with @pytest.mark.unit
cd backend && pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml  # Coverage reports
cd frontend && npm run lint        # Frontend quality check; no frontend test script is configured
```

## Test File Organization

**Location:**
- Backend tests live under `backend/tests/`.
- Backend unit tests live under `backend/tests/unit/`, including `backend/tests/unit/core/`, `backend/tests/unit/services/`, and `backend/tests/unit/connectors/`.
- Backend integration tests live under `backend/tests/integration/` and `backend/tests/integration/api/`.
- Backend API-focused tests also exist under `backend/tests/api/`.
- Backend e2e tests live under `backend/tests/e2e/`.
- Backend performance tests live under `backend/tests/performance/` and `backend/tests/performance_benchmark.py`.
- Shared backend fixtures live in `backend/tests/conftest.py`.
- Backend fixture/factory helpers live in `backend/tests/fixtures/test_data_manager.py`.
- Frontend component test is co-located at `frontend/src/components/chat/SourcesList.test.tsx`.

**Naming:**
- Backend pytest discovery is `test_*.py`, `Test*` classes, and `test_*` functions in `backend/pyproject.toml`.
- Backend class suites use `TestFeatureName`, for example `TestSecurityService` in `backend/tests/unit/core/test_security.py`, `TestLLMService` in `backend/tests/unit/services/llm/test_llm_service.py`, and `TestGitHubConnector` in `backend/tests/unit/connectors/test_github_connector.py`.
- Frontend Jest-style suites use `describe` and `it` blocks in `frontend/src/components/chat/SourcesList.test.tsx`.

**Structure:**
```text
backend/tests/
├── conftest.py                         # shared async DB, client, auth, qdrant fixtures
├── test_*.py                           # broad backend tests
├── api/test_*.py                       # API-specific tests
├── unit/
│   ├── core/test_*.py
│   ├── services/test_*.py
│   ├── services/llm/test_*.py
│   └── connectors/test_*.py
├── integration/
│   ├── test_*.py
│   └── api/test_*.py
├── e2e/test_*.py
├── performance/test_*.py
└── fixtures/test_data_manager.py

frontend/src/
└── components/chat/SourcesList.test.tsx # Jest-style component test, not wired into package scripts
```

## Test Structure

**Suite Organization:**
```python
class TestLLMService:
    @pytest.fixture
    def llm_service(self):
        return LLMService()

    @pytest.mark.asyncio
    async def test_chat_completion_success(
        self, llm_service, sample_chat_request, mock_provider_response
    ):
        with patch.object(llm_service, "_call_provider", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_provider_response
            response = await llm_service.chat_completion(sample_chat_request)
            assert response is not None
            mock_call.assert_called_once()
```

**Patterns:**
- Use class-based pytest suites for cohesive service, API, connector, and security behavior, following `backend/tests/unit/core/test_security.py` and `backend/tests/unit/services/llm/test_llm_service.py`.
- Define local `@pytest.fixture` values inside classes for scenario-specific data, following `sample_chat_request`, `mock_provider_response`, and `sample_user` fixtures in backend tests.
- Mark async backend tests with `@pytest.mark.asyncio`; pytest-asyncio auto mode is enabled in `backend/pyproject.toml`.
- Use `pytest.mark.unit`, `pytest.mark.integration`, `pytest.mark.e2e`, `pytest.mark.slow`, `pytest.mark.db`, `pytest.mark.redis`, and `pytest.mark.qdrant` markers as defined in `backend/pyproject.toml`.
- Use `pytest.mark.skipif` for optional SDK-dependent connector tests, as in `backend/tests/unit/connectors/test_github_connector.py`.
- API tests use `httpx.AsyncClient` against the FastAPI app, as in `backend/tests/integration/api/test_auth_endpoints.py` and shared fixtures in `backend/tests/conftest.py`.
- Frontend component tests use React Testing Library `render`, `screen`, `within`, `userEvent`, Jest mocks, and Jest DOM assertions in `frontend/src/components/chat/SourcesList.test.tsx`.

## Mocking

**Framework:** Backend uses `unittest.mock` (`AsyncMock`, `MagicMock`, `Mock`, `patch`, and `patch.object`). Frontend test file uses Jest `jest.mock`.

**Patterns:**
```python
with patch.object(llm_service, "_call_provider", new_callable=AsyncMock) as mock_call:
    mock_call.return_value = mock_provider_response
    response = await llm_service.chat_completion(sample_chat_request)
    mock_call.assert_called_once()
```

```python
with patch("github.Github") as mock_github_class:
    mock_github = MagicMock()
    mock_github.get_user.return_value = mock_user
    mock_github_class.return_value = mock_github
    connector.validate()
```

```typescript
jest.mock('lucide-react', () => ({
  ExternalLink: ({ className, 'aria-hidden': ariaHidden }: any) => (
    <span data-testid="external-link-icon" className={className} aria-hidden={ariaHidden} />
  ),
}))
```

**What to Mock:**
- Mock LLM provider calls and network/service boundaries in unit tests, following `_call_provider` patching in `backend/tests/unit/services/llm/test_llm_service.py`.
- Mock third-party SDK clients in connector tests, following `github.Github` patching in `backend/tests/unit/connectors/test_github_connector.py`.
- Mock database sessions with `AsyncMock` for isolated service tests, following `backend/tests/test_provider_pricing_sync.py` and `backend/tests/test_usage_recording_service.py`.
- Use FastAPI `app.dependency_overrides` for endpoint dependency replacement, following `backend/tests/conftest.py`.
- Mock icons and UI primitives in frontend component tests when the component contract matters more than library rendering, following `frontend/src/components/chat/SourcesList.test.tsx`.

**What NOT to Mock:**
- Do not mock Pydantic model validation in backend API and service tests; construct real request/response models such as `ChatRequest`, `ChatMessage`, and `User` as shown in `backend/tests/unit/services/llm/test_llm_service.py` and `backend/tests/unit/core/test_security.py`.
- Do not mock FastAPI routing for API integration tests; use `httpx.AsyncClient` with the app/ASGI transport through fixtures in `backend/tests/conftest.py`.
- Do not mock SQLAlchemy model objects when testing model constraints and persistence behavior in `backend/tests/test_database_models.py`; use the test database fixture instead.

## Fixtures and Factories

**Test Data:**
```python
@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession) -> dict:
    user = User(
        email="testuser@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return AttrDict({"id": str(user.id), "email": user.email, "username": user.username})
```

**Location:**
- Shared async fixtures are in `backend/tests/conftest.py`.
- Test data manager helpers are in `backend/tests/fixtures/test_data_manager.py`.
- Endpoint tests should reuse `async_client`, `client`, `authenticated_client`, `api_key_client`, `test_db`, `test_user`, `test_user_token`, and `test_api_key` from `backend/tests/conftest.py`.
- Qdrant tests should reuse `qdrant_client` and `test_qdrant_collection` from `backend/tests/conftest.py`.
- Nginx e2e tests use `nginx_client` from `backend/tests/conftest.py` and helpers in `backend/tests/clients/nginx_test_client.py`.

## Coverage

**Requirements:** Backend pytest enforces `--cov-fail-under=80` for `app` in `backend/pyproject.toml`. Coverage reports are generated as terminal missing-lines output, HTML under `backend/htmlcov/`, and XML at `backend/coverage.xml`.

**View Coverage:**
```bash
cd backend && pytest --cov=app --cov-report=term-missing
cd backend && pytest --cov=app --cov-report=html
cd backend && pytest --cov=app --cov-report=xml
```

## Test Types

**Unit Tests:**
- Scope: isolated services, security helpers, cost calculators, connectors, tool calling, URL metadata, and LLM models/services.
- Locations: `backend/tests/unit/`, plus top-level focused unit files such as `backend/tests/test_usage_recording_service.py`, `backend/tests/test_provider_pricing_sync.py`, and `backend/tests/test_pricing_management.py`.
- Approach: instantiate real domain models and services, patch provider/network/database boundaries with `AsyncMock`, `MagicMock`, and `patch`.

**Integration Tests:**
- Scope: FastAPI endpoint behavior, database interactions, Redis/Qdrant connectivity, auth performance, budget flows, RAG URL flows, cascade deletes, and LLM service integration.
- Locations: `backend/tests/integration/` and `backend/tests/integration/api/`.
- Approach: use async test DB sessions and `httpx.AsyncClient`/ASGI transport fixtures from `backend/tests/conftest.py`.

**E2E Tests:**
- Framework: pytest.
- Locations: `backend/tests/e2e/test_nginx_routing.py` and `backend/tests/e2e/test_openai_compatibility.py`.
- Approach: exercise nginx routing and OpenAI compatibility flows through test clients in `backend/tests/clients/`.

**Performance Tests:**
- Framework: pytest plus pytest-benchmark dependency, with standalone performance scripts.
- Locations: `backend/tests/performance/` and `backend/tests/performance_benchmark.py`.
- Approach: async load/performance scenarios around LLM and platform workflows.

**Frontend Tests:**
- Framework: Not configured in `frontend/package.json`.
- Existing pattern: `frontend/src/components/chat/SourcesList.test.tsx` expects Jest, React Testing Library, Jest DOM, and user-event, and includes setup instructions in its file header.
- Runnable command: Not detected.

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_provider_timeout_handling(llm_service, sample_chat_request):
    with patch.object(llm_service, "_call_provider", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = asyncio.TimeoutError("Provider timeout")
        with pytest.raises(Exception) as exc_info:
            await llm_service.chat_completion(sample_chat_request)
        assert "timeout" in str(exc_info.value).lower()
```

**Error Testing:**
```python
with pytest.raises(ValueError, match="access_token"):
    connector.load_credentials({})
```

```python
response = await client.post("/api/v1/auth/register", json=test_data)
assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
assert "password" in str(response.json()).lower()
```

**Endpoint Testing:**
```python
async with AsyncClient(app=app, base_url="http://test") as ac:
    response = await ac.post("/api/v1/auth/login", json=sample_login_data)
    assert response.status_code == status.HTTP_200_OK
```

**Frontend Component Testing:**
```typescript
render(<SourcesList sources={[mockSourceWithUrl]} />)
const link = screen.getByRole('link', { name: /How to reset password\?/i })
expect(link).toHaveAttribute('target', '_blank')
expect(link).toHaveAttribute('rel', 'noopener noreferrer')
```

---

*Testing analysis: 2026-07-01*
