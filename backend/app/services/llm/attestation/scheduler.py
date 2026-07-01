"""
Attestation Scheduler

Periodically verifies provider attestations and maintains health state.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .base import BaseAttestationVerifier
from .models import AttestationResult, ProviderHealth

logger = logging.getLogger(__name__)


class AttestationScheduler:
    """
    Periodically verifies provider attestations.
    Marks providers unhealthy on failure, healthy on success.

    This is the core component that maintains the health state of all
    registered providers by running periodic attestation checks.
    """

    def __init__(self, verification_interval_seconds: int = 300):
        """
        Initialize attestation scheduler.

        Args:
            verification_interval_seconds: Time between verification checks (default: 5 minutes)
        """
        self.verification_interval = verification_interval_seconds
        self._provider_health: Dict[str, ProviderHealth] = {}
        self._verifiers: Dict[str, Tuple[BaseAttestationVerifier, str]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info(
            f"Initialized attestation scheduler with {verification_interval_seconds}s interval"
        )

    async def start(self):
        """Start the periodic verification loop."""
        if self._running:
            logger.warning("Attestation scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._verification_loop())
        logger.info("Attestation scheduler started")

    async def stop(self):
        """Stop the verification loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("Verification task cancelled successfully")

        logger.info("Attestation scheduler stopped")

    def register_provider(
        self, provider_id: str, verifier: BaseAttestationVerifier, test_model: str
    ):
        """
        Register a provider for periodic verification.

        Args:
            provider_id: Unique provider identifier
            verifier: Attestation verifier instance for this provider
            test_model: Model to use for verification checks
        """
        self._verifiers[provider_id] = (verifier, test_model)
        self._provider_health[provider_id] = ProviderHealth(
            provider_id=provider_id,
            healthy=False,  # Start unhealthy until first check passes
            error="Awaiting initial verification",
        )
        logger.info(f"Registered provider '{provider_id}' for attestation monitoring")

    def get_health(self, provider_id: str) -> Optional[ProviderHealth]:
        """
        Get current health status for a provider.

        Args:
            provider_id: Provider identifier

        Returns:
            ProviderHealth object or None if provider not registered
        """
        return self._provider_health.get(provider_id)

    def is_healthy(self, provider_id: str) -> bool:
        """
        Check if provider is healthy.

        Args:
            provider_id: Provider identifier

        Returns:
            True if provider is healthy and available
        """
        health = self._provider_health.get(provider_id)
        return health.healthy if health else False

    async def _verification_loop(self):
        """
        Main verification loop.

        Runs continuously while scheduler is active, sleeping between verification rounds.
        """
        logger.debug("Starting verification loop")
        while self._running:
            try:
                await self._verify_all_providers()
            except Exception as e:
                logger.error(f"Error in verification loop: {e}", exc_info=True)

            # Sleep until next verification round
            await asyncio.sleep(self.verification_interval)

    async def _verify_all_providers(self):
        """
        Verify all registered providers.

        Runs verification checks for each provider in parallel for efficiency.
        """
        if not self._verifiers:
            logger.debug("No providers registered for verification")
            return

        logger.debug(
            f"Starting verification round for {len(self._verifiers)} providers"
        )

        # Run all verifications in parallel
        tasks = []
        for provider_id, (verifier, test_model) in self._verifiers.items():
            task = self._verify_single_provider(provider_id, verifier, test_model)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.debug("Verification round completed")

    async def _verify_single_provider(
        self, provider_id: str, verifier: BaseAttestationVerifier, test_model: str
    ):
        """
        Verify a single provider.

        Args:
            provider_id: Provider identifier
            verifier: Attestation verifier
            test_model: Model to verify
        """
        try:
            logger.debug(f"Verifying provider '{provider_id}'")
            result = await verifier.verify_provider(test_model)
            self._update_health(provider_id, result)
        except Exception as e:
            logger.error(f"Verification error for '{provider_id}': {e}", exc_info=True)
            self._mark_unhealthy(provider_id, f"Verification exception: {str(e)}")

    def _update_health(self, provider_id: str, result: AttestationResult):
        """
        Update provider health based on verification result.

        Args:
            provider_id: Provider identifier
            result: Attestation verification result
        """
        health = self._provider_health[provider_id]
        health.last_check = result

        if result.verified:
            health.healthy = True
            health.last_healthy_at = datetime.now(timezone.utc)
            health.error = None
            logger.info(f"Provider '{provider_id}': healthy")
        else:
            health.healthy = False
            # Join all errors into a single string
            health.error = (
                "; ".join(result.errors) if result.errors else "Verification failed"
            )
            logger.warning(f"Provider '{provider_id}': unhealthy - {health.error}")

    def _mark_unhealthy(self, provider_id: str, error: str):
        """
        Mark provider as unhealthy.

        Args:
            provider_id: Provider identifier
            error: Error message explaining why provider is unhealthy
        """
        if provider_id not in self._provider_health:
            logger.error(
                f"Attempted to mark unknown provider '{provider_id}' as unhealthy"
            )
            return

        health = self._provider_health[provider_id]
        health.healthy = False
        health.error = error
        logger.warning(f"Marked provider '{provider_id}' as unhealthy: {error}")

    async def verify_now(self, provider_id: str) -> AttestationResult:
        """
        Force immediate verification of a provider.

        Args:
            provider_id: Provider identifier

        Returns:
            AttestationResult from verification

        Raises:
            ValueError: If provider not registered
        """
        if provider_id not in self._verifiers:
            raise ValueError(f"Unknown provider: {provider_id}")

        logger.info(f"Starting immediate verification for provider '{provider_id}'")
        verifier, test_model = self._verifiers[provider_id]
        result = await verifier.verify_provider(test_model)
        self._update_health(provider_id, result)
        logger.info(
            f"Immediate verification completed for '{provider_id}': {'healthy' if result.verified else 'unhealthy'}"
        )

        return result


# Global singleton instance
attestation_scheduler = AttestationScheduler()
