"""
Usage Statistics API Endpoints

Internal API endpoints for querying usage statistics and records.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import RequiresRole, get_current_user
from app.db.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.usage_stats import (
    ProviderBreakdownResponse,
    TopKeysResponse,
    TopUsersResponse,
    UsageOverviewResponse,
    UsageRecordResponse,
    UsageRecordsListResponse,
    UsageStatsResponse,
)
from app.services.usage_stats import UsageStatsService

logger = get_logger(__name__)

router = APIRouter(prefix="/usage", tags=["Usage Statistics"])


@router.get("/me/stats", response_model=UsageStatsResponse)
async def get_my_usage_stats(
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d, or custom with start/end dates",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get usage statistics for the current user.

    This includes ALL usage:
    - API Key usage (external API calls)
    - Playground usage (LLM testing)
    - Agent testing

    **Periods:**
    - `7d`: Last 7 days
    - `30d`: Last 30 days (default)
    - `90d`: Last 90 days
    - `custom`: Use start_date and end_date parameters
    """
    try:
        # Get user_id from current_user (handles both dict and User object)
        user_id = (
            current_user.get("id")
            if isinstance(current_user, dict)
            else current_user.id
        )

        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date are required for custom period",
                )

        # Get stats
        stats_service = UsageStatsService(db)
        stats = await stats_service.get_user_stats(
            user_id=user_id,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return UsageStatsResponse(
            summary=stats["summary"],
            by_provider=stats["by_provider"],
            by_model=stats["by_model"],
            daily_trend=stats["daily_trend"],
            by_source=stats.get("by_source", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage statistics",
        )


@router.get("/me/records", response_model=UsageRecordsListResponse)
async def get_my_usage_records(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Records per page"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model: Optional[str] = Query(None, description="Filter by model"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status (success/error)"
    ),
    source: Optional[str] = Query(
        None, description="Filter by source (agent/api_key/playground)"
    ),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated usage records for the current user.

    This includes ALL usage sources.
    """
    try:
        # Get user_id from current_user
        user_id = (
            current_user.get("id")
            if isinstance(current_user, dict)
            else current_user.id
        )

        # Get records
        stats_service = UsageStatsService(db)
        records, total_count = await stats_service.get_user_records(
            user_id=user_id,
            page=page,
            page_size=page_size,
            provider_filter=provider,
            model_filter=model,
            status_filter=status_filter,
            source_filter=source,
            start_date=start_date,
            end_date=end_date,
        )

        # Convert to response models
        record_responses = [
            UsageRecordResponse(
                id=r.id,
                request_id=str(r.request_id),
                created_at=r.created_at,
                provider_id=r.provider_id,
                provider_model=r.provider_model,
                normalized_model=r.normalized_model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                total_tokens=r.total_tokens,
                input_cost_cents=r.input_cost_cents,
                output_cost_cents=r.output_cost_cents,
                total_cost_cents=r.total_cost_cents,
                total_cost_dollars=r.total_cost_cents / 100,
                endpoint=r.endpoint,
                method=r.method,
                is_streaming=r.is_streaming,
                latency_ms=r.latency_ms,
                status=r.status,
                error_type=r.error_type,
                error_message=r.error_message,
                agent_config_id=r.agent_config_id,
                session_id=r.session_id,
            )
            for r in records
        ]

        return UsageRecordsListResponse(
            records=record_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size,
        )

    except Exception as e:
        logger.error(f"Error getting user records: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage records",
        )


@router.get("/api-keys/{api_key_id}/stats", response_model=UsageStatsResponse)
async def get_api_key_usage_stats(
    api_key_id: int,
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d, or custom with start/end dates",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get usage statistics for a specific API key.

    User can only access their own API keys' stats.

    **Periods:**
    - `7d`: Last 7 days
    - `30d`: Last 30 days (default)
    - `90d`: Last 90 days
    - `custom`: Use start_date and end_date parameters
    """
    try:
        # Verify user owns this API key
        from sqlalchemy import select

        stmt = select(APIKey).where(APIKey.id == api_key_id)
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key {api_key_id} not found",
            )

        # Check ownership (unless admin)
        user_id = (
            current_user.get("id")
            if isinstance(current_user, dict)
            else current_user.id
        )
        is_superuser = (
            current_user.get("is_superuser", False)
            if isinstance(current_user, dict)
            else current_user.is_superuser
        )
        if api_key.user_id != user_id and not is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view stats for your own API keys",
            )

        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date required for custom period",
                )

        # Get statistics
        stats_service = UsageStatsService(db)
        stats = await stats_service.get_api_key_stats(
            api_key_id=api_key_id,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage statistics",
        )


