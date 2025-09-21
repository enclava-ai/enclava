"""
Rate limiting middleware
"""

import time
import redis
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiting implementation using Redis"""
    
    def __init__(self):
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.redis_client.ping()  # Test connection
            logger.info("Rate limiter initialized with Redis backend")
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
            self.redis_client = None
            # Fall back to in-memory rate limiting
            self.memory_store: Dict[str, Dict[str, float]] = {}
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        identifier: str = "default"
    ) -> tuple[bool, Dict[str, int]]:
        """
        Check if request is within rate limit
        
        Args:
            key: Rate limiting key (e.g., IP address, API key)
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds
            identifier: Additional identifier for the rate limit
            
        Returns:
            Tuple of (is_allowed, headers_dict)
        """
        
        full_key = f"rate_limit:{identifier}:{key}"
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        if self.redis_client:
            return await self._check_redis_rate_limit(
                full_key, limit, window_seconds, current_time, window_start
            )
        else:
            return self._check_memory_rate_limit(
                full_key, limit, window_seconds, current_time, window_start
            )
    
    async def _check_redis_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        current_time: int,
        window_start: int
    ) -> tuple[bool, Dict[str, int]]:
        """Check rate limit using Redis"""
        
        pipe = self.redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiration
        pipe.expire(key, window_seconds + 1)
        
        results = pipe.execute()
        current_requests = results[1]
        
        # Calculate remaining requests and reset time
        remaining = max(0, limit - current_requests - 1)
        reset_time = current_time + window_seconds
        
        headers = {
            "X-RateLimit-Limit": limit,
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": reset_time,
            "X-RateLimit-Window": window_seconds
        }
        
        is_allowed = current_requests < limit
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for key: {key}")
        
        return is_allowed, headers
    
    def _check_memory_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        current_time: int,
        window_start: int
    ) -> tuple[bool, Dict[str, int]]:
        """Check rate limit using in-memory storage"""
        
        if key not in self.memory_store:
            self.memory_store[key] = {}
        
        # Clean old entries
        store = self.memory_store[key]
        keys_to_remove = [k for k, v in store.items() if v < window_start]
        for k in keys_to_remove:
            del store[k]
        
        current_requests = len(store)
        
        # Calculate remaining requests and reset time
        remaining = max(0, limit - current_requests - 1)
        reset_time = current_time + window_seconds
        
        headers = {
            "X-RateLimit-Limit": limit,
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": reset_time,
            "X-RateLimit-Window": window_seconds
        }
        
        is_allowed = current_requests < limit
        
        if is_allowed:
            # Add current request
            store[str(current_time)] = current_time
        else:
            logger.warning(f"Rate limit exceeded for key: {key}")
        
        return is_allowed, headers


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI"""

    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        logger.info("RateLimitMiddleware initialized")

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting"""

        # Skip rate limiting if disabled in settings
        if not settings.API_RATE_LIMITING_ENABLED:
            response = await call_next(request)
            return response

        # Skip rate limiting for all internal API endpoints (platform operations)
        if request.url.path.startswith("/api-internal/v1/"):
            response = await call_next(request)
            return response

        # Only apply rate limiting to privatemode.ai proxy endpoints (OpenAI-compatible API and LLM service)
        # Skip for all other endpoints
        if not (request.url.path.startswith("/api/v1/chat/completions") or
                request.url.path.startswith("/api/v1/embeddings") or
                request.url.path.startswith("/api/v1/models") or
                request.url.path.startswith("/api/v1/llm/")):
            response = await call_next(request)
            return response

        # Skip rate limiting for health checks and static files
        if request.url.path in ["/health", "/", "/api/v1/docs", "/api/v1/openapi.json"]:
            response = await call_next(request)
            return response

        # Get client IP
        client_ip = request.client.host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # Check for API key in headers
        api_key = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif request.headers.get("X-API-Key"):
            api_key = request.headers.get("X-API-Key")

        # Determine rate limiting strategy
        headers = {}
        is_allowed = True

        if api_key:
            # API key-based rate limiting
            api_key_key = f"api_key:{api_key}"

            # First check organization-wide limits (PrivateMode limits are org-wide)
            org_key = "organization:privatemode"

            # Check organization per-minute limit
            org_allowed_minute, org_headers_minute = await self.rate_limiter.check_rate_limit(
                org_key, settings.PRIVATEMODE_REQUESTS_PER_MINUTE, 60, "minute"
            )

            # Check organization per-hour limit
            org_allowed_hour, org_headers_hour = await self.rate_limiter.check_rate_limit(
                org_key, settings.PRIVATEMODE_REQUESTS_PER_HOUR, 3600, "hour"
            )

            # If organization limits are exceeded, return 429
            if not (org_allowed_minute and org_allowed_hour):
                logger.warning(f"Organization rate limit exceeded for {org_key}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Organization rate limit exceeded"},
                    headers=org_headers_minute
                )

            # Then check per-API key limits
            limit_per_minute = settings.API_RATE_LIMIT_API_KEY_PER_MINUTE
            limit_per_hour = settings.API_RATE_LIMIT_API_KEY_PER_HOUR

            # Check per-minute limit
            is_allowed_minute, headers_minute = await self.rate_limiter.check_rate_limit(
                api_key_key, limit_per_minute, 60, "minute"
            )

            # Check per-hour limit
            is_allowed_hour, headers_hour = await self.rate_limiter.check_rate_limit(
                api_key_key, limit_per_hour, 3600, "hour"
            )

            is_allowed = is_allowed_minute and is_allowed_hour
            headers = headers_minute  # Use minute headers for response

        else:
            # IP-based rate limiting for unauthenticated requests
            rate_limit_key = f"ip:{client_ip}"

            # More restrictive limits for unauthenticated requests
            limit_per_minute = 20  # Hardcoded for unauthenticated users
            limit_per_hour = 100

            # Check per-minute limit
            is_allowed_minute, headers_minute = await self.rate_limiter.check_rate_limit(
                rate_limit_key, limit_per_minute, 60, "minute"
            )

            # Check per-hour limit
            is_allowed_hour, headers_hour = await self.rate_limiter.check_rate_limit(
                rate_limit_key, limit_per_hour, 3600, "hour"
            )

            is_allowed = is_allowed_minute and is_allowed_hour
            headers = headers_minute  # Use minute headers for response

        # If rate limit exceeded, return 429
        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Please try again later.",
                    "details": {
                        "limit": headers["X-RateLimit-Limit"],
                        "reset_time": headers["X-RateLimit-Reset"]
                    }
                },
                headers={k: str(v) for k, v in headers.items()}
            )

        # Continue with request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = str(value)

        return response


# Keep the old function for backward compatibility
async def rate_limit_middleware(request: Request, call_next):
    """Legacy function - use RateLimitMiddleware class instead"""
    middleware = RateLimitMiddleware(None)
    return await middleware.dispatch(request, call_next)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded"""
    
    def __init__(self, limit: int, reset_time: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Limit: {limit}, Reset: {reset_time}"
        )


