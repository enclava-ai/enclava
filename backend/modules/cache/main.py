"""
Cache module implementation with Redis backend
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio import Redis
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import log_module_event

logger = logging.getLogger(__name__)


class CacheModule:
    """Redis-based cache module for request/response caching"""
    
    def __init__(self):
        self.redis_client: Optional[Redis] = None
        self.config: Dict[str, Any] = {}
        self.enabled = False
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_requests": 0
        }
    
    async def initialize(self):
        """Initialize the cache module"""
        
        try:
            # Initialize Redis connection
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            await self.redis_client.ping()
            
            self.enabled = True
            log_module_event("cache", "initialized", {
                "provider": self.config.get("provider", "redis"),
                "ttl": self.config.get("ttl", 3600),
                "max_size": self.config.get("max_size", 10000)
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize cache module: {e}")
            log_module_event("cache", "initialization_failed", {"error": str(e)})
            self.enabled = False
            raise
    
    async def cleanup(self):
        """Cleanup cache resources"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
        
        self.enabled = False
        log_module_event("cache", "cleanup", {"success": True})
    
    def _get_cache_key(self, key: str, prefix: str = "ce") -> str:
        """Generate cache key with prefix"""
        return f"{prefix}:{key}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        if not self.enabled:
            return default
        
        try:
            cache_key = self._get_cache_key(key)
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
            logger.error(f"Cache get error: {e}")
            self.stats["errors"] += 1
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(key)
            ttl = ttl or self.config.get("ttl", 3600)
            
            # Serialize complex objects as JSON
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value)
            
            await self.redis_client.setex(cache_key, ttl, value)
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(key)
            result = await self.redis_client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(key)
            return await self.redis_client.exists(cache_key) > 0
            
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear keys matching pattern"""
        if not self.enabled:
            return 0
        
        try:
            cache_pattern = self._get_cache_key(pattern)
            keys = await self.redis_client.keys(cache_pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def clear_all(self) -> bool:
        """Clear all cache entries"""
        if not self.enabled:
            return False
        
        try:
            await self.redis_client.flushdb()
            return True
            
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = self.stats.copy()
        
        if self.enabled:
            try:
                info = await self.redis_client.info()
                stats.update({
                    "redis_memory_used": info.get("used_memory_human", "N/A"),
                    "redis_connected_clients": info.get("connected_clients", 0),
                    "redis_total_commands": info.get("total_commands_processed", 0),
                    "hit_rate": round(
                        (stats["hits"] / stats["total_requests"]) * 100, 2
                    ) if stats["total_requests"] > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
        
        return stats
    
    async def pre_request_interceptor(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-request interceptor for caching"""
        if not self.enabled:
            return context
        
        request = context.get("request")
        if not request:
            return context
        
        # Only cache GET requests
        if request.method != "GET":
            return context
        
        # Generate cache key from request
        cache_key = f"request:{request.method}:{request.url.path}"
        if request.query_params:
            cache_key += f":{hash(str(request.query_params))}"
        
        # Check if cached response exists
        cached_response = await self.get(cache_key)
        if cached_response:
            log_module_event("cache", "hit", {"cache_key": cache_key})
            context["cached_response"] = cached_response
            context["cache_hit"] = True
        else:
            log_module_event("cache", "miss", {"cache_key": cache_key})
            context["cache_key"] = cache_key
            context["cache_hit"] = False
        
        return context
    
    async def post_response_interceptor(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Post-response interceptor for caching"""
        if not self.enabled:
            return context
        
        # Skip if this was a cache hit
        if context.get("cache_hit"):
            return context
        
        cache_key = context.get("cache_key")
        response = context.get("response")
        
        if cache_key and response and response.status_code == 200:
            # Cache successful responses
            cache_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.body.decode() if hasattr(response, 'body') else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.set(cache_key, cache_data)
            log_module_event("cache", "stored", {"cache_key": cache_key})
        
        return context

# Global cache instance
cache_module = CacheModule()

# Module interface functions
async def initialize():
    """Initialize cache module"""
    await cache_module.initialize()

async def cleanup():
    """Cleanup cache module"""
    await cache_module.cleanup()

async def pre_request_interceptor(context: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-request interceptor"""
    return await cache_module.pre_request_interceptor(context)

async def post_response_interceptor(context: Dict[str, Any]) -> Dict[str, Any]:
    """Post-response interceptor"""
    return await cache_module.post_response_interceptor(context)# Force reload
# Trigger reload
