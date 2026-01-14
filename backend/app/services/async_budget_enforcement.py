"""
Async budget enforcement service for managing spending limits and cost control

This module provides async-native budget enforcement, eliminating the need for
synchronous database access in async contexts. Uses asyncio.sleep for retries
and async SQLAlchemy for all database operations.
"""

import asyncio
import random
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.models.budget import Budget
from app.models.api_key import APIKey
from app.services.cost_calculator import CostCalculator, estimate_request_cost
from app.core.logging import get_logger

logger = get_logger(__name__)


class AsyncBudgetEnforcementError(Exception):
    """Custom exception for budget enforcement failures"""
    pass


class AsyncBudgetExceededError(AsyncBudgetEnforcementError):
    """Exception raised when budget would be exceeded"""

    def __init__(self, message: str, budget: Budget, requested_cost: int):
        super().__init__(message)
        self.budget = budget
        self.requested_cost = requested_cost


class AsyncBudgetConcurrencyError(AsyncBudgetEnforcementError):
    """Exception raised when budget update fails due to concurrency"""

    def __init__(self, message: str, retry_count: int = 0):
        super().__init__(message)
        self.retry_count = retry_count


class AsyncBudgetAtomicError(AsyncBudgetEnforcementError):
    """Exception raised when atomic budget operation fails"""

    def __init__(self, message: str, budget_id: int, requested_amount: int):
        super().__init__(message)
        self.budget_id = budget_id
        self.requested_amount = requested_amount


