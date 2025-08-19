"""
Security API endpoints for monitoring and configuration
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.security import get_current_active_user, RequiresRole
from app.middleware.security import get_security_stats, get_request_auth_level, get_request_risk_score
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["security"])


# Pydantic models for API responses
class SecurityStatsResponse(BaseModel):
    """Security statistics response model"""
    total_requests_analyzed: int
    threats_detected: int
    threats_blocked: int
    anomalies_detected: int
    rate_limits_exceeded: int
    avg_analysis_time: float
    threat_types: Dict[str, int]
    threat_levels: Dict[str, int]
    top_attacking_ips: List[tuple]
    security_enabled: bool
    threat_detection_enabled: bool
    rate_limiting_enabled: bool


class SecurityConfigResponse(BaseModel):
    """Security configuration response model"""
    security_enabled: bool = Field(description="Overall security system enabled")
    threat_detection_enabled: bool = Field(description="Threat detection analysis enabled")
    rate_limiting_enabled: bool = Field(description="Rate limiting enabled")
    ip_reputation_enabled: bool = Field(description="IP reputation checking enabled")
    anomaly_detection_enabled: bool = Field(description="Anomaly detection enabled")
    security_headers_enabled: bool = Field(description="Security headers enabled")
    
    # Rate limiting settings
    unauthenticated_per_minute: int = Field(description="Rate limit for unauthenticated requests per minute")
    authenticated_per_minute: int = Field(description="Rate limit for authenticated users per minute")
    api_key_per_minute: int = Field(description="Rate limit for API key users per minute")
    premium_per_minute: int = Field(description="Rate limit for premium users per minute")
    
    # Security thresholds
    risk_threshold: float = Field(description="Risk score threshold for blocking requests")
    warning_threshold: float = Field(description="Risk score threshold for warnings")
    anomaly_threshold: float = Field(description="Anomaly severity threshold")
    
    # IP settings
    blocked_ips: List[str] = Field(description="List of blocked IP addresses")
    allowed_ips: List[str] = Field(description="List of allowed IP addresses (empty = allow all)")


class RateLimitInfoResponse(BaseModel):
    """Rate limit information for current request"""
    auth_level: str = Field(description="Authentication level (unauthenticated, authenticated, api_key, premium)")
    current_limits: Dict[str, int] = Field(description="Current rate limits for this auth level")
    remaining_requests: Optional[Dict[str, int]] = Field(description="Estimated remaining requests (if available)")


@router.get("/stats", response_model=SecurityStatsResponse)
async def get_security_statistics(
    current_user: Dict[str, Any] = Depends(RequiresRole("admin"))
):
    """
    Get security system statistics
    
    Requires admin role. Returns comprehensive statistics about:
    - Request analysis counts
    - Threat detection results
    - Rate limiting enforcement
    - Top attacking IPs
    - Performance metrics
    """
    try:
        stats = get_security_stats()
        return SecurityStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting security stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security statistics"
        )


@router.get("/config", response_model=SecurityConfigResponse)
async def get_security_config(
    current_user: Dict[str, Any] = Depends(RequiresRole("admin"))
):
    """
    Get current security configuration
    
    Requires admin role. Returns current security settings including:
    - Feature enablement flags
    - Rate limiting thresholds
    - Security thresholds
    - IP allowlists/blocklists
    """
    return SecurityConfigResponse(
        security_enabled=settings.API_SECURITY_ENABLED,
        threat_detection_enabled=settings.API_THREAT_DETECTION_ENABLED,
        rate_limiting_enabled=settings.API_RATE_LIMITING_ENABLED,
        ip_reputation_enabled=settings.API_IP_REPUTATION_ENABLED,
        anomaly_detection_enabled=settings.API_ANOMALY_DETECTION_ENABLED,
        security_headers_enabled=settings.API_SECURITY_HEADERS_ENABLED,
        
        unauthenticated_per_minute=settings.API_RATE_LIMIT_UNAUTHENTICATED_PER_MINUTE,
        authenticated_per_minute=settings.API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE,
        api_key_per_minute=settings.API_RATE_LIMIT_API_KEY_PER_MINUTE,
        premium_per_minute=settings.API_RATE_LIMIT_PREMIUM_PER_MINUTE,
        
        risk_threshold=settings.API_SECURITY_RISK_THRESHOLD,
        warning_threshold=settings.API_SECURITY_WARNING_THRESHOLD,
        anomaly_threshold=settings.API_SECURITY_ANOMALY_THRESHOLD,
        
        blocked_ips=settings.API_BLOCKED_IPS,
        allowed_ips=settings.API_ALLOWED_IPS
    )


@router.get("/status")
async def get_security_status(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get security status for current request
    
    Returns information about the security analysis of the current request:
    - Authentication level
    - Risk score (if available)
    - Rate limiting status
    """
    auth_level = get_request_auth_level(request)
    risk_score = get_request_risk_score(request)
    
    # Get rate limits for current auth level
    from app.core.threat_detection import AuthLevel
    try:
        auth_enum = AuthLevel(auth_level)
        from app.core.threat_detection import threat_detection_service
        minute_limit, hour_limit = threat_detection_service.get_rate_limits(auth_enum)
        
        rate_limit_info = RateLimitInfoResponse(
            auth_level=auth_level,
            current_limits={
                "per_minute": minute_limit,
                "per_hour": hour_limit
            },
            remaining_requests=None  # We don't track remaining requests in current implementation
        )
    except ValueError:
        rate_limit_info = RateLimitInfoResponse(
            auth_level=auth_level,
            current_limits={},
            remaining_requests=None
        )
    
    return {
        "security_enabled": settings.API_SECURITY_ENABLED,
        "auth_level": auth_level,
        "risk_score": round(risk_score, 3) if risk_score > 0 else None,
        "rate_limit_info": rate_limit_info.dict(),
        "security_headers_enabled": settings.API_SECURITY_HEADERS_ENABLED
    }


