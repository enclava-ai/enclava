"""
Debugging middleware for detailed request/response logging
"""
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


class DebuggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log detailed request/response information for debugging"""

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID for tracing
        request_id = str(uuid4())

        # Skip debugging for health checks and static files
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"] or \
           request.url.path.startswith("/static"):
            return await call_next(request)

        # Log request details
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Clone request body to avoid consuming it
                body_bytes = await request.body()
                if body_bytes:
                    try:
                        request_body = json.loads(body_bytes)
                    except json.JSONDecodeError:
                        request_body = body_bytes.decode('utf-8', errors='replace')
                    # Restore body for downstream processing
                    request._body = body_bytes
            except Exception:
                request_body = "[Failed to read request body]"

        # Extract headers we care about
        headers_to_log = {
            "authorization": request.headers.get("Authorization", "")[:50] + "..." if
                          request.headers.get("Authorization") else None,
            "content-type": request.headers.get("Content-Type"),
            "user-agent": request.headers.get("User-Agent"),
            "x-forwarded-for": request.headers.get("X-Forwarded-For"),
            "x-real-ip": request.headers.get("X-Real-IP"),
        }

        # Log request
        logger.info("=== API REQUEST DEBUG ===", extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": {k: v for k, v in headers_to_log.items() if v is not None},
            "body": request_body,
            "client_ip": request.client.host if request.client else None,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Process the request
        start_time = time.time()
        response = None
        response_body = None

        # Add timeout detection
        try:
            logger.info(f"=== START PROCESSING REQUEST === {request_id} at {datetime.utcnow().isoformat()}")
            logger.info(f"Request path: {request.url.path}")
            logger.info(f"Request method: {request.method}")
            
            # Check if this is the login endpoint
            if request.url.path == "/api-internal/v1/auth/login" and request.method == "POST":
                logger.info(f"=== LOGIN REQUEST DETECTED === {request_id}")
                
            response = await call_next(request)
            logger.info(f"=== REQUEST COMPLETED === {request_id} at {datetime.utcnow().isoformat()}")

            # Capture response body for successful JSON responses
            if response.status_code < 400 and isinstance(response, JSONResponse):
                try:
                    response_body = json.loads(response.body.decode('utf-8'))
                except:
                    response_body = "[Failed to decode response body]"

        except Exception as e:
            logger.error(f"Request processing failed: {str(e)}", extra={
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            response = JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_ERROR", "message": "Internal server error"}
            )

        # Calculate timing
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # milliseconds

        # Log response
        logger.info("=== API RESPONSE DEBUG ===", extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": round(duration, 2),
            "response_body": response_body,
            "response_headers": dict(response.headers),
            "timestamp": datetime.utcnow().isoformat()
        })

        return response


def setup_debugging_middleware(app):
    """Add debugging middleware to the FastAPI app"""
    app.add_middleware(DebuggingMiddleware)
    logger.info("Debugging middleware configured")