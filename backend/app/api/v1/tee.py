"""
TEE (Trusted Execution Environment) API endpoints
Handles Privatemode.ai TEE integration endpoints
"""

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.services.tee_service import tee_service
from app.services.api_key_auth import get_current_api_key_user
from app.models.user import User
from app.models.api_key import APIKey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tee", tags=["tee"])
security = HTTPBearer()


class AttestationRequest(BaseModel):
    """Request model for attestation"""
    nonce: Optional[str] = Field(None, description="Optional nonce for attestation")


class AttestationVerificationRequest(BaseModel):
    """Request model for attestation verification"""
    report: str = Field(..., description="Attestation report")
    signature: str = Field(..., description="Attestation signature")
    certificate_chain: str = Field(..., description="Certificate chain")
    nonce: Optional[str] = Field(None, description="Optional nonce")


class SecureSessionRequest(BaseModel):
    """Request model for secure session creation"""
    capabilities: Optional[list] = Field(
        default=["confidential_inference", "secure_memory", "attestation"],
        description="Requested TEE capabilities"
    )


@router.get("/health")
async def get_tee_health():
    """
    Get TEE environment health status
    
    Returns comprehensive health information about the TEE environment
    including capabilities, status, and availability.
    """
    try:
        health_data = await tee_service.health_check()
        return {
            "success": True,
            "data": health_data
        }
    except Exception as e:
        logger.error(f"TEE health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get TEE health status"
        )


@router.get("/capabilities")
async def get_tee_capabilities(
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Get TEE environment capabilities
    
    Returns detailed information about TEE capabilities including
    supported features, encryption algorithms, and security properties.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        capabilities = await tee_service.get_tee_capabilities()
        
        return {
            "success": True,
            "data": capabilities
        }
    except Exception as e:
        logger.error(f"Failed to get TEE capabilities: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get TEE capabilities"
        )


@router.post("/attestation")
async def get_attestation(
    request: AttestationRequest,
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Get TEE attestation report
    
    Generates a cryptographic attestation report that proves the integrity
    and authenticity of the TEE environment. The report can be used to
    verify that code is running in a genuine TEE.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        attestation_data = await tee_service.get_attestation(request.nonce)
        
        return {
            "success": True,
            "data": attestation_data
        }
    except Exception as e:
        logger.error(f"Failed to get attestation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get TEE attestation"
        )


@router.post("/attestation/verify")
async def verify_attestation(
    request: AttestationVerificationRequest,
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Verify TEE attestation report
    
    Verifies the authenticity and integrity of a TEE attestation report.
    This includes validating the certificate chain, signature, and
    measurements against known good values.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        
        attestation_data = {
            "report": request.report,
            "signature": request.signature,
            "certificate_chain": request.certificate_chain,
            "nonce": request.nonce
        }
        
        verification_result = await tee_service.verify_attestation(attestation_data)
        
        return {
            "success": True,
            "data": verification_result
        }
    except Exception as e:
        logger.error(f"Failed to verify attestation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to verify TEE attestation"
        )


@router.post("/session")
async def create_secure_session(
    request: SecureSessionRequest,
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Create a secure TEE session
    
    Creates a secure session within the TEE environment with requested
    capabilities. The session provides isolated execution context with
    enhanced security properties.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        
        session_data = await tee_service.create_secure_session(
            user_id=str(user.id),
            api_key_id=api_key.id
        )
        
        return {
            "success": True,
            "data": session_data
        }
    except Exception as e:
        logger.error(f"Failed to create secure session: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create TEE secure session"
        )


@router.get("/metrics")
async def get_privacy_metrics(
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Get privacy and security metrics
    
    Returns comprehensive metrics about TEE usage, privacy protection,
    and security status including request counts, data encrypted,
    and performance statistics.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        metrics = await tee_service.get_privacy_metrics()
        
        return {
            "success": True,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get privacy metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get privacy metrics"
        )


@router.get("/models")
async def list_tee_models(
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    List available TEE models
    
    Returns a list of AI models available through the TEE environment.
    These models provide confidential inference capabilities with
    enhanced privacy and security properties.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        models = await tee_service.list_tee_models()
        
        return {
            "success": True,
            "data": models,
            "count": len(models)
        }
    except Exception as e:
        logger.error(f"Failed to list TEE models: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list TEE models"
        )


@router.get("/status")
async def get_tee_status(
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Get comprehensive TEE status
    
    Returns combined status information including health, capabilities,
    and metrics for a complete overview of the TEE environment.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        
        # Get all status information
        health_data = await tee_service.health_check()
        capabilities = await tee_service.get_tee_capabilities()
        metrics = await tee_service.get_privacy_metrics()
        models = await tee_service.list_tee_models()
        
        status_data = {
            "health": health_data,
            "capabilities": capabilities,
            "metrics": metrics,
            "models": {
                "available": len(models),
                "list": models
            },
            "summary": {
                "tee_enabled": health_data.get("tee_enabled", False),
                "secure_inference_available": len(models) > 0,
                "attestation_available": health_data.get("attestation_available", False),
                "privacy_score": metrics.get("privacy_score", 0)
            }
        }
        
        return {
            "success": True,
            "data": status_data
        }
    except Exception as e:
        logger.error(f"Failed to get TEE status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get TEE status"
        )


@router.delete("/cache")
async def clear_attestation_cache(
    current_user: tuple = Depends(get_current_api_key_user)
):
    """
    Clear attestation cache
    
    Manually clears the attestation cache to force fresh attestation
    reports. This can be useful for debugging or when attestation
    requirements change.
    
    Requires authentication.
    """
    try:
        user, api_key = current_user
        
        # Clear the cache
        await tee_service.cleanup_expired_cache()
        tee_service.attestation_cache.clear()
        
        return {
            "success": True,
            "message": "Attestation cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"Failed to clear attestation cache: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to clear attestation cache"
        )