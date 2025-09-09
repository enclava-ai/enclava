"""
Internal LLM API endpoints - for frontend use with JWT authentication
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user
from app.services.llm.service import llm_service
from app.api.v1.llm import get_cached_models  # Reuse the caching logic

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models")
async def list_models(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    List available LLM models for authenticated users
    """
    try:
        models = await get_cached_models()
        return {"data": models}
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve models"
        )


@router.get("/providers/status")
async def get_provider_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get status of all LLM providers for authenticated users
    """
    try:
        provider_status = await llm_service.get_provider_status()
        return {
            "object": "provider_status",
            "data": {
                name: {
                    "provider": status.provider,
                    "status": status.status,
                    "latency_ms": status.latency_ms,
                    "success_rate": status.success_rate,
                    "last_check": status.last_check.isoformat(),
                    "error_message": status.error_message,
                    "models_available": status.models_available
                }
                for name, status in provider_status.items()
            }
        }
    except Exception as e:
        logger.error(f"Failed to get provider status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider status"
        )


@router.get("/health")
async def health_check(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get LLM service health status for authenticated users
    """
    try:
        health = await llm_service.health_check()
        return {
            "status": health["status"],
            "providers": health.get("providers", {}),
            "timestamp": health.get("timestamp")
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.get("/metrics")
async def get_metrics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get LLM service metrics for authenticated users
    """
    try:
        metrics = await llm_service.get_metrics()
        return {
            "object": "metrics",
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )