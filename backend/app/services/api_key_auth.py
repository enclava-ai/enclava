"""
API Key Authentication Service
Handles API key validation and user authentication with Redis caching for performance
"""

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_api_key
from app.db.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.services.cached_api_key import cached_api_key_service
from app.utils.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class _TestModeAPIKey:
    """Minimal API key object for live test-mode e2e requests."""

    id = 1
    user_id = 1
    name = "Test API Key"
    key_prefix = "sk-test"
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

    def is_valid(self) -> bool:
        return True

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


def _get_test_mode_context(api_key: str) -> Optional[Dict[str, Any]]:
    if not (settings.TESTING or settings.LLM_TEST_MODE):
        return None
    if not (api_key.startswith("sk-test-") or api_key.startswith("ce_test")):
        return None

    key = _TestModeAPIKey()
    key.key_prefix = "ce_test" if api_key.startswith("ce_test") else "sk-test"
    user = SimpleNamespace(
        id=key.user_id,
        email="test@example.com",
        username="testuser",
        is_active=True,
        is_superuser=True,
    )
    return {
        "auth_type": "api_key",
        "api_key": key,
        "api_key_id": key.id,
        "api_key_name": key.name,
        "user": user,
        "user_id": user.id,
    }


async def get_api_key_from_db(api_key: str) -> Optional[Dict[str, Any]]:
    """
    Backward-compatible lookup hook for legacy tests/integrations.

    The production path uses APIKeyAuthService with cache-aware database lookup.
    Older tests patch this function directly, so the default implementation
    intentionally returns None instead of duplicating the service query path.
    """
    return None


def _is_expired(expires_at: Optional[datetime]) -> bool:
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


async def validate_api_key(api_key: str) -> bool:
    """Legacy boolean API-key validator."""
    api_key_data = await get_api_key_from_db(api_key)
    if not api_key_data:
        return False

    if not api_key_data.get("is_active", False):
        return False

    if _is_expired(api_key_data.get("expires_at")):
        return False

    key_hash = api_key_data.get("key_hash") or api_key_data.get("hashed_key")
    if not key_hash:
        return False

    return verify_api_key(api_key, key_hash)


async def get_api_key_info(api_key: str) -> Optional[Dict[str, Any]]:
    """Legacy API-key info helper that returns metadata for valid keys."""
    if not await validate_api_key(api_key):
        return None

    api_key_data = await get_api_key_from_db(api_key)
    if not api_key_data:
        return None

    return {
        key: value
        for key, value in api_key_data.items()
        if key not in {"key_hash", "hashed_key"}
    }


