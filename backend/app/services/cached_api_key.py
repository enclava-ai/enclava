"""
Cached API Key Service
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

from app.core.config import settings
from app.core.security import verify_api_key
from app.models.api_key import APIKey
from app.models.user import User

# Check Redis availability at runtime, not import time
aioredis = None
REDIS_AVAILABLE = False

def _import_aioredis():
    """Import aioredis at runtime"""
    global aioredis, REDIS_AVAILABLE
    if aioredis is None:
        try:
            import aioredis as _aioredis
            aioredis = _aioredis
            REDIS_AVAILABLE = True
            return True
        except ImportError as e:
            REDIS_AVAILABLE = False
            return False
        except Exception as e:
            # Handle the Python 3.11 + aioredis 2.0.1 compatibility issue
            REDIS_AVAILABLE = False
            return False
    return REDIS_AVAILABLE

logger = logging.getLogger(__name__)


class CachedAPIKeyService:
    """Redis-backed API key caching service for performance optimization with fallback to optimized database queries"""
    
    def __init__(self):
        self.redis = None
        self.cache_ttl = 300  # 5 minutes cache TTL
        self.verification_cache_ttl = 3600  # 1 hour for verification results
        self.redis_enabled = _import_aioredis()
        
        if not self.redis_enabled:
            logger.warning("Redis not available, falling back to optimized database queries only")
        
    async def get_redis(self):
        """Get Redis connection, create if doesn't exist"""
        if not self.redis_enabled or not REDIS_AVAILABLE:
            return None
            
        if not self.redis and aioredis:
            try:
                self.redis = aioredis.from_url(
                    settings.REDIS_URL, 
                    encoding="utf-8", 
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test the connection
                await self.redis.ping()
                logger.info("Redis connection established for API key caching")
            except Exception as e:
                logger.warning(f"Redis connection failed, disabling cache: {e}")
                self.redis_enabled = False
                self.redis = None
                
        return self.redis
    
    async def close(self):
        """Close Redis connection"""
        if self.redis and self.redis_enabled:
            try:
                await self.redis.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
    
    def _get_cache_key(self, key_prefix: str) -> str:
        """Generate cache key for API key data"""
        return f"api_key:data:{key_prefix}"
    
    def _get_verification_cache_key(self, key_prefix: str, key_suffix_hash: str) -> str:
        """Generate cache key for API key verification results"""
        return f"api_key:verified:{key_prefix}:{key_suffix_hash}"
    
    def _get_last_used_cache_key(self, api_key_id: int) -> str:
        """Generate cache key for last used timestamp"""
        return f"api_key:last_used:{api_key_id}"
    
    async def _serialize_api_key_data(self, api_key: APIKey, user: User) -> str:
        """Serialize API key and user data for caching"""
        data = {
            # API Key data
            "api_key_id": api_key.id,
            "api_key_name": api_key.name,
            "key_hash": api_key.key_hash,
            "key_prefix": api_key.key_prefix,
            "is_active": api_key.is_active,
            "permissions": api_key.permissions,
            "scopes": api_key.scopes,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "rate_limit_per_hour": api_key.rate_limit_per_hour,
            "rate_limit_per_day": api_key.rate_limit_per_day,
            "allowed_models": api_key.allowed_models,
            "allowed_endpoints": api_key.allowed_endpoints,
            "allowed_ips": api_key.allowed_ips,
            "is_unlimited": api_key.is_unlimited,
            "budget_limit_cents": api_key.budget_limit_cents,
            "budget_type": api_key.budget_type,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "total_requests": api_key.total_requests,
            "total_tokens": api_key.total_tokens,
            "total_cost": api_key.total_cost,
            
            # User data
            "user_id": user.id,
            "user_email": user.email,
            "user_role": user.role,
            "user_is_active": user.is_active,
            
            # Cache metadata
            "cached_at": datetime.utcnow().isoformat()
        }
        return json.dumps(data, default=str)
    
    async def _deserialize_api_key_data(self, cached_data: str) -> Optional[Dict[str, Any]]:
        """Deserialize cached API key data"""
        try:
            data = json.loads(cached_data)
            
            # Check if cached data is still valid
            if data.get("expires_at"):
                expires_at = datetime.fromisoformat(data["expires_at"])
                if datetime.utcnow() > expires_at:
                    return None
            
            # Reconstruct the context object expected by the rest of the system
            context = {
                "user_id": data["user_id"],
                "user_email": data["user_email"],
                "user_role": data["user_role"],
                "api_key_id": data["api_key_id"],
                "api_key_name": data["api_key_name"],
                "permissions": data["permissions"],
                "scopes": data["scopes"],
                "rate_limits": {
                    "per_minute": data["rate_limit_per_minute"],
                    "per_hour": data["rate_limit_per_hour"],
                    "per_day": data["rate_limit_per_day"]
                },
                # Create minimal API key object with necessary attributes
                "api_key": type("APIKey", (), {
                    "id": data["api_key_id"],
                    "name": data["api_key_name"],
                    "key_prefix": data["key_prefix"],
                    "is_active": data["is_active"],
                    "permissions": data["permissions"],
                    "scopes": data["scopes"],
                    "allowed_models": data["allowed_models"],
                    "allowed_endpoints": data["allowed_endpoints"],
                    "allowed_ips": data["allowed_ips"],
                    "is_unlimited": data["is_unlimited"],
                    "budget_limit_cents": data["budget_limit_cents"],
                    "budget_type": data["budget_type"],
                    "total_requests": data["total_requests"],
                    "total_tokens": data["total_tokens"],
                    "total_cost": data["total_cost"],
                    "expires_at": datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
                    "can_access_model": lambda model: not data["allowed_models"] or model in data["allowed_models"],
                    "can_access_endpoint": lambda endpoint: not data["allowed_endpoints"] or endpoint in data["allowed_endpoints"],
                    "can_access_from_ip": lambda ip: not data["allowed_ips"] or ip in data["allowed_ips"],
                    "has_scope": lambda scope: scope in data["scopes"],
                    "is_valid": lambda: data["is_active"] and (not data.get("expires_at") or datetime.utcnow() <= datetime.fromisoformat(data["expires_at"])),
                    "update_usage": lambda tokens, cost: None  # Handled separately for cache consistency
                })(),
                # Create minimal user object
                "user": type("User", (), {
                    "id": data["user_id"],
                    "email": data["user_email"],
                    "role": data["user_role"],
                    "is_active": data["user_is_active"]
                })()
            }
            
            return context
            
        except Exception as e:
            logger.warning(f"Failed to deserialize cached API key data: {e}")
            return None
    
    async def get_cached_api_key(self, key_prefix: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get API key data from cache or database with optimized queries"""
        try:
            redis = await self.get_redis()
            
            # If Redis is available, try cache first
            if redis:
                cache_key = self._get_cache_key(key_prefix)
                
                # Try to get from cache first
                cached_data = await redis.get(cache_key)
                if cached_data:
                    logger.debug(f"API key cache hit for {key_prefix}")
                    context = await self._deserialize_api_key_data(cached_data)
                    if context:
                        return context
                    else:
                        # Invalid cached data, remove it
                        await redis.delete(cache_key)
                
                logger.debug(f"API key cache miss for {key_prefix}, fetching from database")
            else:
                logger.debug(f"Redis not available, fetching API key {key_prefix} from database with optimized query")
            
            # Cache miss or Redis not available - fetch from database with optimized query
            context = await self._fetch_from_database(key_prefix, db)
            
            # If Redis is available and we have data, cache it
            if context and redis:
                try:
                    api_key = context["api_key"]
                    user = context["user"]
                    
                    # Reconstruct full objects for serialization
                    full_api_key = await self._get_full_api_key_from_db(key_prefix, db)
                    if full_api_key:
                        cached_data = await self._serialize_api_key_data(full_api_key, user)
                        await redis.setex(cache_key, self.cache_ttl, cached_data)
                        logger.debug(f"Cached API key data for {key_prefix}")
                except Exception as cache_error:
                    logger.warning(f"Failed to cache API key data: {cache_error}")
                    # Don't fail the request if caching fails
            
            return context
            
        except Exception as e:
            logger.error(f"Error in cached API key lookup for {key_prefix}: {e}")
            # Fallback to database
            return await self._fetch_from_database(key_prefix, db)
    
    async def _get_full_api_key_from_db(self, key_prefix: str, db: AsyncSession) -> Optional[APIKey]:
        """Helper to get full API key object from database"""
        stmt = select(APIKey).where(APIKey.key_prefix == key_prefix)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _fetch_from_database(self, key_prefix: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Fetch API key and user data from database with optimized query"""
        try:
            # Optimized query with joinedload to eliminate N+1 query problem
            stmt = select(APIKey).options(
                joinedload(APIKey.user)
            ).where(APIKey.key_prefix == key_prefix)
            
            result = await db.execute(stmt)
            api_key = result.scalar_one_or_none()
            
            if not api_key:
                logger.warning(f"API key not found: {key_prefix}")
                return None
            
            user = api_key.user
            if not user or not user.is_active:
                logger.warning(f"User not found or inactive for API key: {key_prefix}")
                return None
            
            # Return the same structure as the original service
            return {
                "user_id": user.id,
                "user_email": user.email,
                "user_role": user.role,
                "api_key_id": api_key.id,
                "api_key_name": api_key.name,
                "api_key": api_key,
                "user": user,
                "permissions": api_key.permissions,
                "scopes": api_key.scopes,
                "rate_limits": {
                    "per_minute": api_key.rate_limit_per_minute,
                    "per_hour": api_key.rate_limit_per_hour,
                    "per_day": api_key.rate_limit_per_day
                }
            }
            
        except Exception as e:
            logger.error(f"Database error fetching API key {key_prefix}: {e}")
            return None
    
    async def verify_api_key_cached(self, api_key: str, key_prefix: str) -> bool:
        """Cache API key verification results to avoid repeated bcrypt operations"""
        try:
            redis = await self.get_redis()
            
            # If Redis is not available, skip caching
            if not redis:
                logger.debug(f"Redis not available, skipping verification cache for {key_prefix}")
                return False  # Caller should handle full verification
            
            # Create a hash of the key suffix for cache key (never store the actual key)
            import hashlib
            key_suffix = api_key[8:] if len(api_key) > 8 else api_key
            key_suffix_hash = hashlib.sha256(key_suffix.encode()).hexdigest()[:16]
            
            verification_cache_key = self._get_verification_cache_key(key_prefix, key_suffix_hash)
            
            # Check verification cache
            cached_result = await redis.get(verification_cache_key)
            if cached_result:
                logger.debug(f"API key verification cache hit for {key_prefix}")
                return cached_result == "valid"
            
            # Need to do actual verification - get the hash from database
            # This should be called only after we've confirmed the key exists
            logger.debug(f"API key verification cache miss for {key_prefix}")
            return False  # Caller should handle full verification
            
        except Exception as e:
            logger.warning(f"Error in verification cache for {key_prefix}: {e}")
            return False
    
    async def cache_verification_result(self, api_key: str, key_prefix: str, key_hash: str, is_valid: bool):
        """Cache the verification result to avoid future bcrypt operations"""
        try:
            # Only cache successful verifications and do actual verification
            actual_valid = verify_api_key(api_key, key_hash)
            if actual_valid != is_valid:
                logger.warning(f"Verification mismatch for {key_prefix}")
                return
            
            if actual_valid:
                redis = await self.get_redis()
                
                # If Redis is not available, skip caching
                if not redis:
                    logger.debug(f"Redis not available, skipping verification result cache for {key_prefix}")
                    return
                
                # Create a hash of the key suffix for cache key
                import hashlib
                key_suffix = api_key[8:] if len(api_key) > 8 else api_key
                key_suffix_hash = hashlib.sha256(key_suffix.encode()).hexdigest()[:16]
                
                verification_cache_key = self._get_verification_cache_key(key_prefix, key_suffix_hash)
                
                # Cache successful verification
                await redis.setex(verification_cache_key, self.verification_cache_ttl, "valid")
                logger.debug(f"Cached verification result for {key_prefix}")
                
        except Exception as e:
            logger.warning(f"Error caching verification result for {key_prefix}: {e}")
    
    async def invalidate_api_key_cache(self, key_prefix: str):
        """Invalidate cached data for an API key"""
        try:
            redis = await self.get_redis()
            
            # If Redis is not available, skip invalidation
            if not redis:
                logger.debug(f"Redis not available, skipping cache invalidation for {key_prefix}")
                return
                
            cache_key = self._get_cache_key(key_prefix)
            await redis.delete(cache_key)
            
            # Also invalidate verification cache - get all verification keys for this prefix
            pattern = f"api_key:verified:{key_prefix}:*"
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
                
            logger.debug(f"Invalidated cache for API key {key_prefix}")
            
        except Exception as e:
            logger.warning(f"Error invalidating cache for {key_prefix}: {e}")
    
    async def update_last_used(self, api_key_id: int, db: AsyncSession):
        """Update last used timestamp with write-through cache"""
        try:
            redis = await self.get_redis()
            current_time = datetime.utcnow()
            should_update = True
            
            # If Redis is available, check if we've updated recently (avoid too frequent DB writes)
            if redis:
                cache_key = self._get_last_used_cache_key(api_key_id)
                last_update = await redis.get(cache_key)
                if last_update:
                    last_update_time = datetime.fromisoformat(last_update)
                    if current_time - last_update_time < timedelta(minutes=1):
                        # Skip update if last update was less than 1 minute ago
                        should_update = False
            
            if should_update:
                # Update database
                stmt = select(APIKey).where(APIKey.id == api_key_id)
                result = await db.execute(stmt)
                api_key = result.scalar_one_or_none()
                
                if api_key:
                    api_key.last_used_at = current_time
                    await db.commit()
                    
                    # Update cache if Redis is available
                    if redis:
                        cache_key = self._get_last_used_cache_key(api_key_id)
                        await redis.setex(cache_key, 300, current_time.isoformat())
                    
                    logger.debug(f"Updated last used timestamp for API key {api_key_id}")
                
        except Exception as e:
            logger.warning(f"Error updating last used timestamp for API key {api_key_id}: {e}")


# Global cached service instance
cached_api_key_service = CachedAPIKeyService()