"""
Logging configuration
"""

import logging
import sys
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory

from app.core.config import settings


def setup_logging() -> None:
    """Setup structured logging"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer(),
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
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


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
    
    logger.info("API request", **log_data)