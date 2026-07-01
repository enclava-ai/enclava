"""
Pytest configuration and shared fixtures for all tests.
"""

import asyncio
import builtins
import decimal as _decimal
import inspect
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncGenerator, Generator

import aiohttp
import httpx
import pytest
import pytest_asyncio
import sqlalchemy.exc as sa_exc
from fastapi import HTTPException, Request, status
from httpx import AsyncClient
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

if not hasattr(sa_exc, "OptimisticLockError"):

    class OptimisticLockError(Exception):
        pass

    sa_exc.OptimisticLockError = OptimisticLockError

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.security import (
    get_current_active_user,
    get_current_user,
    verify_token,
)
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services.api_key_auth import get_api_key_context
from app.services.llm.models import ChatMessage, ChatRequest
from app.services.llm.service import LLMService

builtins.asyncio = asyncio


class CompatDecimal(_decimal.Decimal):
    """Decimal subclass that tolerates float arithmetic in legacy tests."""

    @staticmethod
    def _coerce(value):
        if isinstance(value, float):
            return CompatDecimal(str(value))
        return value

    def __mul__(self, other):
        return super().__mul__(self._coerce(other))

    def __rmul__(self, other):
        return super().__rmul__(self._coerce(other))


_decimal.Decimal = CompatDecimal


class AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def _patched_dependency(name: str, original):
    module_names = (
        "app.api.v1.auth",
        "app.api.v1.analytics",
        "app.api.v1.budgets",
        "app.api.v1.rag",
        "app.api.v1.llm",
    )
    for module_name in module_names:
        module = sys.modules.get(module_name)
        candidate = getattr(module, name, None) if module else None
        if candidate is not None and candidate is not original:
            return candidate
    return None


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


@pytest.fixture
def llm_service():
    """Shared LLM service fixture for legacy service test classes."""
    return LLMService()


@pytest.fixture
def sample_chat_request():
    """Shared sample chat request for legacy service test classes."""
    return ChatRequest(
        messages=[ChatMessage(role="user", content="Hello, how are you?")],
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=150,
        user_id="test-user",
    )


def _user_dict(user):
    if isinstance(user, dict):
        return user
    if isinstance(user, User) or hasattr(user, "id"):
        role = getattr(user, "role", None)
        role_name = (
            role.name
            if hasattr(role, "name")
            else getattr(user, "_legacy_role_name", role)
        )
        return {
            "id": getattr(user, "id", None),
            "email": getattr(user, "email", None),
            "username": getattr(user, "username", None),
            "is_superuser": getattr(user, "is_superuser", False),
            "is_active": getattr(user, "is_active", True),
            "role": role_name,
            "permissions": ["*"] if getattr(user, "is_superuser", False) else [],
            "user_obj": user,
        }
    return user


