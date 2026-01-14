"""
Cached API Key Service - Refactored to use Core Cache Infrastructure
High-performance Redis-based API key caching to reduce authentication overhead
from ~60ms to ~5ms by avoiding expensive bcrypt operations
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import core_cache
from app.core.config import settings
from app.core.security import verify_api_key
from app.models.api_key import APIKey
from app.models.user import User

logger = logging.getLogger(__name__)


class CachedAPIKeyService:
    """Core cache-backed API key caching service for performance optimization"""

    def __init__(self):
        self.cache_ttl = 300  # 5 minutes cache TTL
        self.verification_cache_ttl = 3600  # 1 hour for verification results
        logger.info("Cached API key service initialized with core cache backend")

    async def close(self):
        """Close method for compatibility - core cache handles its own lifecycle"""
        logger.info(
            "Cached API key service close called - core cache handles lifecycle"
        )

    async def get_cached_api_key(
        self, key_prefix: str, db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Get API key data from cache or database
        Returns: Dictionary with api_key, user, and api_key_id
        """
        try:
            # Try cache first
            cached_data = await core_cache.get_cached_api_key(key_prefix)
            if cached_data:
                logger.debug(f"API key cache hit for prefix: {key_prefix}")

                # Recreate APIKey object from cached data
                api_key_data = cached_data.get("api_key_data", {})
                user_data = cached_data.get("user_data", {})

                # Create APIKey instance
                api_key = APIKey(**api_key_data)

                # Create User instance
                user = User(**user_data)

                return {
                    "api_key": api_key,
                    "user": user,
                    "api_key_id": api_key_data.get("id"),
                }

            logger.debug(
                f"API key cache miss for prefix: {key_prefix}, fetching from database"
            )

            # Cache miss - fetch from database with optimized query
            stmt = (
                select(APIKey, User)
                .join(User, APIKey.user_id == User.id)
                .options(joinedload(APIKey.user), joinedload(User.api_keys))
                .where(APIKey.key_prefix == key_prefix)
                .where(APIKey.is_active == True)
            )

            result = await db.execute(stmt)
            api_key_user = result.first()

            if not api_key_user:
                logger.debug(f"API key not found in database for prefix: {key_prefix}")
                return None

            api_key, user = api_key_user

            # Cache for future requests
            await self._cache_api_key_data(key_prefix, api_key, user)

            return {"api_key": api_key, "user": user, "api_key_id": api_key.id}

        except Exception as e:
            logger.error(f"Error retrieving API key for prefix {key_prefix}: {e}")
            return None

    async def _cache_api_key_data(self, key_prefix: str, api_key: APIKey, user: User):
        """Cache API key and user data"""
        try:
            # Serialize data for caching
            cache_data = {
                "api_key_data": {
                    "id": api_key.id,
                    "name": api_key.name,
                    "key_hash": api_key.key_hash,
                    "key_prefix": api_key.key_prefix,
                    "user_id": api_key.user_id,
                    "is_active": api_key.is_active,
                    "permissions": api_key.permissions,
                    "scopes": api_key.scopes,
                    "rate_limit_per_minute": api_key.rate_limit_per_minute,
                    "rate_limit_per_hour": api_key.rate_limit_per_hour,
                    "rate_limit_per_day": api_key.rate_limit_per_day,
                    "allowed_models": api_key.allowed_models,
                    "allowed_endpoints": api_key.allowed_endpoints,
                    "allowed_ips": api_key.allowed_ips,
                    "description": api_key.description,
                    "tags": api_key.tags,
                    "created_at": api_key.created_at.isoformat()
                    if api_key.created_at
                    else None,
                    "updated_at": api_key.updated_at.isoformat()
                    if api_key.updated_at
                    else None,
                    "last_used_at": api_key.last_used_at.isoformat()
                    if api_key.last_used_at
                    else None,
                    "expires_at": api_key.expires_at.isoformat()
                    if api_key.expires_at
                    else None,
                    "total_requests": api_key.total_requests,
                    "total_tokens": api_key.total_tokens,
                    "total_cost": api_key.total_cost,
                    "is_unlimited": api_key.is_unlimited,
                    "budget_limit_cents": api_key.budget_limit_cents,
                    "budget_type": api_key.budget_type,
                    "allowed_chatbots": api_key.allowed_chatbots,
                    "allowed_agents": api_key.allowed_agents,
                },
                "user_data": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser,
                    "role_id": user.role_id,  # Use column instead of relationship to avoid lazy loading
                    "created_at": user.created_at.isoformat()
                    if user.created_at
                    else None,
                    "updated_at": user.updated_at.isoformat()
                    if user.updated_at
                    else None,
                    "last_login": user.last_login.isoformat()
                    if user.last_login
                    else None,
                },
                "cached_at": datetime.utcnow().isoformat(),
            }

            await core_cache.cache_api_key(key_prefix, cache_data, self.cache_ttl)
            logger.debug(f"Cached API key data for prefix: {key_prefix}")

        except Exception as e:
            logger.error(f"Error caching API key data for prefix {key_prefix}: {e}")

    async def verify_api_key_cached(
        self, api_key: str, key_prefix: str
    ) -> Optional[bool]:
        """
        Verify API key using cached hash to avoid expensive bcrypt operations
        Returns: True if verified, False if invalid, None if not cached
        """
        try:
            # Check verification cache
            cached_verification = await core_cache.get_cached_verification(key_prefix)

            if cached_verification:
                # Check if cache is still valid (within TTL)
                cached_timestamp = datetime.fromisoformat(
                    cached_verification["timestamp"]
                )
                if datetime.utcnow() - cached_timestamp < timedelta(
                    seconds=self.verification_cache_ttl
                ):
                    logger.debug(
                        f"API key verification cache hit for prefix: {key_prefix}"
                    )
                    return cached_verification.get("is_valid", False)

            return None  # Not cached or expired

        except Exception as e:
            logger.error(
                f"Error checking verification cache for prefix {key_prefix}: {e}"
            )
            return None

    async def cache_verification_result(
        self, api_key: str, key_prefix: str, key_hash: str, is_valid: bool
    ):
        """Cache API key verification result to avoid expensive bcrypt operations"""
        try:
            await core_cache.cache_verification_result(
                api_key, key_prefix, key_hash, is_valid, self.verification_cache_ttl
            )
            logger.debug(f"Cached verification result for prefix: {key_prefix}")

        except Exception as e:
            logger.error(
                f"Error caching verification result for prefix {key_prefix}: {e}"
            )

    async def invalidate_api_key_cache(self, key_prefix: str):
        """Invalidate cached API key data"""
        try:
            await core_cache.invalidate_api_key(key_prefix)

            # Also invalidate verification cache
            verification_keys = await core_cache.clear_pattern(
                f"verify:{key_prefix}*", prefix="auth"
            )

            logger.debug(f"Invalidated cache for API key prefix: {key_prefix}")

        except Exception as e:
            logger.error(f"Error invalidating cache for prefix {key_prefix}: {e}")

    async def update_last_used(self, api_key_id: int, db: AsyncSession):
        """Update last used timestamp asynchronously for performance"""
        try:
            # Use core cache to track update requests to avoid database spam
            cache_key = f"last_used_update:{api_key_id}"

            # Check if we recently updated (within 5 minutes)
            last_update = await core_cache.get(cache_key, prefix="perf")
            if last_update:
                return  # Skip update if recent

            # Update database
            stmt = select(APIKey).where(APIKey.id == api_key_id)
            result = await db.execute(stmt)
            api_key = result.scalar_one_or_none()

            if api_key:
                api_key.last_used_at = datetime.utcnow()
                await db.commit()

                # Cache that we updated to prevent spam
                await core_cache.set(
                    cache_key, datetime.utcnow().isoformat(), ttl=300, prefix="perf"
                )

                logger.debug(f"Updated last_used_at for API key {api_key_id}")

        except Exception as e:
            logger.error(f"Error updating last_used for API key {api_key_id}: {e}")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        try:
            core_stats = await core_cache.get_stats()
            return {
                "cache_backend": "core_cache",
                "cache_enabled": core_stats.get("enabled", False),
                "cache_stats": core_stats,
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "cache_backend": "core_cache",
                "cache_enabled": False,
                "error": str(e),
            }


# Global instance
cached_api_key_service = CachedAPIKeyService()
