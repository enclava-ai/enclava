"""
Audit Logging Middleware
Automatically logs user actions and system events
"""
import time
import json
import logging
from typing import Callable, Optional, Dict, Any
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction, AuditSeverity
from app.db.database import get_db_session
from app.core.security import verify_token

logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log user actions and API calls"""

    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        # Paths to exclude from audit logging
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
            "/static",
            "/favicon.ico",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip audit logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Skip audit logging for health checks and static assets
        if request.url.path in ["/", "/health"] or "/static/" in request.url.path:
            return await call_next(request)

        start_time = time.time()

        # Extract user information from request
        user_info = await self._extract_user_info(request)

        # Prepare audit data
        audit_data = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "ip_address": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Process request
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time
        audit_data["response_time"] = round(process_time * 1000, 2)  # milliseconds
        audit_data["status_code"] = response.status_code
        audit_data["success"] = 200 <= response.status_code < 400

        # Log the audit event asynchronously
        try:
            await self._log_audit_event(user_info, audit_data, request)
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            # Don't fail the request if audit logging fails

        return response

    async def _extract_user_info(self, request: Request) -> Optional[Dict[str, Any]]:
        """Extract user information from request headers"""
        try:
            # Try to get user info from Authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                payload = verify_token(token)
                return {
                    "user_id": int(payload.get("sub")) if payload.get("sub") else None,
                    "email": payload.get("email"),
                    "is_superuser": payload.get("is_superuser", False),
                    "role": payload.get("role"),
                }
        except Exception:
            # If token verification fails, continue without user info
            pass

        # Try to get user info from API key header
        api_key = request.headers.get("x-api-key")
        if api_key:
            # Would need to implement API key lookup here
            # For now, just indicate it's an API key request
            return {
                "user_id": None,
                "email": "api_key_user",
                "is_superuser": False,
                "role": "api_user",
                "auth_type": "api_key",
            }

        return None

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support"""
        # Check for forwarded headers first (for reverse proxy setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        forwarded = request.headers.get("x-forwarded")
        if forwarded:
            return forwarded

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    async def _log_audit_event(
        self,
        user_info: Optional[Dict[str, Any]],
        audit_data: Dict[str, Any],
        request: Request
    ):
        """Log the audit event to database"""

        # Determine action based on HTTP method and path
        action = self._determine_action(request.method, request.url.path)

        # Determine resource type and ID from path
        resource_type, resource_id = self._parse_resource_from_path(request.url.path)

        # Create description
        description = self._create_description(request.method, request.url.path, audit_data["success"])

        # Determine severity
        severity = self._determine_severity(request.method, audit_data["status_code"], request.url.path)

        # Create audit log entry
        try:
            async with get_db_session() as db:
                audit_log = AuditLog(
                    user_id=user_info.get("user_id") if user_info else None,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=description,
                    details={
                        "request": {
                            "method": audit_data["method"],
                            "path": audit_data["path"],
                            "query_params": audit_data["query_params"],
                            "response_time_ms": audit_data["response_time"],
                        },
                        "user_info": user_info,
                    },
                    ip_address=audit_data["ip_address"],
                    user_agent=audit_data["user_agent"],
                    severity=severity,
                    category=self._determine_category(request.url.path),
                    success=audit_data["success"],
                    tags=self._generate_tags(request.method, request.url.path),
                )

                db.add(audit_log)
                await db.commit()

        except Exception as e:
            logger.error(f"Failed to save audit log to database: {e}")
            # Could implement fallback logging to file here

    def _determine_action(self, method: str, path: str) -> str:
        """Determine action type from HTTP method and path"""
        method = method.upper()

        if method == "GET":
            return AuditAction.READ
        elif method == "POST":
            if "login" in path.lower():
                return AuditAction.LOGIN
            elif "logout" in path.lower():
                return AuditAction.LOGOUT
            else:
                return AuditAction.CREATE
        elif method == "PUT" or method == "PATCH":
            return AuditAction.UPDATE
        elif method == "DELETE":
            return AuditAction.DELETE
        else:
            return method.lower()

    def _parse_resource_from_path(self, path: str) -> tuple[str, Optional[str]]:
        """Parse resource type and ID from URL path"""
        path_parts = path.strip("/").split("/")

        # Skip API version prefix
        if path_parts and path_parts[0] in ["api", "api-internal"]:
            path_parts = path_parts[2:]  # Skip 'api' and 'v1'

        if not path_parts:
            return "system", None

        resource_type = path_parts[0]
        resource_id = None

        # Try to find numeric ID in path
        for part in path_parts[1:]:
            if part.isdigit():
                resource_id = part
                break

        return resource_type, resource_id

    def _create_description(self, method: str, path: str, success: bool) -> str:
        """Create human-readable description of the action"""
        action_verbs = {
            "GET": "accessed" if success else "attempted to access",
            "POST": "created" if success else "attempted to create",
            "PUT": "updated" if success else "attempted to update",
            "PATCH": "modified" if success else "attempted to modify",
            "DELETE": "deleted" if success else "attempted to delete",
        }

        verb = action_verbs.get(method, method.lower())
        resource = path.strip("/").split("/")[-1] if "/" in path else path

        return f"User {verb} {resource}"

    def _determine_severity(self, method: str, status_code: int, path: str) -> str:
        """Determine severity level based on action and outcome"""

        # Critical operations
        if any(keyword in path.lower() for keyword in ["delete", "password", "admin", "key"]):
            return AuditSeverity.HIGH

        # Failed operations
        if status_code >= 400:
            if status_code >= 500:
                return AuditSeverity.CRITICAL
            elif status_code in [401, 403]:
                return AuditSeverity.HIGH
            else:
                return AuditSeverity.MEDIUM

        # Write operations
        if method in ["POST", "PUT", "PATCH", "DELETE"]:
            return AuditSeverity.MEDIUM

        # Read operations
        return AuditSeverity.LOW

    def _determine_category(self, path: str) -> str:
        """Determine category based on path"""
        path = path.lower()

        if any(keyword in path for keyword in ["auth", "login", "logout", "token"]):
            return "authentication"
        elif any(keyword in path for keyword in ["user", "admin", "role", "permission"]):
            return "user_management"
        elif any(keyword in path for keyword in ["api-key", "key"]):
            return "security"
        elif any(keyword in path for keyword in ["budget", "billing", "usage"]):
            return "financial"
        elif any(keyword in path for keyword in ["audit", "log"]):
            return "audit"
        elif any(keyword in path for keyword in ["setting", "config"]):
            return "configuration"
        else:
            return "general"

    def _generate_tags(self, method: str, path: str) -> list[str]:
        """Generate tags for the audit log"""
        tags = [method.lower()]

        path_parts = path.strip("/").split("/")
        if path_parts:
            tags.append(path_parts[0])

        # Add special tags
        if "admin" in path.lower():
            tags.append("admin_action")
        if any(keyword in path.lower() for keyword in ["password", "auth", "login"]):
            tags.append("security_action")

        return tags


