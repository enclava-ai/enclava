"""
PrivateMode Attestation Verifier

Simple verifier for PrivateMode proxy. The proxy handles attestation internally.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp

from .base import BaseAttestationVerifier
from .models import AttestationResult

logger = logging.getLogger(__name__)


class PrivateModeAttestationVerifier(BaseAttestationVerifier):
    """
    Simple verifier for PrivateMode.

    The privatemode-proxy handles attestation internally. If the proxy
    responds successfully, TEE attestation is valid. A failed attestation
    would cause the proxy to reject all requests.
    """

    def __init__(self, proxy_url: str, api_key: str):
        """
        Initialize PrivateMode verifier.

        Args:
            proxy_url: Base URL of the privatemode proxy
            api_key: API key for authentication
        """
        self.proxy_url = proxy_url.rstrip("/")
        self.api_key = api_key
        logger.debug(f"Initialized PrivateMode verifier for {self.proxy_url}")

    async def verify_provider(self, model: str = None) -> AttestationResult:
        """
        Verify PrivateMode by checking if proxy responds.

        If /models endpoint succeeds, the TEE attestation is working.

        Args:
            model: Unused for PrivateMode (proxy checks all models)

        Returns:
            AttestationResult with verification status
        """
        logger.debug("Starting PrivateMode attestation verification")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.proxy_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info("PrivateMode attestation verified successfully")
                        return AttestationResult(
                            verified=True,
                            provider_id="privatemode",
                            model=model or "all",
                            timestamp=datetime.now(timezone.utc),
                            intel_tdx_verified=True,  # Proxy handles this
                            gpu_attestation_verified=True,  # Proxy handles this
                            nonce_binding_verified=True,  # Proxy handles this
                            errors=[],
                        )
                    else:
                        text = await response.text()
                        error_msg = f"Proxy returned HTTP {response.status}: {text}"
                        logger.warning(f"PrivateMode attestation failed: {error_msg}")
                        return AttestationResult(
                            verified=False,
                            provider_id="privatemode",
                            model=model or "all",
                            timestamp=datetime.now(timezone.utc),
                            errors=[error_msg],
                        )

        except aiohttp.ClientError as e:
            error_msg = f"Proxy unreachable: {str(e)}"
            logger.error(f"PrivateMode attestation error: {error_msg}")
            return AttestationResult(
                verified=False,
                provider_id="privatemode",
                model=model or "all",
                timestamp=datetime.now(timezone.utc),
                errors=[error_msg],
            )
        except Exception as e:
            error_msg = f"Verification error: {str(e)}"
            logger.error(
                f"PrivateMode attestation unexpected error: {error_msg}", exc_info=True
            )
            return AttestationResult(
                verified=False,
                provider_id="privatemode",
                model=model or "all",
                timestamp=datetime.now(timezone.utc),
                errors=[error_msg],
            )
