"""
Base module interface and interceptor pattern implementation
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from fastapi import Request, Response
import json
import re
import copy
import time
import hashlib
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.utils.exceptions import ValidationError, AuthenticationError, RateLimitExceeded
from app.services.permission_manager import permission_registry

logger = get_logger(__name__)


@dataclass
class Permission:
    """Represents a module permission"""

    resource: str
    action: str
    description: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"


@dataclass
class ModuleMetrics:
    """Module performance metrics"""

    requests_processed: int = 0
    average_response_time: float = 0.0
    error_rate: float = 0.0
    last_activity: Optional[str] = None
    total_errors: int = 0
    uptime_start: float = 0.0

    def __post_init__(self):
        if self.uptime_start == 0.0:
            self.uptime_start = time.time()


@dataclass
class ModuleHealth:
    """Module health status"""

    status: str = "healthy"  # healthy, warning, error
    message: str = "Module is functioning normally"
    uptime: float = 0.0
    last_check: float = 0.0

    def __post_init__(self):
        if self.last_check == 0.0:
            self.last_check = time.time()


class BaseModule(ABC):
    """Base class for all modules with interceptor pattern support"""

    def __init__(self, module_id: str, config: Dict[str, Any] = None):
        self.module_id = module_id
        self.config = config or {}
        self.metrics = ModuleMetrics()
        self.health = ModuleHealth()
        self.initialized = False
        self.interceptors: List["ModuleInterceptor"] = []

        # Register default interceptors
        self._register_default_interceptors()

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the module"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup module resources"""
        pass

    @abstractmethod
    def get_required_permissions(self) -> List[Permission]:
        """Return list of permissions this module requires"""
        return []

    @abstractmethod
    async def process_request(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a module request"""
        pass

    def get_health(self) -> ModuleHealth:
        """Get current module health status"""
        self.health.uptime = time.time() - self.metrics.uptime_start
        self.health.last_check = time.time()
        return self.health

    def get_metrics(self) -> ModuleMetrics:
        """Get current module metrics"""
        return self.metrics

    def check_access(self, user_permissions: List[str], action: str) -> bool:
        """Check if user can perform action on this module"""
        required = f"modules:{self.module_id}:{action}"
        return permission_registry.check_permission(user_permissions, required)

    def _register_default_interceptors(self):
        """Register default interceptors for all modules"""
        self.interceptors = [
            AuthenticationInterceptor(),
            PermissionInterceptor(self),
            ValidationInterceptor(),
            MetricsInterceptor(self),
            SecurityInterceptor(),
            AuditInterceptor(self),
        ]

    async def execute_with_interceptors(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute request through interceptor chain"""
        start_time = time.time()

        try:
            # Pre-processing interceptors
            for interceptor in self.interceptors:
                request, context = await interceptor.pre_process(request, context)

            # Execute main module logic
            response = await self.process_request(request, context)

            # Post-processing interceptors (in reverse order)
            for interceptor in reversed(self.interceptors):
                response = await interceptor.post_process(request, context, response)

            # Update metrics
            self._update_metrics(start_time, success=True)

            return response

        except Exception as e:
            # Update error metrics
            self._update_metrics(start_time, success=False, error=str(e))

            # Error handling interceptors
            for interceptor in reversed(self.interceptors):
                if hasattr(interceptor, "handle_error"):
                    await interceptor.handle_error(request, context, e)

            raise

    def _update_metrics(self, start_time: float, success: bool, error: str = None):
        """Update module metrics"""
        duration = time.time() - start_time

        self.metrics.requests_processed += 1

        # Update average response time
        if self.metrics.requests_processed == 1:
            self.metrics.average_response_time = duration
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_response_time = (
                alpha * duration + (1 - alpha) * self.metrics.average_response_time
            )

        if not success:
            self.metrics.total_errors += 1
            self.metrics.error_rate = (
                self.metrics.total_errors / self.metrics.requests_processed
            )

            # Update health status based on error rate
            if self.metrics.error_rate > 0.1:  # More than 10% error rate
                self.health.status = "error"
                self.health.message = f"High error rate: {self.metrics.error_rate:.2%}"
            elif self.metrics.error_rate > 0.05:  # More than 5% error rate
                self.health.status = "warning"
                self.health.message = (
                    f"Elevated error rate: {self.metrics.error_rate:.2%}"
                )
        else:
            self.metrics.error_rate = (
                self.metrics.total_errors / self.metrics.requests_processed
            )
            if self.metrics.error_rate <= 0.05:
                self.health.status = "healthy"
                self.health.message = "Module is functioning normally"

        self.metrics.last_activity = time.strftime("%Y-%m-%d %H:%M:%S")


class ModuleInterceptor(ABC):
    """Base class for module interceptors"""

    @abstractmethod
    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Pre-process the request"""
        return request, context

    @abstractmethod
    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post-process the response"""
        return response


class AuthenticationInterceptor(ModuleInterceptor):
    """Handles authentication for module requests"""

    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Check if user is authenticated (context should contain user info from API auth)
        if not context.get("user_id") and not context.get("api_key_id"):
            raise AuthenticationError("Authentication required for module access")

        return request, context

    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        return response


class PermissionInterceptor(ModuleInterceptor):
    """Handles permission checking for module requests"""

    def __init__(self, module: BaseModule):
        self.module = module

    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        action = request.get("action", "execute")
        user_permissions = context.get("user_permissions", [])

        if not self.module.check_access(user_permissions, action):
            raise AuthenticationError(
                f"Insufficient permissions for module action: {action}"
            )

        return request, context

    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        return response


class ValidationInterceptor(ModuleInterceptor):
    """Handles request validation and sanitization"""

    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Sanitize request data
        sanitized_request = self._sanitize_request(request)

        # Validate request structure
        self._validate_request(sanitized_request)

        return sanitized_request, context

    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Sanitize response data
        return self._sanitize_response(response)

    def _sanitize_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Remove potentially dangerous content from request"""
        sanitized = copy.deepcopy(request)

        # Define dangerous patterns
        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"data:text/html",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"eval\s*\(",
            r"Function\s*\(",
        ]

        def sanitize_value(value):
            if isinstance(value, str):
                # Remove dangerous patterns
                for pattern in dangerous_patterns:
                    value = re.sub(pattern, "", value, flags=re.IGNORECASE)

                # Limit string length
                max_length = 10000
                if len(value) > max_length:
                    value = value[:max_length]
                    logger.warning(
                        f"Truncated long string in request: {len(value)} chars"
                    )

                return value
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value

        return sanitize_value(sanitized)

    def _sanitize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize response data"""
        # Similar sanitization for responses
        return self._sanitize_request(response)

    def _validate_request(self, request: Dict[str, Any]):
        """Validate request structure"""
        # Check for required fields
        if not isinstance(request, dict):
            raise ValidationError("Request must be a dictionary")

        # Check request size
        request_str = json.dumps(request)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(request_str.encode()) > max_size:
            raise ValidationError(
                f"Request size exceeds maximum allowed ({max_size} bytes)"
            )


class MetricsInterceptor(ModuleInterceptor):
    """Handles metrics collection for module requests"""

    def __init__(self, module: BaseModule):
        self.module = module

    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        context["_metrics_start_time"] = time.time()
        return request, context

    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Metrics are updated in the base module execute_with_interceptors method
        return response


class SecurityInterceptor(ModuleInterceptor):
    """Handles security-related processing"""

    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Add security headers to context
        context["security_headers"] = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        }

        # Check for suspicious patterns
        self._check_security_patterns(request)

        return request, context

    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Remove any sensitive information from response
        return self._remove_sensitive_data(response)

    def _check_security_patterns(self, request: Dict[str, Any]):
        """Check for suspicious security patterns"""
        request_str = json.dumps(request).lower()

        suspicious_patterns = [
            "union select",
            "drop table",
            "insert into",
            "delete from",
            "script>",
            "javascript:",
            "eval(",
            "expression(",
            "../",
            "..\\",
            "file://",
            "ftp://",
        ]

        for pattern in suspicious_patterns:
            if pattern in request_str:
                logger.warning(f"Suspicious pattern detected in request: {pattern}")
                # Could implement additional security measures here

    def _remove_sensitive_data(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from response"""
        sensitive_keys = ["password", "secret", "token", "key", "private"]

        def clean_dict(obj):
            if isinstance(obj, dict):
                return {
                    k: "***REDACTED***"
                    if any(sk in k.lower() for sk in sensitive_keys)
                    else clean_dict(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [clean_dict(item) for item in obj]
            else:
                return obj

        return clean_dict(response)


class AuditInterceptor(ModuleInterceptor):
    """Handles audit logging for module requests"""

    def __init__(self, module: BaseModule):
        self.module = module

    async def pre_process(
        self, request: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        context["_audit_start_time"] = time.time()
        context["_audit_request_hash"] = self._hash_request(request)
        return request, context

    async def post_process(
        self, request: Dict[str, Any], context: Dict[str, Any], response: Dict[str, Any]
    ) -> Dict[str, Any]:
        await self._log_audit_event(request, context, response, success=True)
        return response

    async def handle_error(
        self, request: Dict[str, Any], context: Dict[str, Any], error: Exception
    ):
        """Handle error logging"""
        await self._log_audit_event(
            request, context, {"error": str(error)}, success=False
        )

    def _hash_request(self, request: Dict[str, Any]) -> str:
        """Create a hash of the request for audit purposes"""
        request_str = json.dumps(request, sort_keys=True)
        return hashlib.sha256(request_str.encode()).hexdigest()[:16]

    async def _log_audit_event(
        self,
        request: Dict[str, Any],
        context: Dict[str, Any],
        response: Dict[str, Any],
        success: bool,
    ):
        """Log audit event"""
        duration = time.time() - context.get("_audit_start_time", time.time())

        audit_data = {
            "module_id": self.module.module_id,
            "action": request.get("action", "execute"),
            "user_id": context.get("user_id"),
            "api_key_id": context.get("api_key_id"),
            "ip_address": context.get("ip_address"),
            "request_hash": context.get("_audit_request_hash"),
            "success": success,
            "duration_ms": int(duration * 1000),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if not success:
            audit_data["error"] = response.get("error", "Unknown error")

        # Log the audit event
        logger.info(f"Module audit: {json.dumps(audit_data)}")

        # Could also store in database for persistent audit trail
