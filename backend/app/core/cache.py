"""
Core Cache Service - Redis-based caching infrastructure
Consolidates all caching functionality into core system infrastructure
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)


class CoreCacheService:
    """Core Redis-based cache service for system-wide caching"""
    
    def __init__(self):
        self.redis_pool: Optional[ConnectionPool] = None
        self.redis_client: Optional[Redis] = None
        self.enabled = False
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_requests": 0
        }
    
    async def initialize(self):
        """Initialize the core cache service with connection pool"""
        try:
            # Create Redis connection pool for better resource management
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            
            self.redis_pool = ConnectionPool.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=20,  # Shared pool for all cache operations
                health_check_interval=30
            )
            
            self.redis_client = Redis(connection_pool=self.redis_pool)
            
            # Test connection
            await self.redis_client.ping()
            
            self.enabled = True
            logger.info("Core cache service initialized with Redis connection pool")
            
        except Exception as e:
            logger.error(f"Failed to initialize core cache service: {e}")
            self.enabled = False
            raise
    
    async def cleanup(self):
        """Cleanup cache resources"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
        
        if self.redis_pool:
            await self.redis_pool.disconnect()
            self.redis_pool = None
        
        self.enabled = False
        logger.info("Core cache service cleaned up")
    
    def _get_cache_key(self, key: str, prefix: str = "core") -> str:
        """Generate cache key with prefix"""
        return f"{prefix}:{key}"
    
    async def get(self, key: str, default: Any = None, prefix: str = "core") -> Any:
        """Get value from cache"""
        if not self.enabled:
            return default
        
        try:
            cache_key = self._get_cache_key(key, prefix)
            value = await self.redis_client.get(cache_key)
            
            if value is None:
                self.stats["misses"] += 1
                return default
            
            self.stats["hits"] += 1
            self.stats["total_requests"] += 1
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats["errors"] += 1
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, prefix: str = "core") -> bool:
        """Set value in cache"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(key, prefix)
            ttl = ttl or 3600  # Default 1 hour TTL
            
            # Serialize complex objects as JSON
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value)
            
            await self.redis_client.setex(cache_key, ttl, value)
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def delete(self, key: str, prefix: str = "core") -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(key, prefix)
            result = await self.redis_client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def exists(self, key: str, prefix: str = "core") -> bool:
        """Check if key exists in cache"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(key, prefix)
            return await self.redis_client.exists(cache_key) > 0
            
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def clear_pattern(self, pattern: str, prefix: str = "core") -> int:
        """Clear keys matching pattern"""
        if not self.enabled:
            return 0
        
        try:
            cache_pattern = self._get_cache_key(pattern, prefix)
            keys = await self.redis_client.keys(cache_pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear pattern error for pattern {pattern}: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None, prefix: str = "core") -> int:
        """Increment counter with optional TTL"""
        if not self.enabled:
            return 0
        
        try:
            cache_key = self._get_cache_key(key, prefix)
            
            # Use pipeline for atomic increment + expire
            async with self.redis_client.pipeline() as pipe:
                await pipe.incr(cache_key, amount)
                if ttl:
                    await pipe.expire(cache_key, ttl)
                results = await pipe.execute()
                return results[0]
                
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = self.stats.copy()
        
        if self.enabled:
            try:
                info = await self.redis_client.info()
                stats.update({
                    "redis_memory_used": info.get("used_memory_human", "N/A"),
                    "redis_connected_clients": info.get("connected_clients", 0),
                    "redis_total_commands": info.get("total_commands_processed", 0),
                    "redis_keyspace_hits": info.get("keyspace_hits", 0),
                    "redis_keyspace_misses": info.get("keyspace_misses", 0),
                    "connection_pool_size": self.redis_pool.connection_pool_size if self.redis_pool else 0,
                    "hit_rate": round(
                        (stats["hits"] / stats["total_requests"]) * 100, 2
                    ) if stats["total_requests"] > 0 else 0,
                    "enabled": True
                })
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
                stats["enabled"] = False
        else:
            stats["enabled"] = False
        
        return stats
    
    @asynccontextmanager
    async def pipeline(self):
        """Context manager for Redis pipeline operations"""
        if not self.enabled:
            yield None
            return
        
        async with self.redis_client.pipeline() as pipe:
            yield pipe
    
    # Specialized caching methods for common use cases
    
    async def cache_api_key(self, key_prefix: str, api_key_data: Dict[str, Any], ttl: int = 300) -> bool:
        """Cache API key data for authentication"""
        return await self.set(key_prefix, api_key_data, ttl, prefix="auth")
    
    async def get_cached_api_key(self, key_prefix: str) -> Optional[Dict[str, Any]]:
        """Get cached API key data"""
        return await self.get(key_prefix, prefix="auth")
    
    async def invalidate_api_key(self, key_prefix: str) -> bool:
        """Invalidate cached API key"""
        return await self.delete(key_prefix, prefix="auth")
    
    async def cache_verification_result(self, api_key: str, key_prefix: str, key_hash: str, is_valid: bool, ttl: int = 300) -> bool:
        """Cache API key verification result to avoid expensive bcrypt operations"""
        verification_data = {
            "key_hash": key_hash,
            "is_valid": is_valid,
            "timestamp": datetime.utcnow().isoformat()
        }
        return await self.set(f"verify:{key_prefix}", verification_data, ttl, prefix="auth")
    
    async def get_cached_verification(self, key_prefix: str) -> Optional[Dict[str, Any]]:
        """Get cached verification result"""
        return await self.get(f"verify:{key_prefix}", prefix="auth")
    
    async def cache_rate_limit(self, identifier: str, window_seconds: int, limit: int, current_count: int = 1) -> Dict[str, Any]:
        """Cache and track rate limit state"""
        key = f"rate_limit:{identifier}:{window_seconds}"
        
        try:
            # Use atomic increment with expiry
            count = await self.increment(key, current_count, window_seconds, prefix="rate")
            
            remaining = max(0, limit - count)
            reset_time = int((datetime.utcnow() + timedelta(seconds=window_seconds)).timestamp())
            
            return {
                "count": count,
                "limit": limit,
                "remaining": remaining,
                "reset_time": reset_time,
                "exceeded": count > limit
            }
        except Exception as e:
            logger.error(f"Rate limit cache error: {e}")
            # Return permissive defaults on cache failure
            return {
                "count": 0,
                "limit": limit,
                "remaining": limit,
                "reset_time": int((datetime.utcnow() + timedelta(seconds=window_seconds)).timestamp()),
                "exceeded": False
            }


# Global core cache service instance
core_cache = CoreCacheService()


# Convenience functions for backward compatibility and ease of use
async def get(key: str, default: Any = None, prefix: str = "core") -> Any:
    """Get value from core cache"""
    return await core_cache.get(key, default, prefix)


async def set(key: str, value: Any, ttl: Optional[int] = None, prefix: str = "core") -> bool:
    """Set value in core cache"""
    return await core_cache.set(key, value, ttl, prefix)


async def delete(key: str, prefix: str = "core") -> bool:
    """Delete key from core cache"""
    return await core_cache.delete(key, prefix)


async def exists(key: str, prefix: str = "core") -> bool:
    """Check if key exists in core cache"""
    return await core_cache.exists(key, prefix)


async def clear_pattern(pattern: str, prefix: str = "core") -> int:
    """Clear keys matching pattern from core cache"""
    return await core_cache.clear_pattern(pattern, prefix)


async def get_stats() -> Dict[str, Any]:
    """Get core cache statistics"""
    return await core_cache.get_stats()