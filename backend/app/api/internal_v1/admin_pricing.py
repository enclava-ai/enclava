"""
Admin Pricing API Endpoints

Internal API endpoints for managing provider pricing.
These endpoints require admin privileges.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import RequiresRole, get_current_user
from app.db.database import get_db
from app.models import User
from app.schemas.pricing import (
    PricingAuditLogResponse,
    PricingHistoryResponse,
    PricingListResponse,
    PricingResponse,
    PricingSummary,
    ProviderListResponse,
    ProviderMetadataResponse,
    RemoveOverrideResponse,
    SetPricingRequest,
    SyncResultModel,
    SyncResultResponse,
)
from app.services.pricing_management import PricingManagementService
from app.services.provider_pricing_sync import ProviderPricingSyncService
from app.services.provider_registry import (
    get_all_providers,
    get_currency_symbol,
    get_provider_currency,
)

logger = get_logger(__name__)

router = APIRouter()


# Dependency for admin access
require_admin = RequiresRole("admin")


def _pricing_to_response(pricing) -> PricingResponse:
    """Convert ProviderPricing model to response schema"""
    # Get currency from pricing record, or fall back to provider default
    currency = getattr(pricing, "currency", None) or get_provider_currency(
        pricing.provider_id
    )
    return PricingResponse(
        id=pricing.id,
        provider_id=pricing.provider_id,
        model_id=pricing.model_id,
        model_name=pricing.model_name,
        input_price_per_million_cents=pricing.input_price_per_million_cents,
        output_price_per_million_cents=pricing.output_price_per_million_cents,
        input_price_per_million_dollars=pricing.input_price_per_million_cents / 100.0,
        output_price_per_million_dollars=pricing.output_price_per_million_cents / 100.0,
        currency=currency,
        price_source=pricing.price_source,
        is_override=pricing.is_override,
        override_reason=pricing.override_reason,
        override_by_user_id=pricing.override_by_user_id,
        context_length=pricing.context_length,
        architecture=pricing.architecture,
        quantization=pricing.quantization,
        effective_from=pricing.effective_from,
        effective_until=pricing.effective_until,
        is_current=pricing.is_current,
        created_at=pricing.created_at,
        updated_at=pricing.updated_at,
    )


def _history_to_response(pricing) -> PricingHistoryResponse:
    """Convert ProviderPricing model to history response schema"""
    currency = getattr(pricing, "currency", None) or get_provider_currency(
        pricing.provider_id
    )
    return PricingHistoryResponse(
        id=pricing.id,
        provider_id=pricing.provider_id,
        model_id=pricing.model_id,
        model_name=pricing.model_name,
        input_price_per_million_cents=pricing.input_price_per_million_cents,
        output_price_per_million_cents=pricing.output_price_per_million_cents,
        currency=currency,
        price_source=pricing.price_source,
        is_override=pricing.is_override,
        override_reason=pricing.override_reason,
        effective_from=pricing.effective_from,
        effective_until=pricing.effective_until,
        created_at=pricing.created_at,
    )


def _audit_to_response(audit) -> PricingAuditLogResponse:
    """Convert PricingAuditLog model to response schema"""
    return PricingAuditLogResponse(
        id=audit.id,
        provider_id=audit.provider_id,
        model_id=audit.model_id,
        action=audit.action,
        old_input_price_per_million_cents=audit.old_input_price_per_million_cents,
        old_output_price_per_million_cents=audit.old_output_price_per_million_cents,
        new_input_price_per_million_cents=audit.new_input_price_per_million_cents,
        new_output_price_per_million_cents=audit.new_output_price_per_million_cents,
        change_source=audit.change_source,
        changed_by_user_id=audit.changed_by_user_id,
        change_reason=audit.change_reason,
        sync_job_id=str(audit.sync_job_id) if audit.sync_job_id else None,
        created_at=audit.created_at,
    )


@router.post("/pricing/set", response_model=PricingResponse)
async def set_pricing(
    request: SetPricingRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PricingResponse:
    """
    Set manual pricing for a model.

    Creates a new ProviderPricing record with is_override=True.
    If existing pricing exists, it will be expired.

    Requires admin role.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )

    logger.info(
        f"Admin {user_id} setting pricing for {request.provider_id}/{request.model_id}"
    )

    service = PricingManagementService(db)

    try:
        pricing = await service.set_manual_pricing(
            provider_id=request.provider_id,
            model_id=request.model_id,
            input_price_per_million_cents=request.input_price_per_million_cents,
            output_price_per_million_cents=request.output_price_per_million_cents,
            reason=request.reason,
            user_id=user_id,
            model_name=request.model_name,
        )

        return _pricing_to_response(pricing)

    except Exception as e:
        logger.error(f"Error setting pricing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set pricing: {str(e)}",
        )


