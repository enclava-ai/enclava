"""
Custom exceptions
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class CustomHTTPException(HTTPException):
    """Base custom HTTP exception"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        detail: str,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code
        self.details = details or {}


class AuthenticationError(CustomHTTPException):
    """Authentication error"""
    
    def __init__(self, detail: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_ERROR",
            detail=detail,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(CustomHTTPException):
    """Authorization error"""
    
    def __init__(self, detail: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="AUTHORIZATION_ERROR",
            detail=detail,
            details=details,
        )


class ValidationError(CustomHTTPException):
    """Validation error"""
    
    def __init__(self, detail: str = "Invalid data", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            detail=detail,
            details=details,
        )


class NotFoundError(CustomHTTPException):
    """Not found error"""
    
    def __init__(self, detail: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            detail=detail,
            details=details,
        )


class ConflictError(CustomHTTPException):
    """Conflict error"""
    
    def __init__(self, detail: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
            detail=detail,
            details=details,
        )


class RateLimitError(CustomHTTPException):
    """Rate limit error"""
    
    def __init__(self, detail: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            detail=detail,
            details=details,
        )


class BudgetExceededError(CustomHTTPException):
    """Budget exceeded error"""
    
    def __init__(self, detail: str = "Budget exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            error_code="BUDGET_EXCEEDED",
            detail=detail,
            details=details,
        )


class ModuleError(CustomHTTPException):
    """Module error"""
    
    def __init__(self, detail: str = "Module error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MODULE_ERROR",
            detail=detail,
            details=details,
        )


class CircuitBreakerOpen(Exception):
    """Circuit breaker is open"""
    pass


class ModuleLoadError(Exception):
    """Module load error"""
    pass


class ModuleNotFoundError(Exception):
    """Module not found error"""
    pass


class ModuleFatalError(Exception):
    """Fatal module error"""
    pass


class ConfigurationError(Exception):
    """Configuration error"""
    pass


class PluginError(CustomHTTPException):
    """Plugin error"""
    
    def __init__(self, detail: str = "Plugin error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PLUGIN_ERROR",
            detail=detail,
            details=details,
        )


class SecurityError(CustomHTTPException):
    """Security error"""
    
    def __init__(self, detail: str = "Security violation", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="SECURITY_ERROR",
            detail=detail,
            details=details,
        )


class PluginLoadError(Exception):
    """Plugin load error"""
    pass


class PluginInstallError(Exception):
    """Plugin installation error"""
    pass


class PluginSecurityError(Exception):
    """Plugin security error"""
    pass


class DatabaseError(CustomHTTPException):
    """Database error"""
    
    def __init__(self, detail: str = "Database error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            detail=detail,
            details=details,
        )


# Aliases for backwards compatibility
RateLimitExceeded = RateLimitError
APIException = CustomHTTPException  # Generic API exception alias