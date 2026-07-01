"""
Usage Statistics Service

Service for aggregating and querying usage statistics from usage_records.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import utc_now
from app.models.agent_config import AgentConfig
from app.models.api_key import APIKey
from app.models.usage_record import UsageRecord
from app.models.user import User

logger = get_logger(__name__)


class UsageStatsService:
    """Service for querying and aggregating usage statistics."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the usage stats service.

        Args:
            db: Database session
        """
        self.db = db

    def _get_date_range(
        self,
        period_days: int,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> tuple[datetime, datetime]:
        """
        Get date range for queries, ensuring naive datetimes for DB compatibility.

        Args:
            period_days: Number of days to query if no dates provided
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Tuple of (start_date, end_date) as naive datetimes
        """
        if end_date is None:
            end_date = utc_now()
        elif end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        if start_date is None:
            start_date = end_date - timedelta(days=period_days)
        elif start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)

        return start_date, end_date

    async def get_user_stats(
        self,
        user_id: int,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a specific user.

        Args:
            user_id: User ID
            period_days: Number of days to query (if start_date/end_date not provided)
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Dictionary with summary, by_provider, by_model, by_source, and daily_trend
        """
        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Build base query - filter by user_id
        base_conditions = [
            UsageRecord.user_id == user_id,
            UsageRecord.created_at >= start_date,
            UsageRecord.created_at <= end_date,
        ]

        # Get summary
        summary = await self._get_summary(base_conditions)

        # Get provider breakdown
        by_provider = await self._get_provider_breakdown(base_conditions)

        # Get model breakdown
        by_model = await self._get_model_breakdown(base_conditions)

        # Get daily trend
        daily_trend = await self._get_daily_trend(base_conditions, start_date, end_date)

        # Get breakdown by source (agents, API keys, playground)
        by_source = await self._get_source_breakdown(base_conditions)

        return {
            "summary": summary,
            "by_provider": by_provider,
            "by_model": by_model,
            "by_source": by_source,
            "daily_trend": daily_trend,
        }

    async def get_user_records(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 50,
        provider_filter: Optional[str] = None,
        model_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[UsageRecord], int]:
        """
        Get paginated usage records for a user (all sources).

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            page_size: Records per page
            provider_filter: Filter by provider
            model_filter: Filter by model
            status_filter: Filter by status (success/error)
            source_filter: Filter by source (agent/api_key/playground)
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Tuple of (records, total_count)
        """
        # Build conditions
        conditions = [UsageRecord.user_id == user_id]

        if provider_filter:
            conditions.append(UsageRecord.provider_id == provider_filter)
        if model_filter:
            conditions.append(UsageRecord.normalized_model == model_filter)
        if status_filter:
            conditions.append(UsageRecord.status == status_filter)
        if start_date:
            conditions.append(UsageRecord.created_at >= start_date)
        if end_date:
            conditions.append(UsageRecord.created_at <= end_date)

        # Source filter
        if source_filter == "api_key":
            conditions.append(UsageRecord.api_key_id.is_not(None))
            conditions.append(UsageRecord.agent_config_id.is_(None))
        elif source_filter == "agent":
            conditions.append(UsageRecord.agent_config_id.is_not(None))
        elif source_filter == "playground":
            conditions.append(UsageRecord.api_key_id.is_(None))
            conditions.append(UsageRecord.agent_config_id.is_(None))

        # Get total count
        count_stmt = select(func.count(UsageRecord.id)).where(and_(*conditions))
        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar() or 0

        # Get paginated records
        offset = (page - 1) * page_size
        records_stmt = (
            select(UsageRecord)
            .where(and_(*conditions))
            .order_by(desc(UsageRecord.created_at))
            .limit(page_size)
            .offset(offset)
        )
        records_result = await self.db.execute(records_stmt)
        records = records_result.scalars().all()

        return records, total_count

    async def _get_source_breakdown(self, conditions: List) -> List[Dict[str, Any]]:
        """Get breakdown by usage source (Agent, API Key, Playground).

        Source classification:
        - Agents: agent_config_id IS NOT NULL
        - API Keys: api_key_id IS NOT NULL and agent_config_id IS NULL
        - Playground: api_key_id IS NULL and agent_config_id IS NULL
        """
        sources = []

        agent_conditions = conditions + [
            UsageRecord.agent_config_id.is_not(None),
        ]
        agent_stats = await self._get_summary(agent_conditions)
        sources.append(
            {
                "source": "agent",
                "source_name": "Agents",
                "total_requests": agent_stats["total_requests"],
                "total_tokens": agent_stats["total_tokens"],
                "total_cost_dollars": agent_stats["total_cost_dollars"],
            }
        )

        # API Key usage (api_key_id IS NOT NULL)
        api_key_conditions = conditions + [
            UsageRecord.api_key_id.is_not(None),
            UsageRecord.agent_config_id.is_(None),
        ]
        api_key_stats = await self._get_summary(api_key_conditions)
        sources.append(
            {
                "source": "api_key",
                "source_name": "API Keys",
                "total_requests": api_key_stats["total_requests"],
                "total_tokens": api_key_stats["total_tokens"],
                "total_cost_dollars": api_key_stats["total_cost_dollars"],
            }
        )

        # Playground usage (api_key_id IS NULL AND agent_config_id IS NULL)
        playground_conditions = conditions + [
            UsageRecord.api_key_id.is_(None),
            UsageRecord.agent_config_id.is_(None),
        ]
        playground_stats = await self._get_summary(playground_conditions)
        sources.append(
            {
                "source": "playground",
                "source_name": "Playground",
                "total_requests": playground_stats["total_requests"],
                "total_tokens": playground_stats["total_tokens"],
                "total_cost_dollars": playground_stats["total_cost_dollars"],
            }
        )

        return [s for s in sources if s["total_requests"] > 0]

    async def get_api_key_stats(
        self,
        api_key_id: int,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a specific API key.

        Args:
            api_key_id: API key ID
            period_days: Number of days to query (if start_date/end_date not provided)
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Dictionary with summary, by_provider, by_model, and daily_trend
        """
        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Build base query
        base_conditions = [
            UsageRecord.api_key_id == api_key_id,
            UsageRecord.created_at >= start_date,
            UsageRecord.created_at <= end_date,
        ]

        # Get summary
        summary = await self._get_summary(base_conditions)

        # Get provider breakdown
        by_provider = await self._get_provider_breakdown(base_conditions)

        # Get model breakdown
        by_model = await self._get_model_breakdown(base_conditions)

        # Get daily trend
        daily_trend = await self._get_daily_trend(base_conditions, start_date, end_date)

        return {
            "summary": summary,
            "by_provider": by_provider,
            "by_model": by_model,
            "daily_trend": daily_trend,
        }

    async def get_api_key_records(
        self,
        api_key_id: int,
        page: int = 1,
        page_size: int = 50,
        provider_filter: Optional[str] = None,
        model_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[UsageRecord], int]:
        """
        Get paginated usage records for an API key.

        Args:
            api_key_id: API key ID
            page: Page number (1-indexed)
            page_size: Records per page
            provider_filter: Filter by provider
            model_filter: Filter by model
            status_filter: Filter by status (success/error)
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Tuple of (records, total_count)
        """
        # Build conditions
        conditions = [UsageRecord.api_key_id == api_key_id]

        if provider_filter:
            conditions.append(UsageRecord.provider_id == provider_filter)
        if model_filter:
            conditions.append(UsageRecord.normalized_model == model_filter)
        if status_filter:
            conditions.append(UsageRecord.status == status_filter)
        if start_date:
            conditions.append(UsageRecord.created_at >= start_date)
        if end_date:
            conditions.append(UsageRecord.created_at <= end_date)

        # Get total count
        count_stmt = select(func.count(UsageRecord.id)).where(and_(*conditions))
        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar() or 0

        # Get paginated records
        offset = (page - 1) * page_size
        records_stmt = (
            select(UsageRecord)
            .where(and_(*conditions))
            .order_by(desc(UsageRecord.created_at))
            .limit(page_size)
            .offset(offset)
        )
        records_result = await self.db.execute(records_stmt)
        records = records_result.scalars().all()

        return records, total_count

    async def get_system_overview(
        self,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get system-wide usage overview.

        Args:
            period_days: Number of days to query
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Dictionary with system-wide statistics
        """
        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Build base query (no API key filter for system-wide)
        base_conditions = [
            UsageRecord.created_at >= start_date,
            UsageRecord.created_at <= end_date,
        ]

        # Get summary
        summary = await self._get_summary(base_conditions)

        # Get provider breakdown
        by_provider = await self._get_provider_breakdown(base_conditions)

        # Get top models (limit to 10)
        top_models = await self._get_model_breakdown(base_conditions, limit=10)

        # Get daily trend
        daily_trend = await self._get_daily_trend(base_conditions, start_date, end_date)

        return {
            "summary": summary,
            "by_provider": by_provider,
            "top_models": top_models,
            "daily_trend": daily_trend,
            "period_start": start_date,
            "period_end": end_date,
        }

    async def get_top_users(
        self,
        limit: int = 10,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], datetime, datetime]:
        """
        Get top users by total spend.

        Args:
            limit: Number of top users to return
            period_days: Number of days to query
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Tuple of (users_list, period_start, period_end)
        """
        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Query top users by total cost
        stmt = (
            select(
                UsageRecord.user_id,
                func.count(UsageRecord.id).label("total_requests"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                func.sum(UsageRecord.total_cost_cents).label("total_cost_cents"),
            )
            .where(
                and_(
                    UsageRecord.created_at >= start_date,
                    UsageRecord.created_at <= end_date,
                    UsageRecord.status == "success",
                )
            )
            .group_by(UsageRecord.user_id)
            .order_by(desc("total_cost_cents"))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        user_stats = result.all()

        # Fetch user details
        users = []
        for stat in user_stats:
            # Get user info
            user_stmt = select(User).where(User.id == stat.user_id)
            user_result = await self.db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            # Count API keys for this user
            api_key_count_stmt = select(func.count(APIKey.id)).where(
                APIKey.user_id == stat.user_id
            )
            api_key_count_result = await self.db.execute(api_key_count_stmt)
            api_key_count = api_key_count_result.scalar() or 0

            users.append(
                {
                    "user_id": stat.user_id,
                    "username": user.username if user else None,
                    "email": user.email if user else None,
                    "total_requests": stat.total_requests,
                    "total_tokens": stat.total_tokens or 0,
                    "total_cost_dollars": (stat.total_cost_cents or 0) / 100,
                    "api_key_count": api_key_count,
                }
            )

        return users, start_date, end_date

    async def get_top_api_keys(
        self,
        limit: int = 10,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], datetime, datetime]:
        """
        Get top API keys by total spend.

        Args:
            limit: Number of top keys to return
            period_days: Number of days to query
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Tuple of (keys_list, period_start, period_end)
        """
        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Query top API keys by total cost
        stmt = (
            select(
                UsageRecord.api_key_id,
                func.count(UsageRecord.id).label("total_requests"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                func.sum(UsageRecord.total_cost_cents).label("total_cost_cents"),
            )
            .where(
                and_(
                    UsageRecord.api_key_id.is_not(None),
                    UsageRecord.created_at >= start_date,
                    UsageRecord.created_at <= end_date,
                    UsageRecord.status == "success",
                )
            )
            .group_by(UsageRecord.api_key_id)
            .order_by(desc("total_cost_cents"))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        key_stats = result.all()

        # Fetch API key details
        keys = []
        for stat in key_stats:
            # Get API key info
            key_stmt = select(APIKey).where(APIKey.id == stat.api_key_id)
            key_result = await self.db.execute(key_stmt)
            api_key = key_result.scalar_one_or_none()

            if api_key:
                keys.append(
                    {
                        "api_key_id": stat.api_key_id,
                        "api_key_name": api_key.name,
                        "key_prefix": api_key.key_prefix,
                        "user_id": api_key.user_id,
                        "total_requests": stat.total_requests,
                        "total_tokens": stat.total_tokens or 0,
                        "total_cost_dollars": (stat.total_cost_cents or 0) / 100,
                    }
                )

        return keys, start_date, end_date

    async def get_provider_breakdown(
        self,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], datetime, datetime, int, float]:
        """
        Get detailed breakdown by provider.

        Args:
            period_days: Number of days to query
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Tuple of (providers, period_start, period_end, total_requests, total_cost)
        """
        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Query provider stats
        stmt = (
            select(
                UsageRecord.provider_id,
                func.count(UsageRecord.id).label("total_requests"),
                func.sum(case((UsageRecord.status == "success", 1), else_=0)).label(
                    "successful_requests"
                ),
                func.sum(case((UsageRecord.status != "success", 1), else_=0)).label(
                    "failed_requests"
                ),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
                func.sum(UsageRecord.total_cost_cents).label("total_cost_cents"),
                func.avg(UsageRecord.latency_ms).label("average_latency_ms"),
            )
            .where(
                and_(
                    UsageRecord.created_at >= start_date,
                    UsageRecord.created_at <= end_date,
                )
            )
            .group_by(UsageRecord.provider_id)
            .order_by(desc("total_cost_cents"))
        )

        result = await self.db.execute(stmt)
        provider_stats = result.all()

        # Build detailed provider stats
        providers = []
        total_requests_all = 0
        total_cost_all = 0

        for stat in provider_stats:
            total_requests = stat.total_requests
            successful = stat.successful_requests or 0
            failed = stat.failed_requests or 0
            error_rate = (failed / total_requests * 100) if total_requests > 0 else 0
            avg_tokens = (
                (stat.total_tokens or 0) / total_requests if total_requests > 0 else 0
            )
            cost_dollars = (stat.total_cost_cents or 0) / 100

            # Get top models for this provider
            top_models_stmt = (
                select(
                    UsageRecord.normalized_model,
                    func.count(UsageRecord.id).label("requests"),
                    func.sum(UsageRecord.total_tokens).label("tokens"),
                    func.sum(UsageRecord.total_cost_cents).label("cost_cents"),
                )
                .where(
                    and_(
                        UsageRecord.provider_id == stat.provider_id,
                        UsageRecord.created_at >= start_date,
                        UsageRecord.created_at <= end_date,
                        UsageRecord.status == "success",
                    )
                )
                .group_by(UsageRecord.normalized_model)
                .order_by(desc("cost_cents"))
                .limit(5)
            )

            top_models_result = await self.db.execute(top_models_stmt)
            top_models_data = top_models_result.all()

            top_models = [
                {
                    "model": m.normalized_model,
                    "provider_id": stat.provider_id,
                    "requests": m.requests,
                    "tokens": m.tokens or 0,
                    "cost_dollars": (m.cost_cents or 0) / 100,
                }
                for m in top_models_data
            ]

            providers.append(
                {
                    "provider_id": stat.provider_id,
                    "provider_name": stat.provider_id.capitalize(),
                    "total_requests": total_requests,
                    "successful_requests": successful,
                    "failed_requests": failed,
                    "error_rate_percent": error_rate,
                    "total_tokens": stat.total_tokens or 0,
                    "total_cost_dollars": cost_dollars,
                    "average_latency_ms": stat.average_latency_ms,
                    "average_tokens_per_request": avg_tokens,
                    "top_models": top_models,
                }
            )

            total_requests_all += total_requests
            total_cost_all += cost_dollars

        return providers, start_date, end_date, total_requests_all, total_cost_all

    # Internal helper methods

    async def _get_summary(self, conditions: List) -> Dict[str, Any]:
        """Get summary statistics for given conditions."""
        stmt = select(
            func.count(UsageRecord.id).label("total_requests"),
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.total_cost_cents).label("total_cost_cents"),
            func.sum(case((UsageRecord.status == "success", 1), else_=0)).label(
                "successful"
            ),
            func.sum(case((UsageRecord.status != "success", 1), else_=0)).label(
                "failed"
            ),
        ).where(and_(*conditions))

        result = await self.db.execute(stmt)
        stat = result.one()

        total_requests = stat.total_requests or 0
        successful = stat.successful or 0
        failed = stat.failed or 0
        error_rate = (failed / total_requests * 100) if total_requests > 0 else 0

        return {
            "total_requests": total_requests,
            "total_tokens": stat.total_tokens or 0,
            "total_cost_dollars": (stat.total_cost_cents or 0) / 100,
            "error_rate_percent": error_rate,
            "successful_requests": successful,
            "failed_requests": failed,
        }

    async def _get_provider_breakdown(self, conditions: List) -> List[Dict[str, Any]]:
        """Get breakdown by provider for given conditions."""
        stmt = (
            select(
                UsageRecord.provider_id,
                func.count(UsageRecord.id).label("requests"),
                func.sum(UsageRecord.total_tokens).label("tokens"),
                func.sum(UsageRecord.total_cost_cents).label("cost_cents"),
            )
            .where(and_(*conditions, UsageRecord.status == "success"))
            .group_by(UsageRecord.provider_id)
            .order_by(desc("cost_cents"))
        )

        result = await self.db.execute(stmt)
        providers = result.all()

        return [
            {
                "provider_id": p.provider_id,
                "provider_name": p.provider_id.capitalize(),
                "requests": p.requests,
                "tokens": p.tokens or 0,
                "cost_dollars": (p.cost_cents or 0) / 100,
            }
            for p in providers
        ]

    async def _get_model_breakdown(
        self, conditions: List, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get breakdown by model for given conditions."""
        stmt = (
            select(
                UsageRecord.normalized_model,
                UsageRecord.provider_id,
                func.count(UsageRecord.id).label("requests"),
                func.sum(UsageRecord.total_tokens).label("tokens"),
                func.sum(UsageRecord.total_cost_cents).label("cost_cents"),
            )
            .where(and_(*conditions, UsageRecord.status == "success"))
            .group_by(UsageRecord.normalized_model, UsageRecord.provider_id)
            .order_by(desc("cost_cents"))
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        models = result.all()

        return [
            {
                "model": m.normalized_model,
                "provider_id": m.provider_id,
                "requests": m.requests,
                "tokens": m.tokens or 0,
                "cost_dollars": (m.cost_cents or 0) / 100,
            }
            for m in models
        ]

    async def _get_daily_trend(
        self, conditions: List, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get daily usage trend for given conditions."""
        stmt = (
            select(
                func.date(UsageRecord.created_at).label("date"),
                func.count(UsageRecord.id).label("requests"),
                func.sum(UsageRecord.total_tokens).label("tokens"),
                func.sum(UsageRecord.total_cost_cents).label("cost_cents"),
            )
            .where(and_(*conditions, UsageRecord.status == "success"))
            .group_by(func.date(UsageRecord.created_at))
            .order_by(func.date(UsageRecord.created_at))
        )

        result = await self.db.execute(stmt)
        daily = result.all()

        return [
            {
                "date": d.date.strftime("%Y-%m-%d"),
                "requests": d.requests,
                "tokens": d.tokens or 0,
                "cost_dollars": (d.cost_cents or 0) / 100,
            }
            for d in daily
        ]

    async def get_agent_stats(
        self,
        agent_config_id: int,
        period_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a specific agent config.

        Args:
            agent_config_id: Agent config identifier (used as api_key_id for filtering)
            period_days: Number of days to query
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            Dictionary with summary, by_provider, by_model, and daily_trend
        """
        # Verify agent config exists
        result = await self.db.execute(
            select(AgentConfig).where(AgentConfig.id == agent_config_id)
        )
        agent_config = result.scalar_one_or_none()

        if not agent_config:
            raise ValueError(f"Agent config not found: {agent_config_id}")

        # Determine date range (naive datetimes for DB compatibility)
        start_date, end_date = self._get_date_range(period_days, start_date, end_date)

        # Build base query conditions
        base_conditions = [
            UsageRecord.agent_config_id == agent_config_id,
            UsageRecord.created_at >= start_date,
            UsageRecord.created_at <= end_date,
        ]

        # Get summary
        summary = await self._get_summary(base_conditions)

        # Get provider breakdown
        by_provider = await self._get_provider_breakdown(base_conditions)

        # Get model breakdown
        by_model = await self._get_model_breakdown(base_conditions)

        # Get daily trend
        daily_trend = await self._get_daily_trend(base_conditions, start_date, end_date)

        return {
            "summary": summary,
            "by_provider": by_provider,
            "by_model": by_model,
            "daily_trend": daily_trend,
            "agent_config_id": agent_config_id,
        }


# Convenience function
def get_usage_stats_service(db: AsyncSession) -> UsageStatsService:
    """
    Factory function to create UsageStatsService.

    Args:
        db: Database session

    Returns:
        UsageStatsService instance
    """
    return UsageStatsService(db)
