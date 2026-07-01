"""
Rate Limiting Middleware

Security mitigation for:
- #2: Rate limiting disabled
- #46: No rate limiting on refresh endpoint
- #49: Missing rate limit response headers

Provides per-IP, per-user, and per-API-key rate limiting with proper headers.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.cache import core_cache
from app.core.config import settings
from app.core.security import verify_token
from app.utils.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Configuration for rate limiting by endpoint pattern"""

    # Strict limits for sensitive endpoints (configurable via settings)
    @property
    def STRICT_ENDPOINTS(self):
        return {
            "/api-internal/v1/auth/refresh": {
                "per_minute": settings.API_RATE_LIMIT_REFRESH_PER_MINUTE,
                "per_hour": settings.API_RATE_LIMIT_REFRESH_PER_HOUR,
            },
            "/api-internal/v1/auth/login": {
                "per_minute": settings.API_RATE_LIMIT_LOGIN_PER_MINUTE,
                "per_hour": settings.API_RATE_LIMIT_LOGIN_PER_HOUR,
            },
            "/api-internal/v1/auth/register": {
                "per_minute": settings.API_RATE_LIMIT_REGISTER_PER_MINUTE,
                "per_hour": settings.API_RATE_LIMIT_REGISTER_PER_HOUR,
            },
            "/api/v1/auth/refresh": {
                "per_minute": settings.API_RATE_LIMIT_REFRESH_PER_MINUTE,
                "per_hour": settings.API_RATE_LIMIT_REFRESH_PER_HOUR,
            },
            "/api/v1/auth/login": {
                "per_minute": settings.API_RATE_LIMIT_LOGIN_PER_MINUTE,
                "per_hour": settings.API_RATE_LIMIT_LOGIN_PER_HOUR,
            },
        }

    # Default limits
    DEFAULT_AUTHENTICATED_PER_MINUTE = settings.API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE
    DEFAULT_AUTHENTICATED_PER_HOUR = settings.API_RATE_LIMIT_AUTHENTICATED_PER_HOUR
    DEFAULT_API_KEY_PER_MINUTE = settings.API_RATE_LIMIT_API_KEY_PER_MINUTE
    DEFAULT_API_KEY_PER_HOUR = settings.API_RATE_LIMIT_API_KEY_PER_HOUR

    # Unauthenticated/anonymous limits (configurable via settings)
    ANONYMOUS_PER_MINUTE = settings.API_RATE_LIMIT_ANONYMOUS_PER_MINUTE
    ANONYMOUS_PER_HOUR = settings.API_RATE_LIMIT_ANONYMOUS_PER_HOUR


class RateLimiter:
    """Rate limiter using Redis for distributed rate limiting"""

    def __init__(self):
        self.config = RateLimitConfig()

    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        is_authenticated: bool = False,
        is_api_key: bool = False,
    ) -> Dict[str, Any]:
        """
        Check rate limit for a request.

        Returns dict with:
        - allowed: bool
        - limit: int
        - remaining: int
        - reset: int (timestamp)
        - retry_after: int (seconds, only if not allowed)
        """
        # Determine limits based on endpoint and auth status
        limits = self._get_limits(endpoint, is_authenticated, is_api_key)

        # Check per-minute limit first (more granular)
        minute_key = f"ratelimit:{identifier}:minute:{int(time.time() // 60)}"
        minute_result = await self._check_window(minute_key, limits["per_minute"], 60)

        if not minute_result["allowed"]:
            return minute_result

        # Check per-hour limit
        hour_key = f"ratelimit:{identifier}:hour:{int(time.time() // 3600)}"
        hour_result = await self._check_window(hour_key, limits["per_hour"], 3600)

        if not hour_result["allowed"]:
            return hour_result

        # Return the more restrictive remaining count
        if minute_result["remaining"] < hour_result["remaining"]:
            return minute_result
        return hour_result

    def _get_limits(
        self, endpoint: str, is_authenticated: bool, is_api_key: bool
    ) -> Dict[str, int]:
        """Get rate limits for the given context"""
        # Check for strict endpoint limits first
        for pattern, limits in self.config.STRICT_ENDPOINTS.items():
            if endpoint.startswith(pattern) or endpoint == pattern:
                return limits

        # Use appropriate default limits
        if is_api_key:
            return {
                "per_minute": self.config.DEFAULT_API_KEY_PER_MINUTE,
                "per_hour": self.config.DEFAULT_API_KEY_PER_HOUR,
            }
        elif is_authenticated:
            return {
                "per_minute": self.config.DEFAULT_AUTHENTICATED_PER_MINUTE,
                "per_hour": self.config.DEFAULT_AUTHENTICATED_PER_HOUR,
            }
        else:
            return {
                "per_minute": self.config.ANONYMOUS_PER_MINUTE,
                "per_hour": self.config.ANONYMOUS_PER_HOUR,
            }

    async def _check_window(
        self, key: str, limit: int, window_seconds: int
    ) -> Dict[str, Any]:
        """Check rate limit for a specific time window"""
        try:
            if not core_cache.enabled:
                # Fallback: allow request if cache is unavailable
                # (fail open for availability, but log warning)
                logger.warning("Rate limiting disabled: cache unavailable")
                return {
                    "allowed": True,
                    "limit": limit,
                    "remaining": limit,
                    "reset": int(time.time()) + window_seconds,
                }

            result = await core_cache.cache_rate_limit(key, window_seconds, limit, 1)

            return {
                "allowed": not result["exceeded"],
                "limit": limit,
                "remaining": result["remaining"],
                "reset": result["reset_time"],
                "retry_after": window_seconds if result["exceeded"] else 0,
            }

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open to avoid blocking legitimate requests
            return {
                "allowed": True,
                "limit": limit,
                "remaining": limit,
                "reset": int(time.time()) + window_seconds,
            }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting requests.

    Rate limiting strategy:
    - JWT-authenticated users (dashboard): NO rate limits (unlimited usage)
    - API key users: Rate limited per key
    - Anonymous/unauthenticated: Rate limited per IP
    - Auth endpoints (login/register/refresh): Always rate limited (brute-force protection)

    Can be disabled globally via RATE_LIMIT_ENABLED=false in .env
    """

    # Endpoints exempt from rate limiting
    EXEMPT_ENDPOINTS = {
        "/health",
        "/",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/openapi.json",
    }

    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.limiter = RateLimiter()
        self.exclude_paths = exclude_paths or []

    # Auth endpoints that need rate limiting even for pre-auth requests
    AUTH_ENDPOINTS = {
        "/api-internal/v1/auth/login",
        "/api-internal/v1/auth/register",
        "/api-internal/v1/auth/refresh",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting"""
        # Check if rate limiting is disabled globally
        if (
            not settings.RATE_LIMIT_ENABLED
            or settings.TESTING
            or settings.LLM_TEST_MODE
        ):
            return await call_next(request)

        path = request.url.path

        # Skip rate limiting for exempt endpoints
        if self._is_exempt(path):
            return await call_next(request)

        # Get identifier for rate limiting
        identifier, is_jwt_user, is_api_key = self._get_identifier(request)

        # JWT-authenticated users (dashboard) have NO rate limits
        # except for auth endpoints (login/register/refresh)
        is_auth_endpoint = any(path.startswith(ep) for ep in self.AUTH_ENDPOINTS)
        if is_jwt_user and not is_api_key and not is_auth_endpoint:
            return await call_next(request)

        # Rate limit: API key users, anonymous users, and auth endpoints
        result = await self.limiter.check_rate_limit(
            identifier, path, is_jwt_user, is_api_key
        )

        if not result["allowed"]:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {identifier} on {path}",
                extra={
                    "identifier": identifier,
                    "path": path,
                    "limit": result["limit"],
                },
            )
            return self._rate_limit_response(result)

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response (#49)
        self._add_rate_limit_headers(response, result)

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting"""
        if path in self.EXEMPT_ENDPOINTS:
            return True
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return True
        return False

    def _get_identifier(self, request: Request) -> tuple:
        """
        Get rate limit identifier from request.

        Returns: (identifier, is_authenticated, is_api_key)
        """
        # Check for API key first
        api_key = request.headers.get("X-API-Key")
        if api_key and len(api_key) >= 8:
            # Use API key prefix as identifier
            return f"apikey:{api_key[:8]}", True, True

        # Check for Bearer token (could be API key or JWT)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token.startswith("eyJ"):
                # JWT token - MUST validate signature before exempting from rate limits
                # SECURITY FIX: Previously this just decoded without verification,
                # allowing fake JWT-like tokens to bypass rate limiting
                try:
                    payload = verify_token(token)
                    user_id = payload.get("sub")
                    if user_id:
                        return f"user:{user_id}", True, False
                except (AuthenticationError, Exception):
                    # Invalid JWT - fall through to IP-based rate limiting
                    # Do NOT treat as API key (they might be testing for bypass)
                    logger.debug(
                        "Invalid JWT token in Authorization header, using IP-based rate limiting"
                    )
                    pass
            elif len(token) >= 8:
                # API key in Bearer header
                return f"apikey:{token[:8]}", True, True

        # Fall back to IP-based rate limiting
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}", False, False

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, considering proxies"""
        # Check X-Forwarded-For header (common with proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get first IP in the chain (client IP)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _rate_limit_response(self, result: Dict[str, Any]) -> JSONResponse:
        """Create 429 Too Many Requests response"""
        headers = {
            "X-RateLimit-Limit": str(result["limit"]),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(result["reset"]),
            "Retry-After": str(result.get("retry_after", 60)),
        }

        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down.",
                "retry_after": result.get("retry_after", 60),
            },
            headers=headers,
        )

    def _add_rate_limit_headers(
        self, response: Response, result: Dict[str, Any]
    ) -> None:
        """Add X-RateLimit-* headers to response"""
        response.headers["X-RateLimit-Limit"] = str(result["limit"])
        response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
        response.headers["X-RateLimit-Reset"] = str(result["reset"])


def setup_rate_limiting(app) -> None:
    """Setup rate limiting middleware on the FastAPI app"""
    if not settings.RATE_LIMIT_ENABLED:
        logger.warning(
            "Rate limiting is DISABLED (RATE_LIMIT_ENABLED=false). "
            "This should only be used for development/testing."
        )
    app.add_middleware(
        RateLimitMiddleware,
        exclude_paths=["/health", "/api/v1/docs", "/api/v1/redoc"],
    )
    logger.info(
        f"Rate limiting middleware {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}"
    )


async def rate_limit_middleware(request, call_next):
    """Backward-compatible patch target for legacy tests."""
    return await call_next(request)