class LoginAuditMiddleware(BaseHTTPMiddleware):
    """Specialized middleware for login/logout events"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only process auth-related endpoints
        if not any(path in request.url.path for path in ["/auth/login", "/auth/logout", "/auth/refresh"]):
            return await call_next(request)

        start_time = time.time()

        # Store request body for login attempts
        request_body = None
        if request.method == "POST" and "/login" in request.url.path:
            try:
                body = await request.body()
                if body:
                    request_body = json.loads(body.decode())
                    # Re-create request with body for downstream processing
                    from starlette.requests import Request as StarletteRequest
                    from io import BytesIO
                    request._body = body
            except Exception as e:
                logger.warning(f"Failed to parse login request body: {e}")

        response = await call_next(request)

        # Log login/logout events
        try:
            await self._log_auth_event(request, response, request_body, time.time() - start_time)
        except Exception as e:
            logger.error(f"Failed to log auth event: {e}")

        return response

    async def _log_auth_event(self, request: Request, response: Response, request_body: dict, process_time: float):
        """Log authentication events"""

        success = 200 <= response.status_code < 300

        if "/login" in request.url.path:
            # Extract email/username from request
            identifier = None
            if request_body:
                identifier = request_body.get("email") or request_body.get("username")

            # For successful logins, we could extract user_id from response
            # For now, we'll use the identifier

            async with get_db_session() as db:
                audit_log = AuditLog.create_login_event(
                    user_id=None,  # Would need to extract from response for successful logins
                    success=success,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    error_message=f"HTTP {response.status_code}" if not success else None,
                )

                # Add additional details
                audit_log.details.update({
                    "identifier": identifier,
                    "response_time_ms": round(process_time * 1000, 2),
                })

                db.add(audit_log)
                await db.commit()

        elif "/logout" in request.url.path:
            # Extract user info from token if available
            user_id = None
            try:
                auth_header = request.headers.get("authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
                    payload = verify_token(token)
                    user_id = int(payload.get("sub")) if payload.get("sub") else None
            except Exception:
                pass

            async with get_db_session() as db:
                audit_log = AuditLog.create_logout_event(
                    user_id=user_id,
                    session_id=None,  # Could extract from token if stored
                )

                db.add(audit_log)
                await db.commit()

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"