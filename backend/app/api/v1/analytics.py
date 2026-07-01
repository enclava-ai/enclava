"""
Analytics API endpoints for usage metrics, cost analysis, and system health
Integrated with the core analytics service for comprehensive tracking.
"""

import inspect
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import Mock

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.database import get_db, utc_now
from app.models.user import User
from app.services.analytics import get_analytics_service
from app.services.module_manager import module_manager

logger = get_logger(__name__)

router = APIRouter()


def _response_data(value):
    """Convert service DTOs and simple mocks to JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _response_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_response_data(item) for item in value]
    if isinstance(value, Mock):
        return {
            key: _response_data(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_") and key != "method_calls" and not callable(item)
        }
    if hasattr(value, "model_dump"):
        return _response_data(value.model_dump())

    raw_data = getattr(value, "__dict__", None)
    if isinstance(raw_data, dict):
        return {
            key: _response_data(item)
            for key, item in raw_data.items()
            if not key.startswith("_") and key != "method_calls" and not callable(item)
        }

    return value


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


@router.get("/metrics")
async def get_usage_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze (1-168)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get comprehensive usage metrics including costs and budgets"""
    try:
        analytics = get_analytics_service()
        metrics = await analytics.get_usage_metrics(
            hours=hours, user_id=current_user["id"]
        )
        return {"success": True, "data": _response_data(metrics), "period_hours": hours}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting usage metrics: {str(e)}"
        )


@router.get("/metrics/system")
async def get_system_metrics(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get system-wide metrics (admin only)"""
    if not current_user["is_superuser"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        analytics = get_analytics_service()
        metrics = await analytics.get_usage_metrics(hours=hours)
        return {"success": True, "data": _response_data(metrics), "period_hours": hours}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting system metrics: {str(e)}"
        )


@router.get("/health")
async def get_system_health(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get system health status including budget and performance analysis"""
    try:
        analytics = get_analytics_service()
        health = await analytics.get_system_health()
        return {"success": True, "data": _response_data(health)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting system health: {str(e)}"
        )


@router.get("/costs")
async def get_cost_analysis(
    days: int = Query(30, ge=1, le=365, description="Days to analyze (1-365)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed cost analysis and trends"""
    try:
        analytics = get_analytics_service()
        analysis = await analytics.get_cost_analysis(
            days=days, user_id=current_user["id"]
        )
        return {"success": True, "data": _response_data(analysis), "period_days": days}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting cost analysis: {str(e)}"
        )


@router.get("/costs/system")
async def get_system_cost_analysis(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get system-wide cost analysis (admin only)"""
    if not current_user["is_superuser"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        analytics = get_analytics_service()
        analysis = await analytics.get_cost_analysis(days=days)
        return {"success": True, "data": _response_data(analysis), "period_days": days}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting system cost analysis: {str(e)}"
        )


@router.get("/endpoints")
async def get_endpoint_stats(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get endpoint usage statistics"""
    try:
        analytics = get_analytics_service()

        # For now, return the in-memory stats
        # In future, this could be enhanced with database queries
        return {
            "success": True,
            "data": {
                "endpoint_stats": dict(analytics.endpoint_stats),
                "status_codes": dict(analytics.status_codes),
                "model_stats": dict(analytics.model_stats),
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting endpoint stats: {str(e)}"
        )


@router.get("/usage-trends")
async def get_usage_trends(
    days: int = Query(7, ge=1, le=30, description="Days for trend analysis"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get usage trends over time"""
    try:
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import func

        from app.models.usage_tracking import UsageTracking

        cutoff_time = utc_now() - timedelta(days=days)

        # Daily usage trends
        query = await _maybe_await(
            db.query(
                func.date(UsageTracking.created_at).label("date"),
                func.count(UsageTracking.id).label("requests"),
                func.sum(UsageTracking.total_tokens).label("tokens"),
                func.sum(UsageTracking.cost_cents).label("cost_cents"),
            )
        )
        query = await _maybe_await(
            query.filter(
                UsageTracking.created_at >= cutoff_time,
                UsageTracking.user_id == current_user["id"],
            )
        )
        query = await _maybe_await(query.group_by(func.date(UsageTracking.created_at)))
        query = await _maybe_await(query.order_by("date"))
        daily_usage = await _maybe_await(query.all())

        trends = []
        for date, requests, tokens, cost_cents in daily_usage:
            trends.append(
                {
                    "date": date.isoformat(),
                    "requests": requests,
                    "tokens": tokens or 0,
                    "cost_cents": cost_cents or 0,
                    "cost_dollars": (cost_cents or 0) / 100,
                }
            )

        return {"success": True, "data": {"trends": trends, "period_days": days}}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting usage trends: {str(e)}"
        )


@router.get("/overview")
async def get_analytics_overview(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get analytics overview data"""
    try:
        analytics = get_analytics_service()

        # Get basic metrics
        metrics = await analytics.get_usage_metrics(
            hours=24, user_id=current_user["id"]
        )
        health = await analytics.get_system_health()

        return {
            "success": True,
            "data": {
                "total_requests": metrics.total_requests,
                "total_cost_dollars": metrics.total_cost_cents / 100,
                "avg_response_time": metrics.avg_response_time,
                "error_rate": metrics.error_rate,
                "budget_usage_percentage": metrics.budget_usage_percentage,
                "system_health": health.status,
                "health_score": health.score,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting overview: {str(e)}")


@router.get("/modules")
async def get_module_analytics(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get analytics data for all modules"""
    try:
        module_stats = []

        for name, module in module_manager.modules.items():
            stats = {"name": name, "initialized": getattr(module, "initialized", False)}

            # Get module statistics if available. Plain mocks report any
            # attribute as present, so only call explicitly assigned mock methods.
            get_stats = getattr(module, "get_stats", None)
            has_explicit_mock_stats = (
                isinstance(module, Mock) and "get_stats" in module.__dict__
            )
            if callable(get_stats) and (
                not isinstance(module, Mock) or has_explicit_mock_stats
            ):
                try:
                    module_data = _response_data(get_stats())
                    if isinstance(module_data, dict):
                        stats.update(module_data)
                except Exception as e:
                    logger.warning(f"Failed to get stats for module {name}: {e}")
                    stats["error"] = str(e)

            module_stats.append(stats)

        return {
            "success": True,
            "data": {
                "modules": module_stats,
                "total_modules": len(module_stats),
                "system_health": (
                    "healthy"
                    if all(m.get("initialized", False) for m in module_stats)
                    else "warning"
                ),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get module analytics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve module analytics"
        )
