"""
LLM Service Exceptions

Custom exceptions for LLM service operations.
"""


class LLMError(Exception):
    """Base exception for LLM service errors"""
    
    def __init__(self, message: str, error_code: str = "LLM_ERROR", details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ProviderError(LLMError):
    """Exception for LLM provider-specific errors"""
    
    def __init__(self, message: str, provider: str, error_code: str = "PROVIDER_ERROR", details: dict = None):
        super().__init__(message, error_code, details)
        self.provider = provider


class SecurityError(LLMError):
    """Exception for security-related errors"""
    
    def __init__(self, message: str, risk_score: float = 0.0, error_code: str = "SECURITY_ERROR", details: dict = None):
        super().__init__(message, error_code, details)
        self.risk_score = risk_score


class ConfigurationError(LLMError):
    """Exception for configuration-related errors"""
    
    def __init__(self, message: str, error_code: str = "CONFIG_ERROR", details: dict = None):
        super().__init__(message, error_code, details)


class RateLimitError(LLMError):
    """Exception for rate limiting errors"""
    
    def __init__(self, message: str, retry_after: int = None, error_code: str = "RATE_LIMIT_ERROR", details: dict = None):
        super().__init__(message, error_code, details)
        self.retry_after = retry_after


class TimeoutError(LLMError):
    """Exception for timeout errors"""
    
    def __init__(self, message: str, timeout_duration: float = None, error_code: str = "TIMEOUT_ERROR", details: dict = None):
        super().__init__(message, error_code, details)
        self.timeout_duration = timeout_duration


class ValidationError(LLMError):
    """Exception for request validation errors"""
    
    def __init__(self, message: str, field: str = None, error_code: str = "VALIDATION_ERROR", details: dict = None):
        super().__init__(message, error_code, details)
        self.field = field