@router.delete("/pricing/override/{provider}/{model:path}")
async def remove_override(
    provider: str,
    model: str,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> RemoveOverrideResponse:
    """
    Remove manual override for a model.

    The model path parameter can contain slashes (e.g., 'meta-llama/llama-3.1-70b').

    Requires admin role.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )

    logger.info(f"Admin {user_id} removing override for {provider}/{model}")

    service = PricingManagementService(db)

    # Get existing pricing for response
    existing = await service.get_pricing_for_model(provider, model)

    success = await service.remove_override(
        provider_id=provider,
        model_id=model,
        user_id=user_id,
    )

    if not success:
        return RemoveOverrideResponse(
            success=False,
            provider_id=provider,
            model_id=model,
            message="No override found for this model",
            previous_pricing=None,
        )

    return RemoveOverrideResponse(
        success=True,
        provider_id=provider,
        model_id=model,
        message="Override removed successfully. Model will use API-synced pricing after next sync.",
        previous_pricing=_pricing_to_response(existing) if existing else None,
    )


@router.post("/pricing/sync/{provider}", response_model=SyncResultResponse)
async def trigger_sync(
    provider: str,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SyncResultResponse:
    """
    Manually trigger pricing sync for a provider.

    Fetches pricing from the provider's API and updates the database.

    Requires admin role.
    """
    user_id = current_user.get("id")
    logger.info(f"Admin {user_id} triggering pricing sync for {provider}")

    service = ProviderPricingSyncService(db)

    # Check if provider is syncable
    syncable = service.get_syncable_providers()
    if provider not in syncable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' does not support API sync. Syncable providers: {syncable}",
        )

    try:
        result = await service.sync_provider(provider)

        return SyncResultResponse(
            provider_id=result.provider_id,
            sync_job_id=str(result.sync_job_id),
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_ms=result.duration_ms,
            total_models=result.total_models,
            created_count=result.created_count,
            updated_count=result.updated_count,
            unchanged_count=result.unchanged_count,
            error_count=result.error_count,
            models=[
                SyncResultModel(
                    model_id=m.model_id,
                    model_name=m.model_name,
                    action=m.action,
                    old_input_price=m.old_input_price,
                    old_output_price=m.old_output_price,
                    new_input_price=m.new_input_price,
                    new_output_price=m.new_output_price,
                )
                for m in result.models
            ],
            errors=result.errors,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


@router.get("/pricing/history/{provider}/{model:path}")
async def get_history(
    provider: str,
    model: str,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[PricingHistoryResponse]:
    """
    Get pricing history for a model.

    The model path parameter can contain slashes.

    Requires admin role.
    """
    service = PricingManagementService(db)

    pricing_history = await service.get_pricing_history(
        provider_id=provider,
        model_id=model,
        limit=limit,
    )

    return [_history_to_response(p) for p in pricing_history]


@router.get("/pricing/all", response_model=PricingListResponse)
async def get_all_pricing(
    provider_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PricingListResponse:
    """
    Get all current pricing.

    Optionally filter by provider.

    Requires admin role.
    """
    service = PricingManagementService(db)

    pricing_list = await service.get_current_pricing(provider_id=provider_id)
    providers = await service.get_providers()

    return PricingListResponse(
        pricing=[_pricing_to_response(p) for p in pricing_list],
        total=len(pricing_list),
        providers=providers,
    )


@router.get("/pricing/model/{provider}/{model:path}", response_model=PricingResponse)
async def get_model_pricing(
    provider: str,
    model: str,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PricingResponse:
    """
    Get current pricing for a specific model.

    The model path parameter can contain slashes.

    Requires admin role.
    """
    service = PricingManagementService(db)

    pricing = await service.get_pricing_for_model(
        provider_id=provider,
        model_id=model,
    )

    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pricing found for {provider}/{model}",
        )

    return _pricing_to_response(pricing)


@router.get("/pricing/audit-log")
async def get_audit_log(
    provider_id: Optional[str] = Query(default=None),
    model_id: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[PricingAuditLogResponse]:
    """
    Get pricing audit log entries.

    Supports filtering by provider, model, and user.

    Requires admin role.
    """
    service = PricingManagementService(db)

    audit_logs = await service.get_audit_log(
        provider_id=provider_id,
        model_id=model_id,
        user_id=user_id,
        limit=limit,
    )

    return [_audit_to_response(a) for a in audit_logs]


@router.get("/pricing/summary", response_model=PricingSummary)
async def get_pricing_summary(
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PricingSummary:
    """
    Get pricing summary statistics.

    Requires admin role.
    """
    service = PricingManagementService(db)

    summary = await service.get_pricing_summary()

    return PricingSummary(
        total_models=summary["total_models"],
        models_by_provider=summary["models_by_provider"],
        override_count=summary["override_count"],
        api_sync_count=summary["api_sync_count"],
        manual_count=summary["manual_count"],
        last_sync_at=summary["last_sync_at"],
    )


@router.get("/pricing/search")
async def search_pricing(
    query: str = Query(..., min_length=1),
    provider_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[PricingResponse]:
    """
    Search for models by name or ID.

    Requires admin role.
    """
    service = PricingManagementService(db)

    results = await service.search_models(
        query=query,
        provider_id=provider_id,
        limit=limit,
    )

    return [_pricing_to_response(p) for p in results]


@router.get("/pricing/syncable-providers")
async def get_syncable_providers(
    current_user: dict = Depends(require_admin),
) -> List[str]:
    """
    Get list of providers that support API sync.

    Requires admin role.
    """
    return ProviderPricingSyncService.get_syncable_providers()


@router.get("/pricing/available-providers", response_model=ProviderListResponse)
async def get_available_providers(
    current_user: dict = Depends(require_admin),
) -> ProviderListResponse:
    """
    Get all available providers with their metadata.

    Returns provider information including:
    - Native currency (EUR for PrivateMode, USD for RedPill)
    - Whether the provider supports API sync
    - Display name and description

    Requires admin role.
    """
    providers = get_all_providers()

    provider_responses = [
        ProviderMetadataResponse(
            id=p.id,
            display_name=p.display_name,
            currency=p.currency,
            currency_symbol=get_currency_symbol(p.currency),
            supports_api_sync=p.supports_api_sync,
            description=p.description,
            website=p.website,
        )
        for p in providers
    ]

    return ProviderListResponse(
        providers=provider_responses,
        total=len(provider_responses),
    )