@router.post("/test")
async def test_security_analysis(
    request: Request,
    current_user: Dict[str, Any] = Depends(RequiresRole("admin"))
):
    """
    Test security analysis on current request
    
    Requires admin role. Manually triggers security analysis on the current request
    and returns detailed results. Useful for testing security rules and thresholds.
    """
    try:
        from app.middleware.security import analyze_request_security
        
        analysis = await analyze_request_security(request, current_user)
        
        return {
            "analysis_complete": True,
            "is_threat": analysis.is_threat,
            "risk_score": round(analysis.risk_score, 3),
            "auth_level": analysis.auth_level.value,
            "should_block": analysis.should_block,
            "rate_limit_exceeded": analysis.rate_limit_exceeded,
            "threat_count": len(analysis.threats),
            "threats": [
                {
                    "type": threat.threat_type,
                    "level": threat.level.value,
                    "confidence": round(threat.confidence, 3),
                    "description": threat.description,
                    "mitigation": threat.mitigation
                }
                for threat in analysis.threats
            ],
            "recommendations": analysis.recommendations
        }
    except Exception as e:
        logger.error(f"Error in security analysis test: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform security analysis test"
        )


@router.get("/health")
async def security_health_check():
    """
    Security system health check
    
    Public endpoint that returns the health status of the security system.
    Does not require authentication.
    """
    try:
        stats = get_security_stats()
        
        # Basic health checks
        is_healthy = (
            settings.API_SECURITY_ENABLED and
            stats.get("total_requests_analyzed", 0) >= 0 and
            stats.get("avg_analysis_time", 0) < 1.0  # Analysis should be under 1 second
        )
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "security_enabled": settings.API_SECURITY_ENABLED,
            "threat_detection_enabled": settings.API_THREAT_DETECTION_ENABLED,
            "rate_limiting_enabled": settings.API_RATE_LIMITING_ENABLED,
            "avg_analysis_time_ms": round(stats.get("avg_analysis_time", 0) * 1000, 2),
            "total_requests_analyzed": stats.get("total_requests_analyzed", 0)
        }
    except Exception as e:
        logger.error(f"Security health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": "Security system error",
            "security_enabled": settings.API_SECURITY_ENABLED
        }