@router.get("/api-keys/{api_key_id}/records", response_model=UsageRecordsListResponse)
async def get_api_key_usage_records(
    api_key_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Records per page"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model: Optional[str] = Query(None, description="Filter by model"),
    status_filter: Optional[str] = Query(
        None, description="Filter by status (success/error)"
    ),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated usage records for an API key.

    User can only access their own API keys' records.

    **Filters:**
    - `provider`: Filter by provider ID (e.g., 'privatemode', 'redpill')
    - `model`: Filter by normalized model name
    - `status`: Filter by status ('success' or 'error')
    - `start_date` / `end_date`: Filter by date range
    """
    try:
        # Verify user owns this API key
        from sqlalchemy import select

        stmt = select(APIKey).where(APIKey.id == api_key_id)
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key {api_key_id} not found",
            )

        # Check ownership (unless admin)
        user_id = (
            current_user.get("id")
            if isinstance(current_user, dict)
            else current_user.id
        )
        is_superuser = (
            current_user.get("is_superuser", False)
            if isinstance(current_user, dict)
            else current_user.is_superuser
        )
        if api_key.user_id != user_id and not is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view records for your own API keys",
            )

        # Get records
        stats_service = UsageStatsService(db)
        records, total_count = await stats_service.get_api_key_records(
            api_key_id=api_key_id,
            page=page,
            page_size=page_size,
            provider_filter=provider,
            model_filter=model,
            status_filter=status_filter,
            start_date=start_date,
            end_date=end_date,
        )

        # Convert to response models
        record_responses = [
            UsageRecordResponse(
                id=r.id,
                request_id=str(r.request_id),
                created_at=r.created_at,
                provider_id=r.provider_id,
                provider_model=r.provider_model,
                normalized_model=r.normalized_model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                total_tokens=r.total_tokens,
                input_cost_cents=r.input_cost_cents,
                output_cost_cents=r.output_cost_cents,
                total_cost_cents=r.total_cost_cents,
                total_cost_dollars=r.total_cost_cents / 100,
                endpoint=r.endpoint,
                method=r.method,
                status=r.status,
                error_type=r.error_type,
                is_streaming=r.is_streaming,
                latency_ms=r.latency_ms,
                ttft_ms=r.ttft_ms,
            )
            for r in records
        ]

        total_pages = (total_count + page_size - 1) // page_size

        return UsageRecordsListResponse(
            records=record_responses,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key records: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage records",
        )


# Admin Endpoints


@router.get(
    "/admin/overview",
    response_model=UsageOverviewResponse,
    dependencies=[Depends(RequiresRole("admin"))],
)
async def get_system_usage_overview(
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d, or custom",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get system-wide usage overview (admin only).

    **Periods:**
    - `7d`: Last 7 days
    - `30d`: Last 30 days (default)
    - `90d`: Last 90 days
    - `custom`: Use start_date and end_date parameters
    """
    try:
        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date required for custom period",
                )

        # Get overview
        stats_service = UsageStatsService(db)
        overview = await stats_service.get_system_overview(
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return overview

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system overview",
        )


@router.get(
    "/admin/top-users",
    response_model=TopUsersResponse,
    dependencies=[Depends(RequiresRole("admin"))],
)
async def get_top_users_by_spend(
    limit: int = Query(10, ge=1, le=100, description="Number of top users"),
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d, or custom",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top users by total spend (admin only).

    Returns ranked list of users ordered by total cost.
    """
    try:
        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date required for custom period",
                )

        # Get top users
        stats_service = UsageStatsService(db)
        users, period_start, period_end = await stats_service.get_top_users(
            limit=limit,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return TopUsersResponse(
            users=users,
            period_start=period_start,
            period_end=period_end,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting top users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve top users",
        )


@router.get(
    "/admin/top-keys",
    response_model=TopKeysResponse,
    dependencies=[Depends(RequiresRole("admin"))],
)
async def get_top_api_keys_by_spend(
    limit: int = Query(10, ge=1, le=100, description="Number of top API keys"),
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d, or custom",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top API keys by total spend (admin only).

    Returns ranked list of API keys ordered by total cost.
    """
    try:
        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date required for custom period",
                )

        # Get top API keys
        stats_service = UsageStatsService(db)
        keys, period_start, period_end = await stats_service.get_top_api_keys(
            limit=limit,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return TopKeysResponse(
            keys=keys,
            period_start=period_start,
            period_end=period_end,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting top API keys: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve top API keys",
        )


@router.get(
    "/admin/by-provider",
    response_model=ProviderBreakdownResponse,
    dependencies=[Depends(RequiresRole("admin"))],
)
async def get_provider_breakdown(
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d, or custom",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed breakdown by provider (admin only).

    Returns aggregated statistics per provider including:
    - Total requests, tokens, and cost
    - Success/failure rates
    - Average latency
    - Top models per provider
    """
    try:
        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date required for custom period",
                )

        # Get provider breakdown
        stats_service = UsageStatsService(db)
        (
            providers,
            period_start,
            period_end,
            total_requests,
            total_cost,
        ) = await stats_service.get_provider_breakdown(
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return ProviderBreakdownResponse(
            providers=providers,
            period_start=period_start,
            period_end=period_end,
            total_requests=total_requests,
            total_cost_dollars=total_cost,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error getting provider breakdown: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider breakdown",
        )


@router.get(
    "/agents/{agent_config_id}/stats",
    response_model=UsageStatsResponse,
    dependencies=[Depends(RequiresRole("admin"))],
)
async def get_agent_usage_stats(
    agent_config_id: int,
    period: Optional[str] = Query(
        "30d",
        description="Time period: 7d, 30d, 90d",
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get usage statistics for a specific agent config (admin only).

    **Periods:**
    - `7d`: Last 7 days
    - `30d`: Last 30 days (default)
    - `90d`: Last 90 days
    """
    try:
        # Parse period
        period_days = 30
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        elif period == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date required for custom period",
                )

        # Get statistics - use agent_config_id as api_key_id for filtering
        stats_service = UsageStatsService(db)
        stats = await stats_service.get_agent_stats(
            agent_config_id=agent_config_id,
            period_days=period_days,
            start_date=start_date,
            end_date=end_date,
        )

        return stats

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error getting agent stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent statistics",
        )