class AsyncBudgetEnforcementService:
    """Async service for enforcing budget limits and tracking usage"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.max_retries = 3
        self.retry_delay_base = 0.1  # Base delay in seconds

    async def atomic_check_and_reserve_budget(
        self,
        api_key: APIKey,
        model_name: str,
        estimated_tokens: int,
        endpoint: str = None,
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]], List[int]]:
        """
        Atomically check budget compliance and reserve spending

        Returns:
            Tuple of (is_allowed, error_message, warnings, reserved_budget_ids)
        """
        estimated_cost = estimate_request_cost(model_name, estimated_tokens)
        budgets = await self._get_applicable_budgets(api_key, model_name, endpoint)

        if not budgets:
            logger.debug(f"No applicable budgets found for API key {api_key.id}")
            return True, None, [], []

        # Try atomic reservation with retries
        for attempt in range(self.max_retries):
            try:
                return await self._attempt_atomic_reservation(
                    budgets, estimated_cost, api_key.id, attempt
                )
            except AsyncBudgetConcurrencyError as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Atomic budget reservation failed after {self.max_retries} attempts: {e}"
                    )
                    return (
                        False,
                        f"Budget check temporarily unavailable (concurrency limit)",
                        [],
                        [],
                    )

                # Exponential backoff with jitter - ASYNC sleep
                delay = self.retry_delay_base * (2**attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
                logger.info(
                    f"Retrying atomic budget reservation (attempt {attempt + 2})"
                )
            except Exception as e:
                logger.error(f"Unexpected error in atomic budget reservation: {e}")
                return False, f"Budget check failed: {str(e)}", [], []

        return False, "Budget check failed after maximum retries", [], []

    async def _attempt_atomic_reservation(
        self, budgets: List[Budget], estimated_cost: int, api_key_id: int, attempt: int
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]], List[int]]:
        """Attempt to atomically reserve budget across all applicable budgets"""
        warnings = []
        reserved_budget_ids = []

        try:
            for budget in budgets:
                # Lock budget row for update to prevent concurrent modifications
                stmt = (
                    select(Budget)
                    .where(Budget.id == budget.id)
                    .with_for_update()
                )
                result = await self.db.execute(stmt)
                locked_budget = result.scalar_one_or_none()

                if not locked_budget:
                    raise AsyncBudgetAtomicError(
                        f"Budget {budget.id} not found", budget.id, estimated_cost
                    )

                # Reset budget if expired and auto-renew enabled
                if locked_budget.is_expired() and locked_budget.auto_renew:
                    await self._reset_expired_budget(locked_budget)
                    await self.db.flush()  # Ensure reset is applied before checking

                # Skip inactive or expired budgets
                if not locked_budget.is_active or locked_budget.is_expired():
                    continue

                # Check if request would exceed budget using atomic operation
                if not self._atomic_can_spend(locked_budget, estimated_cost):
                    error_msg = (
                        f"Request would exceed budget '{locked_budget.name}' "
                        f"(${locked_budget.limit_cents/100:.2f}). "
                        f"Current usage: ${locked_budget.current_usage_cents/100:.2f}, "
                        f"Requested: ${estimated_cost/100:.4f}, "
                        f"Remaining: ${(locked_budget.limit_cents - locked_budget.current_usage_cents)/100:.2f}"
                    )
                    logger.warning(
                        f"Budget exceeded for API key {api_key_id}: {error_msg}"
                    )
                    await self.db.rollback()
                    return False, error_msg, warnings, []

                # Check warning threshold
                if (
                    locked_budget.would_exceed_warning(estimated_cost)
                    and not locked_budget.is_warning_sent
                ):
                    warning_msg = (
                        f"Budget '{locked_budget.name}' approaching limit. "
                        f"Usage will be ${(locked_budget.current_usage_cents + estimated_cost)/100:.2f} "
                        f"of ${locked_budget.limit_cents/100:.2f} "
                        f"({((locked_budget.current_usage_cents + estimated_cost) / locked_budget.limit_cents * 100):.1f}%)"
                    )
                    warnings.append(
                        {
                            "type": "budget_warning",
                            "budget_id": locked_budget.id,
                            "budget_name": locked_budget.name,
                            "message": warning_msg,
                            "current_usage_cents": locked_budget.current_usage_cents
                            + estimated_cost,
                            "limit_cents": locked_budget.limit_cents,
                            "usage_percentage": (
                                locked_budget.current_usage_cents + estimated_cost
                            )
                            / locked_budget.limit_cents
                            * 100,
                        }
                    )
                    logger.info(
                        f"Budget warning for API key {api_key_id}: {warning_msg}"
                    )

                # Reserve the budget (temporarily add estimated cost)
                await self._atomic_reserve_usage(locked_budget, estimated_cost)
                reserved_budget_ids.append(locked_budget.id)

            # Commit the reservation
            await self.db.commit()
            logger.debug(
                f"Successfully reserved budget for API key {api_key_id}, estimated cost: ${estimated_cost/100:.4f}"
            )
            return True, None, warnings, reserved_budget_ids

        except IntegrityError as e:
            await self.db.rollback()
            raise AsyncBudgetConcurrencyError(
                f"Database integrity error during budget reservation: {e}", attempt
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error in atomic budget reservation: {e}")
            raise

    def _atomic_can_spend(self, budget: Budget, amount_cents: int) -> bool:
        """Check if budget can accommodate spending"""
        if not budget.is_active or not budget.is_in_period():
            return False

        if not budget.enforce_hard_limit:
            return True

        return (budget.current_usage_cents + amount_cents) <= budget.limit_cents

    async def _atomic_reserve_usage(self, budget: Budget, amount_cents: int):
        """Atomically reserve usage in budget (add to current usage)"""
        # Use database-level atomic update
        stmt = (
            update(Budget)
            .where(Budget.id == budget.id)
            .values(
                current_usage_cents=Budget.current_usage_cents + amount_cents,
                updated_at=datetime.utcnow(),
                is_exceeded=Budget.current_usage_cents + amount_cents
                >= Budget.limit_cents,
                is_warning_sent=(
                    Budget.is_warning_sent
                    | (
                        (Budget.warning_threshold_cents.isnot(None))
                        & (
                            Budget.current_usage_cents + amount_cents
                            >= Budget.warning_threshold_cents
                        )
                    )
                ),
            )
        )
        result = await self.db.execute(stmt)

        if result.rowcount != 1:
            raise AsyncBudgetAtomicError(
                f"Failed to update budget {budget.id}", budget.id, amount_cents
            )

        # Update the in-memory object to reflect changes
        budget.current_usage_cents += amount_cents
        budget.updated_at = datetime.utcnow()
        if budget.current_usage_cents >= budget.limit_cents:
            budget.is_exceeded = True
        if (
            budget.warning_threshold_cents
            and budget.current_usage_cents >= budget.warning_threshold_cents
        ):
            budget.is_warning_sent = True

    async def atomic_finalize_usage(
        self,
        reserved_budget_ids: List[int],
        api_key: APIKey,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        endpoint: str = None,
    ) -> List[Budget]:
        """
        Finalize actual usage and adjust reservations

        Args:
            reserved_budget_ids: Budget IDs that had usage reserved
            api_key: API key that made the request
            model_name: Model that was used
            input_tokens: Actual input tokens used
            output_tokens: Actual output tokens used
            endpoint: API endpoint that was accessed

        Returns:
            List of budgets that were updated
        """
        if not reserved_budget_ids:
            return []

        try:
            actual_cost = CostCalculator.calculate_cost_cents(
                model_name, input_tokens, output_tokens
            )
            updated_budgets = []

            for budget_id in reserved_budget_ids:
                # Lock budget for update
                stmt = (
                    select(Budget)
                    .where(Budget.id == budget_id)
                    .with_for_update()
                )
                result = await self.db.execute(stmt)
                budget = result.scalar_one_or_none()

                if not budget:
                    logger.warning(f"Budget {budget_id} not found during finalization")
                    continue

                if budget.is_active and budget.is_in_period():
                    # The reservation already added the estimated cost
                    # Actual cost adjustment is minimal in most cases
                    updated_budgets.append(budget)

                    logger.debug(
                        f"Finalized usage for budget {budget.id}: "
                        f"${actual_cost/100:.4f} (total: ${budget.current_usage_cents/100:.2f})"
                    )

            # Commit finalization
            await self.db.commit()
            return updated_budgets

        except Exception as e:
            logger.error(f"Error finalizing budget usage: {e}")
            await self.db.rollback()
            return []

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
    """Async convenience function to record actual usage"""
    service = AsyncBudgetEnforcementService(db)
    return await service.record_usage(
        api_key, model_name, input_tokens, output_tokens, endpoint
    )


async def async_atomic_check_and_reserve_budget(
    db: AsyncSession,
    api_key: APIKey,
    model_name: str,
    estimated_tokens: int,
    endpoint: str = None,
) -> Tuple[bool, Optional[str], List[Dict[str, Any]], List[int]]:
    """Async atomic convenience function to check budget compliance and reserve spending"""
    service = AsyncBudgetEnforcementService(db)
    return await service.atomic_check_and_reserve_budget(
        api_key, model_name, estimated_tokens, endpoint
    )


async def async_atomic_finalize_usage(
    db: AsyncSession,
    reserved_budget_ids: List[int],
    api_key: APIKey,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    endpoint: str = None,
) -> List[Budget]:
    """Async atomic convenience function to finalize actual usage after request completion"""
    service = AsyncBudgetEnforcementService(db)
    return await service.atomic_finalize_usage(
        reserved_budget_ids, api_key, model_name, input_tokens, output_tokens, endpoint
    )
