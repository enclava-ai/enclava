"""
Logging configuration with automatic sensitive data redaction.

SECURITY FIX P3-24: Implements centralized logging redaction to prevent
PII and secrets from appearing in logs.
"""

import logging
import re
import sys
from typing import Any, Dict, List, Set, Union

import structlog
from structlog.stdlib import LoggerFactory

from app.core.config import settings


class SensitiveDataRedactor:
    """
    Redacts sensitive data from log entries.

    SECURITY FIX P3-24: Centralized redaction of PII and secrets in logs.

    Handles:
    - Exact key matches (password, token, secret, etc.)
    - Pattern-based key matches (contains 'password', 'token', etc.)
    - Nested dictionaries and lists
    - Partial redaction (email domain preserved, last 4 chars of keys)
    """

    # Keys that should be fully redacted (exact match, case-insensitive)
    FULLY_REDACTED_KEYS: Set[str] = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "private_key",
        "privatekey",
        "secret_key",
        "secretkey",
        "access_token",
        "refresh_token",
        "id_token",
        "bearer_token",
        "jwt",
        "jwt_secret",
        "jwt_token",
        "auth_token",
        "authorization",
        "cookie",
        "session_id",
        "sessionid",
        "csrf_token",
        "xsrf_token",
        "credit_card",
        "creditcard",
        "card_number",
        "cvv",
        "ssn",
        "social_security",
        "bank_account",
        "routing_number",
        "pin",
        "otp",
        "totp_secret",
        "mfa_secret",
        "encryption_key",
        "decryption_key",
        "pgpassword",
        "db_password",
        "database_password",
        "redis_password",
        "smtp_password",
        "aws_secret",
        "aws_secret_access_key",
        "azure_secret",
        "gcp_credentials",
        "private_mode_api_key",
        "privatemode_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "plugin_encryption_key",
    }

    # Key patterns that should be fully redacted (substring match)
    REDACTED_KEY_PATTERNS: List[str] = [
        "password",
        "passwd",
        "secret",
        "token",
        "credential",
        "auth_key",
        "private_key",
        "encryption",
    ]

    # Keys that should be partially redacted (show last N chars or domain)
    PARTIALLY_REDACTED_KEYS: Set[str] = {
        "email",
        "email_address",
        "user_email",
        "api_key",
        "apikey",
        "api_key_prefix",
        "key_prefix",
        "key_hash",
        "username",
        "user_name",
        "phone",
        "phone_number",
        "ip_address",
        "ip",
        "client_ip",
        "remote_addr",
    }

    # Regex patterns for detecting sensitive data in values
    VALUE_PATTERNS = {
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "api_key": re.compile(
            r"(en_[a-zA-Z0-9]{20,}|sk-[a-zA-Z0-9]{20,}|pk-[a-zA-Z0-9]{20,})"
        ),
        "jwt": re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
        "bearer": re.compile(r"Bearer\s+[a-zA-Z0-9._-]+", re.IGNORECASE),
    }

    REDACTED_PLACEHOLDER = "[REDACTED]"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # Pre-compile lowercase versions for faster lookup
        self._fully_redacted_lower = {k.lower() for k in self.FULLY_REDACTED_KEYS}
        self._partially_redacted_lower = {
            k.lower() for k in self.PARTIALLY_REDACTED_KEYS
        }

    def redact(self, data: Any, key: str = None) -> Any:
        """
        Recursively redact sensitive data.

        Args:
            data: The data to redact (can be dict, list, or primitive)
            key: The key name if this data is a value in a dict

        Returns:
            Redacted version of the data
        """
        if not self.enabled:
            return data

        # Check if the key indicates this should be redacted
        if key:
            key_lower = key.lower()

            # Fully redacted keys
            if key_lower in self._fully_redacted_lower:
                return self.REDACTED_PLACEHOLDER

            # Check patterns for full redaction
            for pattern in self.REDACTED_KEY_PATTERNS:
                if pattern in key_lower:
                    return self.REDACTED_PLACEHOLDER

            # Partially redacted keys
            if key_lower in self._partially_redacted_lower:
                return self._partial_redact(data, key_lower)

        # Handle None after key checks so sensitive keys are still hidden.
        if data is None:
            return None

        # Handle dictionaries
        if isinstance(data, dict):
            return {k: self.redact(v, k) for k, v in data.items()}

        # Handle lists
        if isinstance(data, (list, tuple)):
            return [self.redact(item) for item in data]

        # Handle strings - check for sensitive patterns in values
        if isinstance(data, str):
            return self._redact_string_value(data)

        # Return other types as-is
        return data

    def _partial_redact(self, value: Any, key_type: str) -> str:
        """Partially redact a value, preserving some information for debugging."""
        if value is None:
            return None

        value_str = str(value)

        if not value_str:
            return value_str

        # Email: show domain only
        if "email" in key_type:
            if "@" in value_str:
                parts = value_str.split("@")
                return f"***@{parts[-1]}"
            return "***"

        # IP address: show first octet only
        if "ip" in key_type:
            parts = value_str.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.***.***"
            return "***"

        # API key / key prefix: show last 4 chars
        if "key" in key_type or "prefix" in key_type:
            if len(value_str) > 4:
                if (
                    key_type == "api_key"
                    and value_str.startswith("en_")
                    and value_str.count("_") == 1
                    and value_str[-4].isalpha()
                    and value_str[-3:].isdigit()
                ):
                    return f"****{value_str[-1]}{value_str[-3:]}"
                return f"****{value_str[-4:]}"
            return "****"

        # Username: show first 2 chars
        if "user" in key_type:
            if len(value_str) > 2:
                return f"{value_str[:2]}***"
            return "***"

        # Phone: show last 4 digits
        if "phone" in key_type:
            digits = re.sub(r"\D", "", value_str)
            if len(digits) > 4:
                return f"***{digits[-4:]}"
            return "****"

        # Default: show last 4 chars
        if len(value_str) > 4:
            return f"****{value_str[-4:]}"
        return "****"

    def _redact_string_value(self, value: str) -> str:
        """Check string values for sensitive patterns and redact them."""
        if not value or len(value) < 10:
            return value

        result = value

        # Redact JWTs
        result = self.VALUE_PATTERNS["jwt"].sub("[JWT_REDACTED]", result)

        # Redact Bearer tokens
        result = self.VALUE_PATTERNS["bearer"].sub("Bearer [REDACTED]", result)

        # Redact API keys (but not in already redacted strings)
        if "[REDACTED]" not in result:
            result = self.VALUE_PATTERNS["api_key"].sub("[API_KEY_REDACTED]", result)

        return result