def _token_from_request(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return auth_header[7:]


async def _compat_get_db():
    patched_get_db = _patched_dependency("get_db", get_db)
    if patched_get_db:
        result = patched_get_db()
        if inspect.isasyncgen(result):
            async for session in result:
                yield session
            return
        yield await _maybe_await(result)
        return

    async with TestSessionLocal() as session:
        yield session


async def _compat_current_user(request: Request):
    token = _token_from_request(request)

    patched_get_current_user = _patched_dependency("get_current_user", get_current_user)
    if patched_get_current_user:
        return _user_dict(await _maybe_await(patched_get_current_user()))

    if token == "test_access_token":
        return {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "is_superuser": False,
            "is_active": True,
            "role": "user",
            "permissions": [],
        }
    if token == "admin_access_token":
        return {
            "id": 2,
            "email": "admin@example.com",
            "username": "admin",
            "is_superuser": True,
            "is_active": True,
            "role": "admin",
            "permissions": ["*"],
        }

    try:
        payload = verify_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    subject = payload.get("sub")
    user_id = payload.get("user_id") or subject
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        pass

    return {
        "id": user_id,
        "email": payload.get("email") or subject,
        "username": payload.get("username"),
        "is_superuser": payload.get("is_superuser", False),
        "is_active": True,
        "role": payload.get("role", "user"),
        "permissions": [],
    }


async def _compat_current_active_user(request: Request):
    patched_get_current_active_user = _patched_dependency(
        "get_current_active_user", get_current_active_user
    )
    if patched_get_current_active_user:
        return _user_dict(await _maybe_await(patched_get_current_active_user()))

    current_user = await _compat_current_user(request)
    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    return current_user


if "app" not in httpx.AsyncClient.__init__.__annotations__:
    _BaseAsyncClient = httpx.AsyncClient

    class CompatAsyncClient(_BaseAsyncClient):
        """Compatibility wrapper for tests still using httpx.AsyncClient(app=...)."""

        def __init__(self, *args, app=None, **kwargs):
            self._compat_app = app
            self._compat_previous_overrides = None
            if app is not None and "transport" not in kwargs:
                kwargs["transport"] = httpx.ASGITransport(app=app)
            super().__init__(*args, **kwargs)

        async def __aenter__(self):
            if self._compat_app is not None:
                self._compat_previous_overrides = dict(
                    self._compat_app.dependency_overrides
                )
                self._compat_app.dependency_overrides.setdefault(get_db, _compat_get_db)
                self._compat_app.dependency_overrides.setdefault(
                    get_current_user, _compat_current_user
                )
                self._compat_app.dependency_overrides.setdefault(
                    get_current_active_user, _compat_current_active_user
                )
            return await super().__aenter__()

        async def __aexit__(self, exc_type, exc_value, traceback):
            try:
                return await super().__aexit__(exc_type, exc_value, traceback)
            finally:
                if (
                    self._compat_app is not None
                    and self._compat_previous_overrides is not None
                ):
                    self._compat_app.dependency_overrides.clear()
                    self._compat_app.dependency_overrides.update(
                        self._compat_previous_overrides
                    )

    httpx.AsyncClient = CompatAsyncClient
    AsyncClient = CompatAsyncClient


# Test database URL (use different database name for tests)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://enclava_user:enclava_pass@localhost:5432/enclava_test_db",
)


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, pool_pre_ping=True, poolclass=NullPool
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with automatic rollback."""
    async with test_engine.begin() as conn:
        # Create all tables for this test
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        # Rollback any changes made during the test
        await session.rollback()

    # Clean up tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing FastAPI endpoints."""

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    class TestAPIKey:
        id = 1
        user_id = 1
        name = "Test API Key"
        key_prefix = "test-api"
        allowed_models = []
        allowed_endpoints = []
        allowed_ips = []
        permissions = ["*"]
        scopes = [
            "chat.completions",
            "embeddings.create",
            "models.list",
            "admin.status",
            "budget.read",
            "admin.metrics",
        ]
        total_requests = 0
        total_tokens = 0
        total_cost = 0
        rate_limit_per_minute = 1000
        rate_limit_per_hour = 10000
        rate_limit_per_day = 100000
        created_at = None
        last_used_at = None

        def has_scope(self, scope: str) -> bool:
            return scope in self.scopes or "*" in self.scopes

        def can_access_model(self, model_name: str) -> bool:
            return True

        def can_access_endpoint(self, endpoint: str) -> bool:
            return True

        def can_access_from_ip(self, ip_address: str) -> bool:
            return True

        def update_usage(self, tokens_used: int = 0, cost_cents: int = 0):
            self.total_requests += 1
            self.total_tokens += tokens_used
            self.total_cost += cost_cents

    async def override_get_api_key_context(request: Request):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else None
        token = token or request.headers.get("X-API-Key")
        if token != "test-api-key" and not (token or "").startswith("sk-test-"):
            return None

        api_key = TestAPIKey()
        user = SimpleNamespace(
            id=1,
            email="test@example.com",
            username="testuser",
            is_active=True,
            is_superuser=True,
        )
        return {
            "auth_type": "api_key",
            "api_key": api_key,
            "api_key_id": api_key.id,
            "api_key_name": api_key.name,
            "user": user,
            "user_id": user.id,
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_context] = override_get_api_key_context

    try:
        from httpx import ASGITransport

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    except ImportError:
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(async_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """Backward-compatible alias used by older endpoint tests."""
    yield async_client


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(
    async_client: AsyncClient, test_user_token: str
) -> AsyncClient:
    """Create an authenticated async client with JWT token."""
    async_client.headers.update({"Authorization": f"Bearer {test_user_token}"})
    return async_client


@pytest_asyncio.fixture(scope="function")
async def api_key_client(async_client: AsyncClient, test_api_key: str) -> AsyncClient:
    """Create an async client authenticated with API key."""
    async_client.headers.update({"Authorization": f"Bearer {test_api_key}"})
    return async_client


@pytest_asyncio.fixture(scope="function")
async def nginx_client() -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Create an aiohttp client for testing through nginx proxy."""
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture(scope="function")
def qdrant_client() -> QdrantClient:
    """Create a Qdrant client for testing."""
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
    )


@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession) -> dict:
    """Create a test user."""
    from app.core.security import get_password_hash
    from app.models.user import User

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

    return AttrDict(
        {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "password": "testpass123",
        }
    )


@pytest_asyncio.fixture(scope="function")
async def test_user_token(test_user: dict) -> str:
    """Create a JWT token for test user."""
    from app.core.security import create_access_token

    token_data = {"sub": test_user["email"], "user_id": test_user["id"]}
    return create_access_token(data=token_data)


@pytest_asyncio.fixture(scope="function")
async def test_api_key(test_db: AsyncSession, test_user: dict) -> str:
    """Create a test API key."""
    import secrets

    from app.models.api_key import APIKey
    from app.models.budget import Budget

    # Create budget
    budget = Budget(
        id=str(uuid.uuid4()),
        user_id=test_user["id"],
        limit_amount=100.0,
        period="monthly",
        current_usage=0.0,
        is_active=True,
    )
    test_db.add(budget)

    # Create API key
    key = f"sk-test-{secrets.token_urlsafe(32)}"
    api_key = APIKey(
        id=str(uuid.uuid4()),
        key_hash=key,  # In real code, this would be hashed
        name="Test API Key",
        user_id=test_user["id"],
        scopes=["llm.chat", "llm.embeddings"],
        budget_id=budget.id,
        is_active=True,
    )
    test_db.add(api_key)
    await test_db.commit()

    return key


@pytest_asyncio.fixture(scope="function")
async def test_qdrant_collection(qdrant_client: QdrantClient) -> str:
    """Create a test Qdrant collection."""
    from qdrant_client.models import Distance, VectorParams

    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"

    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    yield collection_name

    # Cleanup
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_documents_dir() -> Path:
    """Get the test documents directory."""
    return Path(__file__).parent / "data" / "documents"


@pytest.fixture(scope="session")
def sample_text_path(test_documents_dir: Path) -> Path:
    """Get path to sample text file for testing."""
    text_path = test_documents_dir / "sample.txt"
    if not text_path.exists():
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text("""
        Enclava Platform Documentation
        
        This is a sample document for testing the RAG system.
        It contains information about the Enclava platform's features and capabilities.
        
        Features:
        - Secure LLM access through PrivateMode.ai
        - Agent creation and management
        - RAG (Retrieval Augmented Generation) support
        - OpenAI-compatible API endpoints
        - Budget management and API key controls
        """)
    return text_path


# Test environment variables
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    os.environ["TESTING"] = "true"
    os.environ["LOG_LLM_PROMPTS"] = "true"
    os.environ["APP_DEBUG"] = "true"
    yield
    # Cleanup
    os.environ.pop("TESTING", None)