class APIKeyAuthService:
    """Service for API key authentication and validation"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_api_key(
        self, api_key: str, request: Request
    ) -> Optional[Dict[str, Any]]:
        """Validate API key and return user context using Redis cache for performance"""
        try:
            if not api_key:
                return None

            # Extract key prefix for lookup
            if len(api_key) < 8:
                logger.warning(f"Invalid API key format: too short")
                return None

            key_prefix = api_key[:8]
            # SECURITY FIX #42: Redact API key prefix in logs - show only last 4 chars
            redacted_prefix = f"****{key_prefix[-4:]}"

            # Try cached verification first
            cached_verification = await cached_api_key_service.verify_api_key_cached(
                api_key, key_prefix
            )

            # Get API key data from cache or database
            context = await cached_api_key_service.get_cached_api_key(
                key_prefix, self.db
            )

            if not context:
                logger.warning(f"API key not found: {redacted_prefix}")
                return None

            api_key_obj = context["api_key"]

            # If not in verification cache, verify and cache the result
            if not cached_verification:
                # Get the actual key hash for verification (this should be in the cached context)
                db_api_key = None
                if not hasattr(api_key_obj, "key_hash"):
                    # Fallback: fetch full API key from database for hash
                    stmt = select(APIKey).where(APIKey.key_prefix == key_prefix)
                    result = await self.db.execute(stmt)
                    db_api_key = result.scalar_one_or_none()
                    if not db_api_key:
                        return None
                    key_hash = db_api_key.key_hash
                else:
                    key_hash = api_key_obj.key_hash

                # Verify the API key hash
                if not verify_api_key(api_key, key_hash):
                    logger.warning(f"Invalid API key hash: {redacted_prefix}")
                    return None

                # Cache successful verification
                await cached_api_key_service.cache_verification_result(
                    api_key, key_prefix, key_hash, True
                )

            # Check if key is valid (expiry, active status)
            if not api_key_obj.is_valid():
                logger.warning(f"API key expired or inactive: {redacted_prefix}")
                # Invalidate cache for expired keys
                await cached_api_key_service.invalidate_api_key_cache(key_prefix)
                return None

            # Check IP restrictions
            client_ip = request.client.host if request.client else "unknown"
            if not api_key_obj.can_access_from_ip(client_ip):
                logger.warning(
                    f"IP not allowed for API key {redacted_prefix}: {client_ip}"
                )
                return None

            # Update last used timestamp asynchronously (performance optimization)
            await cached_api_key_service.update_last_used(
                context["api_key_id"], self.db
            )

            return context

        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return None

    async def check_endpoint_permission(
        self, context: Dict[str, Any], endpoint: str
    ) -> bool:
        """Check if API key has permission to access endpoint"""
        api_key: APIKey = context.get("api_key")
        if not api_key:
            return False

        return api_key.can_access_endpoint(endpoint)

    async def check_model_permission(self, context: Dict[str, Any], model: str) -> bool:
        """Check if API key has permission to access model"""
        api_key: APIKey = context.get("api_key")
        if not api_key:
            return False

        return api_key.can_access_model(model)

    async def check_scope_permission(self, context: Dict[str, Any], scope: str) -> bool:
        """Check if API key has required scope"""
        api_key: APIKey = context.get("api_key")
        if not api_key:
            return False

        return api_key.has_scope(scope)

    async def update_usage_stats(
        self, context: Dict[str, Any], tokens_used: int = 0, cost_cents: int = 0
    ):
        """Update API key usage statistics"""
        try:
            api_key: APIKey = context.get("api_key")
            if api_key:
                api_key.update_usage(tokens_used, cost_cents)
                await self.db.commit()
                logger.info(
                    f"Updated usage for API key {api_key.key_prefix}: +{tokens_used} tokens, +{cost_cents} cents"
                )
        except Exception as e:
            logger.error(f"Failed to update usage stats: {e}")


async def get_api_key_context(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Dependency to get API key context from request"""
    auth_service = APIKeyAuthService(db)

    # Try different auth methods
    api_key = None

    # 1. Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Skip if token looks like a JWT (starts with "eyJ" = base64 '{"')
        # JWTs are handled by get_current_user, not API key auth
        if not token.startswith("eyJ"):
            api_key = token

    # 2. Check X-API-Key header
    if not api_key:
        api_key = request.headers.get("X-API-Key")

    # SECURITY FIX #36: API key in query parameters is deprecated and rejected
    # Query params can be logged in access logs, browser history, and referrer headers
    query_api_key = request.query_params.get("api_key")
    if query_api_key:
        logger.warning(
            "DEPRECATED_API_KEY_IN_QUERY_PARAM",
            extra={
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        # Reject API key in query params for security
        # If you need a migration period, you can temporarily allow it with a warning
        # For now, we reject it outright
        return None

    if not api_key:
        return None

    test_context = _get_test_mode_context(api_key)
    if test_context:
        request.state.api_key = test_context["api_key"]
        request.state.auth_context = test_context
        return test_context

    context = await auth_service.validate_api_key(api_key, request)

    # Store API key on request.state for middleware access (Issue #4 fix)
    if context:
        api_key_obj = context.get("api_key")
        if api_key_obj:
            request.state.api_key = api_key_obj
        # Also store full auth context
        request.state.auth_context = context

    return context


async def require_api_key(
    context: Dict[str, Any] = Depends(get_api_key_context),
) -> Dict[str, Any]:
    """Dependency that requires valid API key"""
    if not context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: valid API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return context


async def get_current_api_key_user(
    context: Dict[str, Any] = Depends(require_api_key),
) -> tuple:
    """
    Dependency that returns current user and API key as a tuple

    Returns:
        tuple: (user, api_key)
    """
    user = context.get("user")
    api_key = context.get("api_key")

    if not user or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or API key not found in context",
        )

    return user, api_key


async def get_api_key_auth(
    context: Dict[str, Any] = Depends(require_api_key),
) -> APIKey:
    """
    Dependency that returns the authenticated API key object

    Returns:
        APIKey: The authenticated API key object
    """
    api_key = context.get("api_key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key not found in context",
        )

    return api_key


class RequireScope:
    """Dependency class for scope checking"""

    def __init__(self, scope: str):
        self.scope = scope

    async def __call__(self, context: Dict[str, Any] = Depends(require_api_key)):
        auth_service = APIKeyAuthService(context.get("db"))
        if not await auth_service.check_scope_permission(context, self.scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{self.scope}' required",
            )
        return context


class RequireModel:
    """Dependency class for model access checking"""

    def __init__(self, model: str):
        self.model = model

    async def __call__(self, context: Dict[str, Any] = Depends(require_api_key)):
        auth_service = APIKeyAuthService(context.get("db"))
        if not await auth_service.check_model_permission(context, self.model):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Model '{self.model}' not allowed",
            )
        return context