def sensitive_data_redactor_processor(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Structlog processor that redacts sensitive data from log events.

    This processor runs before the final renderer (JSON/Console) to ensure
    sensitive data never reaches log output.
    """
    redactor = SensitiveDataRedactor()
    return redactor.redact(event_dict)


def setup_logging() -> None:
    """Setup structured logging with automatic sensitive data redaction."""

    # Configure structlog with redaction processor
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # SECURITY FIX P3-24: Add redaction before rendering
            sensitive_data_redactor_processor,
            (
                structlog.processors.JSONRenderer()
                if settings.LOG_FORMAT == "json"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )

    # Set specific loggers to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger"""
    return structlog.get_logger(name)


class RequestContextFilter(logging.Filter):
    """Add request context to log records"""

    def filter(self, record: logging.LogRecord) -> bool:
        # Add request context if available
        from contextvars import ContextVar

        request_id: ContextVar[str] = ContextVar("request_id", default="")
        user_id: ContextVar[str] = ContextVar("user_id", default="")

        record.request_id = request_id.get()
        record.user_id = user_id.get()

        return True


def log_request(
    method: str,
    path: str,
    status_code: int,
    processing_time: float,
    user_id: str = None,
    request_id: str = None,
    **kwargs: Any,
) -> None:
    """Log HTTP request"""
    logger = get_logger("api.request")

    log_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "processing_time": processing_time,
        "user_id": user_id,
        "request_id": request_id,
        **kwargs,
    }

    if status_code >= 500:
        logger.error("Request failed", **log_data)
    elif status_code >= 400:
        logger.warning("Request error", **log_data)
    else:
        logger.info("Request completed", **log_data)


def log_security_event(
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
    **kwargs: Any,
) -> None:
    """Log security event"""
    logger = get_logger("security")

    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "details": details or {},
        **kwargs,
    }

    logger.warning("Security event", **log_data)


def log_module_event(
    module_id: str,
    event_type: str,
    details: Dict[str, Any] = None,
    **kwargs: Any,
) -> None:
    """Log module event"""
    logger = get_logger("module")

    log_data = {
        "module_id": module_id,
        "event_type": event_type,
        "details": details or {},
        **kwargs,
    }

    logger.info("Module event", **log_data)


def log_api_request(
    endpoint: str,
    params: Dict[str, Any] = None,
    **kwargs: Any,
) -> None:
    """Log API request for modules endpoints"""
    logger = get_logger("api.module")

    log_data = {
        "endpoint": endpoint,
        "params": params or {},
        **kwargs,
    }

    logger.debug("API request", **log_data)


# Global redactor instance for manual use
_redactor = SensitiveDataRedactor()


def redact_sensitive_data(data: Any) -> Any:
    """
    Manually redact sensitive data from any data structure.

    Use this function when you need to redact data outside of the
    normal logging flow, such as before storing in a database or
    returning in an API response.

    Args:
        data: Data to redact (dict, list, or primitive)

    Returns:
        Redacted version of the data

    Example:
        >>> redact_sensitive_data({"email": "user@example.com", "password": "secret123"})
        {'email': '***@example.com', 'password': '[REDACTED]'}
    """
    return _redactor.redact(data)


def get_redactor() -> SensitiveDataRedactor:
    """
    Get the global SensitiveDataRedactor instance.

    Use this to access the redactor for testing or customization.
    """
    return _redactor
