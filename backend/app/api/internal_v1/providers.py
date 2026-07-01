"""
Provider Health API Endpoints

Internal API endpoints for monitoring inference provider health and attestation.
These endpoints require admin privileges.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import RequiresRole
from app.db.database import get_db

logger = get_logger(__name__)

router = APIRouter()

# Dependency for admin access
require_admin = RequiresRole("admin")


@router.get("/health")
async def get_providers_health(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get health status of all inference providers.

    Returns provider health information including:
    - Current health status (healthy/unhealthy)
    - Last check timestamp
    - Attestation details (for TEE providers)
    - Pricing information

    Requires admin role.
    """
    try:
        # Import here to avoid circular dependency
        from app.services.llm import llm_service

        # Get health status from LLM service (with db session for pricing lookup)
        providers_health = await llm_service.get_providers_health(db)

        return providers_health

    except Exception as e:
        logger.error(f"Error fetching provider health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch provider health: {str(e)}",
        )


@router.post("/{provider_id}/verify")
async def verify_provider(
    provider_id: str, current_user: dict = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Force immediate attestation verification for a provider.

    Triggers an on-demand attestation check for the specified provider
    and returns the verification results.

    Args:
        provider_id: ID of the provider to verify (e.g., "privatemode", "redpill")

    Returns:
        Verification result with attestation details

    Requires admin role.
    """
    user_id = current_user.get("id")
    logger.info(f"Admin {user_id} triggering verification for provider {provider_id}")

    try:
        # Import here to avoid circular dependency
        from app.services.llm.attestation.scheduler import attestation_scheduler

        # Trigger immediate verification
        result = await attestation_scheduler.verify_now(provider_id)

        return {
            "healthy": result.verified,
            "provider_id": result.provider_id,
            "model": result.model,
            "timestamp": result.timestamp.isoformat(),
            "intel_tdx_verified": result.intel_tdx_verified,
            "gpu_attestation_verified": result.gpu_attestation_verified,
            "nonce_binding_verified": result.nonce_binding_verified,
            "signing_address": result.signing_address,
            "errors": result.errors,
        }

    except ValueError as e:
        # Unknown provider
        logger.warning(f"Unknown provider requested: {provider_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Verification failed for provider {provider_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )
