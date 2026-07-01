"""
Analytics middleware for automatic request tracking
"""

import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.services.analytics import RequestEvent, get_analytics_service

logger = get_logger(__name__)

# Context variable to pass analytics data from endpoints to middleware
analytics_context: ContextVar[dict] = ContextVar("analytics_context", default={})


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically track all requests for analytics"""

    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()

        if settings.TESTING or settings.LLM_TEST_MODE:
            return await call_next(request)

        # Skip analytics for health checks and static files
        if request.url.path in [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ] or request.url.path.startswith("/static"):
            return await call_next(request)

        # Get user info if available from token
        user_id = None
        api_key_id = None

        try:
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                token = authorization.split(" ")[1]
                if not token.startswith("eyJ"):
                    raise ValueError("Bearer token is not a JWT")
                # Try to extract user info from token without full validation
                # This is a lightweight check for analytics purposes
                from app.core.security import verify_token

                try:
                    payload = verify_token(token)
                    user_id = int(payload.get("sub"))
                except:
                    # Token might be invalid, but we still want to track the request
                    pass
        except Exception:
            # Don't let analytics break the request
            pass

        # Get client IP
        client_ip = request.client.host if request.client else None
        if not client_ip:
            # Check for forwarded headers
            client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.headers.get("X-Real-IP", "unknown")

        # Get user agent
        user_agent = request.headers.get("User-Agent", "")

        # Get request size
        request_size = int(request.headers.get("Content-Length", 0))

        # Process the request
        response = None
        error_message = None

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            error_message = str(e)
            response = JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_ERROR", "message": "Internal server error"},
            )

        # Calculate timing
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Get response size
        response_size = 0
        if hasattr(response, "body"):
            response_size = len(response.body) if response.body else 0

        # Get analytics data from context (set by endpoints)
        context_data = analytics_context.get({})

        # ISSUE #4 FIX: Extract API key info from request state (set by auth dependency)
        # This must be done AFTER call_next() since authentication runs during the request
        try:
            api_key = getattr(request.state, "api_key", None)
            if api_key:
                api_key_id = api_key.id
                # Also get user_id from API key if not set from JWT
                if user_id is None:
                    user_id = api_key.user_id

            # Also try auth_context if using dependency injection
            if api_key_id is None:
                auth_context = getattr(request.state, "auth_context", None)
                if auth_context:
                    api_key_id = auth_context.get("api_key_id")
                    if user_id is None:
                        user_id = auth_context.get("user_id")

            # Also check context_data from set_analytics_data calls
            if api_key_id is None:
                api_key_id = context_data.get("api_key_id")
            if user_id is None:
                user_id = context_data.get("user_id")
        except Exception as e:
            logger.debug(f"Could not extract API key info from request state: {e}")

        # Create analytics event
        event = RequestEvent(
            timestamp=datetime.now(timezone.utc),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code if response else 500,
            response_time=response_time,
            user_id=user_id,
            api_key_id=api_key_id,
            ip_address=client_ip,
            user_agent=user_agent,
            request_size=request_size,
            response_size=response_size,
            error_message=error_message,
            # Token/cost info populated by LLM endpoints via context
            model=context_data.get("model"),
            request_tokens=context_data.get("request_tokens", 0),
            response_tokens=context_data.get("response_tokens", 0),
            total_tokens=context_data.get("total_tokens", 0),
            cost_cents=context_data.get("cost_cents", 0),
            budget_ids=context_data.get("budget_ids", []),
            budget_warnings=context_data.get("budget_warnings", []),
        )

        # Track the event
        try:
            from app.services.analytics import analytics_service

            if analytics_service is not None:
                await analytics_service.track_request(event)
            else:
                logger.warning(
                    "Analytics service not initialized, skipping event tracking"
                )
        except Exception as e:
            logger.error(f"Failed to track analytics event: {e}")
            # Don't let analytics failures break the request

        return response


def set_analytics_data(**kwargs):
    """Helper function for endpoints to set analytics data"""
    current_context = analytics_context.get({})
    current_context.update(kwargs)
    analytics_context.set(current_context)


def setup_analytics_middleware(app):
    """Add analytics middleware to the FastAPI app"""
    app.add_middleware(AnalyticsMiddleware)
    logger.info("Analytics middleware configured")