# Decorator for applying rate limits to specific endpoints
def rate_limit(requests_per_minute: int = 60, requests_per_hour: int = 1000):
    """
    Decorator to apply rate limiting to specific endpoints
    
    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be implemented to work with FastAPI dependencies
            # For now, this is a placeholder for endpoint-specific rate limiting
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Helper functions for different rate limiting strategies
async def check_api_key_rate_limit(api_key: str, endpoint: str) -> bool:
    """Check rate limit for specific API key and endpoint"""
    
    # This would lookup API key specific limits from database
    # For now, using default limits
    key = f"api_key:{api_key}:endpoint:{endpoint}"
    
    is_allowed, _ = await rate_limiter.check_rate_limit(
        key, limit=100, window_seconds=60, identifier="endpoint"
    )
    
    return is_allowed


async def check_user_rate_limit(user_id: str, action: str) -> bool:
    """Check rate limit for specific user and action"""
    
    key = f"user:{user_id}:action:{action}"
    
    is_allowed, _ = await rate_limiter.check_rate_limit(
        key, limit=50, window_seconds=60, identifier="user_action"
    )
    
    return is_allowed


async def apply_burst_protection(key: str) -> bool:
    """Apply burst protection for high-frequency actions"""
    
    # Allow burst of 10 requests in 10 seconds
    is_allowed, _ = await rate_limiter.check_rate_limit(
        key, limit=10, window_seconds=10, identifier="burst"
    )
    
    return is_allowed