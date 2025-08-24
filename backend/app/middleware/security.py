"""
Security middleware for request/response processing
"""

import json
import time
from typing import Callable, Optional, Dict, Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.core.threat_detection import threat_detection_service, SecurityAnalysis

logger = get_logger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for threat detection and request filtering"""
    
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled and settings.API_SECURITY_ENABLED
        logger.info(f"SecurityMiddleware initialized, enabled: {self.enabled}")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security analysis"""
        if not self.enabled:
            # Security disabled, pass through
            return await call_next(request)
        
        # Skip security analysis for certain endpoints
        if self._should_skip_security(request):
            response = await call_next(request)
            return self._add_security_headers(response)
        
        # Simple authentication check - drop requests without valid auth
        if not self._has_valid_auth(request):
            return JSONResponse(
                content={"error": "Authentication required", "message": "Valid API key or authentication token required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        try:
            # Get user context if available
            user_context = getattr(request.state, 'user', None)
            
            # Perform security analysis
            start_time = time.time()
            analysis = await threat_detection_service.analyze_request(request, user_context)
            analysis_time = time.time() - start_time
            
            # Store analysis in request state for later use
            request.state.security_analysis = analysis
            
            # Log security events (only for significant threats to reduce false positive noise)
            # Only log if: being blocked OR risk score above warning threshold (0.6)
            if analysis.is_threat and (analysis.should_block or analysis.risk_score >= settings.API_SECURITY_WARNING_THRESHOLD):
                await self._log_security_event(request, analysis)
            
            # Check if request should be blocked
            if analysis.should_block:
                threat_detection_service.stats['threats_blocked'] += 1
                logger.warning(f"Blocked request from {request.client.host if request.client else 'unknown'}: "
                             f"risk_score={analysis.risk_score:.3f}, threats={len(analysis.threats)}")
                
                # Return security block response
                return self._create_block_response(analysis)
            
            # Log warnings for medium-risk requests
            if analysis.risk_score >= settings.API_SECURITY_WARNING_THRESHOLD:
                logger.warning(f"High-risk request detected from {request.client.host if request.client else 'unknown'}: "
                             f"risk_score={analysis.risk_score:.3f}, auth_level={analysis.auth_level.value}")
            
            # Continue with request processing
            response = await call_next(request)
            
            # Add security headers and metrics
            response = self._add_security_headers(response)
            response = self._add_security_metrics(response, analysis, analysis_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # Continue with request on security middleware errors to avoid breaking the app
            response = await call_next(request)
            return self._add_security_headers(response)
    
    def _should_skip_security(self, request: Request) -> bool:
        """Determine if security analysis should be skipped for this request"""
        path = request.url.path
        
        # Skip for health checks, authentication endpoints, and static assets
        skip_paths = [
            "/health",
            "/metrics", 
            "/api/v1/docs",
            "/api/v1/openapi.json",
            "/api/v1/redoc",
            "/favicon.ico",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/",  # Root endpoint
        ]
        
        # Skip for static file extensions
        static_extensions = [".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2"]
        
        return (
            path in skip_paths or 
            any(path.endswith(ext) for ext in static_extensions) or
            path.startswith("/static/")
        )
    
    def _has_valid_auth(self, request: Request) -> bool:
        """Check if request has valid authentication"""
        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")
        
        # Has some form of auth token/key
        return (
            auth_header.startswith("Bearer ") and len(auth_header) > 7 or
            len(api_key_header.strip()) > 0
        )
    
    def _create_block_response(self, analysis: SecurityAnalysis) -> JSONResponse:
        """Create response for blocked requests"""
        # Determine status code based on threat type
        status_code = 403  # Forbidden by default
        
        # Rate limiting gets 429
        if analysis.rate_limit_exceeded:
            status_code = 429
        
        # Critical threats get 403
        for threat in analysis.threats:
            if threat.threat_type in ["command_injection", "sql_injection"]:
                status_code = 403
                break
        
        response_data = {
            "error": "Security Policy Violation",
            "message": "Request blocked due to security policy violation",
            "risk_score": round(analysis.risk_score, 3),
            "auth_level": analysis.auth_level.value,
            "threat_count": len(analysis.threats),
            "recommendations": analysis.recommendations[:3]  # Limit to first 3 recommendations
        }
        
        # Add rate limiting info if applicable
        if analysis.rate_limit_exceeded:
            response_data["error"] = "Rate Limit Exceeded"
            response_data["message"] = f"Rate limit exceeded for {analysis.auth_level.value} user"
            response_data["retry_after"] = "60"  # Suggest retry after 60 seconds
        
        response = JSONResponse(
            content=response_data,
            status_code=status_code
        )
        
        # Add rate limiting headers
        if analysis.rate_limit_exceeded:
            response.headers["Retry-After"] = "60"
            response.headers["X-RateLimit-Limit"] = "See API documentation"
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
        
        return response
    
    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        if not settings.API_SECURITY_HEADERS_ENABLED:
            return response
        
        # Standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Only add HSTS for HTTPS
        if hasattr(response, 'headers') and response.headers.get("X-Forwarded-Proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        if settings.API_CSP_HEADER:
            response.headers["Content-Security-Policy"] = settings.API_CSP_HEADER
        
        return response
    
    def _add_security_metrics(self, response: Response, analysis: SecurityAnalysis, analysis_time: float) -> Response:
        """Add security metrics to response headers (for debugging/monitoring)"""
        # Only add in debug mode or for admin users
        if settings.APP_DEBUG:
            response.headers["X-Security-Risk-Score"] = str(round(analysis.risk_score, 3))
            response.headers["X-Security-Threats"] = str(len(analysis.threats))
            response.headers["X-Security-Auth-Level"] = analysis.auth_level.value
            response.headers["X-Security-Analysis-Time"] = f"{analysis_time*1000:.1f}ms"
        
        return response
    
    async def _log_security_event(self, request: Request, analysis: SecurityAnalysis):
        """Log security events for audit and monitoring"""
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        
        # Create security event log
        event_data = {
            "timestamp": analysis.timestamp.isoformat(),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "path": str(request.url.path),
            "method": request.method,
            "risk_score": round(analysis.risk_score, 3),
            "auth_level": analysis.auth_level.value,
            "threat_count": len(analysis.threats),
            "rate_limit_exceeded": analysis.rate_limit_exceeded,
            "should_block": analysis.should_block,
            "threats": [
                {
                    "type": threat.threat_type,
                    "level": threat.level.value,
                    "confidence": round(threat.confidence, 3),
                    "description": threat.description
                }
                for threat in analysis.threats[:5]  # Limit to first 5 threats
            ],
            "recommendations": analysis.recommendations
        }
        
        # Log at appropriate level based on risk
        if analysis.should_block:
            logger.warning(f"SECURITY_BLOCK: {json.dumps(event_data)}")
        elif analysis.risk_score >= settings.API_SECURITY_WARNING_THRESHOLD:
            logger.warning(f"SECURITY_WARNING: {json.dumps(event_data)}")
        else:
            logger.info(f"SECURITY_THREAT: {json.dumps(event_data)}")


def setup_security_middleware(app, enabled: bool = True) -> None:
    """Setup security middleware on FastAPI app"""
    if enabled and settings.API_SECURITY_ENABLED:
        app.add_middleware(SecurityMiddleware, enabled=enabled)
        logger.info("Security middleware enabled")
    else:
        logger.info("Security middleware disabled")


# Helper functions for manual security checks
async def analyze_request_security(request: Request, user_context: Optional[Dict] = None) -> SecurityAnalysis:
    """Manually analyze request security (for use in route handlers)"""
    return await threat_detection_service.analyze_request(request, user_context)


def get_security_stats() -> Dict[str, Any]:
    """Get security statistics"""
    return threat_detection_service.get_stats()


def is_request_blocked(request: Request) -> bool:
    """Check if request was blocked by security analysis"""
    if hasattr(request.state, 'security_analysis'):
        return request.state.security_analysis.should_block
    return False


def get_request_risk_score(request: Request) -> float:
    """Get risk score for request"""
    if hasattr(request.state, 'security_analysis'):
        return request.state.security_analysis.risk_score
    return 0.0


def get_request_auth_level(request: Request) -> str:
    """Get authentication level for request"""
    if hasattr(request.state, 'security_analysis'):
        return request.state.security_analysis.auth_level.value
    return "unknown"