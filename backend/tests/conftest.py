"""
Pytest configuration and shared fixtures for all tests.
"""
import os
import sys
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import aiohttp
from qdrant_client import QdrantClient
from httpx import AsyncClient
import uuid

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import Base, get_db
from app.core.config import settings
from app.main import app


# Test database URL (use different database name for tests)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://enclava_user:enclava_pass@localhost:5432/enclava_test_db"
)


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
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
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(async_client: AsyncClient, test_user_token: str) -> AsyncClient:
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
        port=int(os.getenv("QDRANT_PORT", "6333"))
    )


@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession) -> dict:
    """Create a test user."""
    from app.models.user import User
    from app.core.security import get_password_hash
    
    user = User(
        email="testuser@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_verified=True
    )
    
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "password": "testpass123"
    }


@pytest_asyncio.fixture(scope="function")
async def test_user_token(test_user: dict) -> str:
    """Create a JWT token for test user."""
    from app.core.security import create_access_token
    
    token_data = {"sub": test_user["email"], "user_id": test_user["id"]}
    return create_access_token(data=token_data)


@pytest_asyncio.fixture(scope="function")
async def test_api_key(test_db: AsyncSession, test_user: dict) -> str:
    """Create a test API key."""
    from app.models.api_key import APIKey
    from app.models.budget import Budget
    import secrets
    
    # Create budget
    budget = Budget(
        id=str(uuid.uuid4()),
        user_id=test_user["id"],
        limit_amount=100.0,
        period="monthly",
        current_usage=0.0,
        is_active=True
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
        is_active=True
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
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
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
        - Chatbot creation and management
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