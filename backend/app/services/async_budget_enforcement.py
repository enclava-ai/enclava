"""
Async budget enforcement service for managing spending limits and cost control

This module provides async-native budget enforcement with a simple pattern:
1. Check if budget is exceeded before request
2. Make the LLM request
3. Record actual usage after request completes

This approach tracks real usage directly without complex reservation/reconciliation.
Small budget overages (by the cost of one request) are acceptable.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.api_key import APIKey
from app.models.budget import Budget
from app.services.alerts import get_alert_service
from app.services.cost_calculator import CostCalculator, estimate_request_cost
from app.services.metrics import get_metrics_service

logger = get_logger(__name__)


class AsyncBudgetEnforcementError(Exception):
    """Custom exception for budget enforcement failures"""

    pass


class AsyncBudgetExceededError(AsyncBudgetEnforcementError):
    """Exception raised when budget would be exceeded"""

    def __init__(self, message: str, budget: Budget):
        super().__init__(message)
        self.budget = budget


class AsyncBudgetEnforcementService:
    """Async service for enforcing budget limits and tracking usage.

    Uses a simple pattern:
    1. check_budget_compliance() - Check if budget already exceeded
    2. (make LLM request)
    3. record_usage() - Add actual cost to budget

    This tracks real usage directly. Small overages are acceptable.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_budget_compliance(
        self,
        api_key: APIKey,
        model_name: str,
        estimated_tokens: int,
        endpoint: str = None,
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """
        Check if a request complies with budget limits (non-atomic version)

        Args:
            api_key: API key making the request
            model_name: Model being used
            estimated_tokens: Estimated token usage
            endpoint: API endpoint being accessed

        Returns:
            Tuple of (is_allowed, error_message, warnings)
        """
        try:
            # Calculate estimated cost
            estimated_cost = estimate_request_cost(model_name, estimated_tokens)

            # Get applicable budgets
            budgets = await self._get_applicable_budgets(api_key, model_name, endpoint)

            if not budgets:
                logger.debug(f"No applicable budgets found for API key {api_key.id}")
                return True, None, []

            warnings = []

            # Check each budget
            for budget in budgets:
                # Reset budget if period expired and auto-renew is enabled
                if budget.is_expired() and budget.auto_renew:
                    await self._reset_expired_budget(budget)

                # Skip inactive or expired budgets
                if not budget.is_active or budget.is_expired():
                    continue

                # Check if request would exceed budget
                if not budget.can_spend(estimated_cost):
                    error_msg = (
                        f"Request would exceed budget '{budget.name}' "
                        f"(${budget.limit_cents/100:.2f}). "
                        f"Current usage: ${budget.current_usage_cents/100:.2f}, "
                        f"Requested: ${estimated_cost/100:.4f}, "
                        f"Remaining: ${(budget.limit_cents - budget.current_usage_cents)/100:.2f}"
                    )
                    logger.warning(
                        f"Budget exceeded for API key {api_key.id}: {error_msg}"
                    )
                    return False, error_msg, warnings

                # Check if request would trigger warning
                if (
                    budget.would_exceed_warning(estimated_cost)
                    and not budget.is_warning_sent
                ):
                    warning_msg = (
                        f"Budget '{budget.name}' approaching limit. "
                        f"Usage will be ${(budget.current_usage_cents + estimated_cost)/100:.2f} "
                        f"of ${budget.limit_cents/100:.2f} "
                        f"({((budget.current_usage_cents + estimated_cost) / budget.limit_cents * 100):.1f}%)"
                    )
                    warnings.append(
                        {
                            "type": "budget_warning",
                            "budget_id": budget.id,
                            "budget_name": budget.name,
                            "message": warning_msg,
                            "current_usage_cents": budget.current_usage_cents
                            + estimated_cost,
                            "limit_cents": budget.limit_cents,
                            "usage_percentage": (
                                budget.current_usage_cents + estimated_cost
                            )
                            / budget.limit_cents
                            * 100,
                        }
                    )
                    logger.info(
                        f"Budget warning for API key {api_key.id}: {warning_msg}"
                    )

            return True, None, warnings

        except Exception as e:
            logger.error(f"Error checking budget compliance: {e}")
            await self.db.rollback()
            # Allow request on error to avoid blocking legitimate usage
            return True, None, []

    async def record_usage(
        self,
        api_key: APIKey,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        endpoint: str = None,
    ) -> List[Budget]:
        """
        Record actual usage against applicable budgets

        Args:
            api_key: API key that made the request
            model_name: Model that was used
            input_tokens: Actual input tokens used
            output_tokens: Actual output tokens used
            endpoint: API endpoint that was accessed

        Returns:
            List of budgets that were updated
        """
        try:
            # Calculate actual cost
            actual_cost = CostCalculator.calculate_cost_cents(
                model_name, input_tokens, output_tokens
            )

            # Get applicable budgets
            budgets = await self._get_applicable_budgets(api_key, model_name, endpoint)

            updated_budgets = []

            for budget in budgets:
                if budget.is_active and budget.is_in_period():
                    # Add usage to budget
                    budget.add_usage(actual_cost)
                    updated_budgets.append(budget)

                    logger.debug(
                        f"Recorded usage for budget {budget.id}: "
                        f"${actual_cost/100:.4f} (total: ${budget.current_usage_cents/100:.2f})"
                    )

            # Commit changes
            await self.db.commit()

            return updated_budgets

        except Exception as e:
            logger.error(f"Error recording budget usage: {e}")
            await self.db.rollback()
            return []

    async def _get_applicable_budgets(
        self, api_key: APIKey, model_name: str = None, endpoint: str = None
    ) -> List[Budget]:
        """Get budgets that apply to the given request"""

        # Build query conditions
        conditions = [
            Budget.is_active == True,
            or_(
                and_(
                    Budget.user_id == api_key.user_id, Budget.api_key_id.is_(None)
                ),  # User budget
                Budget.api_key_id == api_key.id,  # API key specific budget
            ),
        ]

        # Query budgets
        stmt = select(Budget).where(and_(*conditions))
        result = await self.db.execute(stmt)
        budgets = result.scalars().all()

        # Filter budgets based on allowed models/endpoints
        applicable_budgets = []

        for budget in budgets:
            # Check model restrictions
            if model_name and budget.allowed_models:
                if model_name not in budget.allowed_models:
                    continue

            # Check endpoint restrictions
            if endpoint and budget.allowed_endpoints:
                if endpoint not in budget.allowed_endpoints:
                    continue

            applicable_budgets.append(budget)

        return applicable_budgets

    async def _reset_expired_budget(self, budget: Budget):
        """Reset an expired budget for the next period"""
        try:
            budget.reset_period()
            await self.db.commit()

            logger.info(
                f"Reset expired budget {budget.id} for new period: "
                f"{budget.period_start} to {budget.period_end}"
            )

        except Exception as e:
            logger.error(f"Error resetting expired budget {budget.id}: {e}")
            await self.db.rollback()

    async def get_budget_status(self, api_key: APIKey) -> Dict[str, Any]:
        """Get comprehensive budget status for an API key"""
        try:
            budgets = await self._get_applicable_budgets(api_key)

            status = {
                "total_budgets": len(budgets),
                "active_budgets": 0,
                "exceeded_budgets": 0,
                "warning_budgets": 0,
                "total_limit_cents": 0,
                "total_usage_cents": 0,
                "budgets": [],
            }

            for budget in budgets:
                if not budget.is_active:
                    continue

                budget_info = budget.to_dict()
                budget_info.update(
                    {
                        "is_expired": budget.is_expired(),
                        "days_remaining": budget.get_period_days_remaining(),
                        "daily_burn_rate": budget.get_daily_burn_rate(),
                        "projected_spend": budget.get_projected_spend(),
                    }
                )

                status["budgets"].append(budget_info)
                status["active_budgets"] += 1
                status["total_limit_cents"] += budget.limit_cents
                status["total_usage_cents"] += budget.current_usage_cents

                if budget.is_exceeded:
                    status["exceeded_budgets"] += 1
                elif (
                    budget.warning_threshold_cents
                    and budget.current_usage_cents >= budget.warning_threshold_cents
                ):
                    status["warning_budgets"] += 1

            # Calculate overall percentages
            if status["total_limit_cents"] > 0:
                status["overall_usage_percentage"] = (
                    status["total_usage_cents"] / status["total_limit_cents"]
                ) * 100
            else:
                status["overall_usage_percentage"] = 0

            status["total_limit_dollars"] = status["total_limit_cents"] / 100
            status["total_usage_dollars"] = status["total_usage_cents"] / 100
            status["total_remaining_cents"] = max(
                0, status["total_limit_cents"] - status["total_usage_cents"]
            )
            status["total_remaining_dollars"] = status["total_remaining_cents"] / 100

            return status

        except Exception as e:
            logger.error(f"Error getting budget status: {e}")
            return {
                "error": str(e),
                "total_budgets": 0,
                "active_budgets": 0,
                "exceeded_budgets": 0,
                "warning_budgets": 0,
                "budgets": [],
            }


# Convenience functions for async budget enforcement


async def async_check_budget_for_request(
    db: AsyncSession,
    api_key: APIKey,
    model_name: str,
    estimated_tokens: int,
    endpoint: str = None,
) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
    """Async convenience function to check budget compliance"""
    service = AsyncBudgetEnforcementService(db)
    return await service.check_budget_compliance(
        api_key, model_name, estimated_tokens, endpoint
    )


async def async_record_request_usage(
    db: AsyncSession,
    api_key: APIKey,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    endpoint: str = None,
) -> List[Budget]:
    """Async convenience function to record actual usage after request completes"""
    service = AsyncBudgetEnforcementService(db)
    return await service.record_usage(
        api_key, model_name, input_tokens, output_tokens, endpoint
    )
