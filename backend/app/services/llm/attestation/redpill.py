"""
RedPill Attestation Verifier

Full TEE attestation verification for RedPill.ai confidential models.
Verifies Intel TDX, NVIDIA GPU attestation, and nonce binding.
"""

import base64
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import aiohttp

from app.core.config import settings

from .base import BaseAttestationVerifier
from .models import AttestationResult

logger = logging.getLogger(__name__)


def get_confidential_model_prefixes() -> Tuple[str, ...]:
    """Get confidential model prefixes from settings."""
    return tuple(
        p.strip()
        for p in settings.REDPILL_CONFIDENTIAL_MODEL_PREFIXES.split(",")
        if p.strip()
    )


class RedPillAttestationVerifier(BaseAttestationVerifier):
    """
    Verifies RedPill TEE attestation for confidential models.

    Performs comprehensive verification of:
    - Intel TDX quote (CPU TEE)
    - NVIDIA GPU attestation (GPU TEE)
    - Nonce binding (replay attack prevention)
    """

    def __init__(self, api_base: str, api_key: str):
        """
        Initialize RedPill verifier.

        Args:
            api_base: Base URL for RedPill API
            api_key: API key for authentication
        """
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        logger.debug(f"Initialized RedPill verifier for {self.api_base}")

    def is_confidential_model(self, model: str) -> bool:
        """
        Check if model is a confidential (full TEE) model.

        Args:
            model: Model name to check

        Returns:
            True if model is confidential
        """
        return model.lower().startswith(get_confidential_model_prefixes())

    async def verify_provider(self, model: str) -> AttestationResult:
        """
        Full verification flow for RedPill provider.

        Args:
            model: Model name to verify

        Returns:
            AttestationResult with comprehensive verification details
        """
        logger.info(f"Starting RedPill attestation verification for model: {model}")
        errors = []

        # 1. Validate model is confidential
        if not self.is_confidential_model(model):
            error_msg = f"Model {model} is not a confidential model"
            logger.warning(f"RedPill verification failed: {error_msg}")
            return AttestationResult(
                verified=False,
                provider_id="redpill",
                model=model,
                timestamp=datetime.now(timezone.utc),
                errors=[error_msg],
            )

        # 2. Generate fresh nonce
        nonce = secrets.token_hex(32)
        logger.debug(f"Generated nonce for attestation: {nonce[:16]}...")

        # 3. Fetch attestation report
        try:
            report = await self._fetch_attestation(model, nonce)
            logger.debug("Successfully fetched attestation report")
        except Exception as e:
            error_msg = f"Failed to fetch attestation: {str(e)}"
            logger.error(f"RedPill attestation fetch error: {error_msg}")
            return AttestationResult(
                verified=False,
                provider_id="redpill",
                model=model,
                timestamp=datetime.now(timezone.utc),
                errors=[error_msg],
            )

        # Handle multi-node response
        attestation = (
            report.get("all_attestations", [report])[0]
            if report.get("all_attestations")
            else report
        )

        signing_address = attestation.get("signing_address")
        logger.debug(f"Attestation signing address: {signing_address}")

        # 4. Verify Intel TDX quote
        intel_result = await self._verify_intel_tdx(attestation)
        intel_verified = intel_result.get("verified", False)
        if not intel_verified:
            error_msg = f"Intel TDX: {intel_result.get('message', 'failed')}"
            errors.append(error_msg)
            logger.warning(error_msg)
        else:
            logger.debug("Intel TDX verification passed")

        # 5. Verify GPU attestation (required for confidential models)
        gpu_result = await self._verify_gpu(attestation, nonce)
        gpu_verified = gpu_result.get("verified", False)
        if not gpu_verified:
            error_msg = f"GPU attestation: {gpu_result.get('message', 'failed')}"
            errors.append(error_msg)
            logger.warning(error_msg)
        else:
            logger.debug("GPU attestation verification passed")

        # 6. Verify nonce binding
        nonce_verified = self._verify_nonce_binding(
            attestation, nonce, intel_result.get("quote", {})
        )
        if not nonce_verified:
            error_msg = "Nonce binding verification failed"
            errors.append(error_msg)
            logger.warning(error_msg)
        else:
            logger.debug("Nonce binding verification passed")

        # Final result
        all_verified = intel_verified and gpu_verified and nonce_verified
        if all_verified:
            logger.info(f"RedPill attestation verified successfully for {model}")
        else:
            logger.warning(
                f"RedPill attestation failed for {model}: {', '.join(errors)}"
            )

        return AttestationResult(
            verified=all_verified,
            provider_id="redpill",
            model=model,
            timestamp=datetime.now(timezone.utc),
            signing_address=signing_address,
            intel_tdx_verified=intel_verified,
            gpu_attestation_verified=gpu_verified,
            nonce_binding_verified=nonce_verified,
            errors=errors,
        )

    async def _fetch_attestation(self, model: str, nonce: str) -> Dict[str, Any]:
        """
        Fetch attestation report from RedPill API.

        Args:
            model: Model name
            nonce: Fresh nonce for this verification

        Returns:
            Attestation report JSON

        Raises:
            Exception: If fetch fails
        """
        url = f"{self.api_base}/attestation/report"
        params = {"model": model, "nonce": nonce}

        logger.debug(f"Fetching attestation from {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"HTTP {response.status}: {text}")
                return await response.json()

    async def _verify_intel_tdx(self, attestation: Dict) -> Dict[str, Any]:
        """
        Verify Intel TDX quote via Phala's verification service.

        Args:
            attestation: Attestation report containing intel_quote

        Returns:
            Dict with verified status and quote details
        """
        intel_quote = attestation.get("intel_quote")
        if not intel_quote:
            logger.warning("No Intel quote found in attestation")
            return {"verified": False, "message": "No Intel quote"}

        logger.debug("Verifying Intel TDX quote with Phala service")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.PHALA_TDX_VERIFIER_URL,
                    json={"hex": intel_quote},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()
                    quote = result.get("quote", {})
                    return {
                        "verified": quote.get("verified", False),
                        "message": quote.get("message"),
                        "quote": quote,
                    }
        except Exception as e:
            logger.error(f"Intel TDX verification error: {e}")
            return {"verified": False, "message": f"Verification error: {str(e)}"}

    async def _verify_gpu(self, attestation: Dict, nonce: str) -> Dict[str, Any]:
        """
        Verify GPU attestation via NVIDIA NRAS.

        Args:
            attestation: Attestation report containing nvidia_payload
            nonce: Original nonce for verification

        Returns:
            Dict with verified status and verdict
        """
        nvidia_payload = attestation.get("nvidia_payload")
        if not nvidia_payload:
            logger.warning("No NVIDIA payload found in attestation")
            return {"verified": False, "message": "No NVIDIA payload"}

        try:
            payload = json.loads(nvidia_payload)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse NVIDIA payload: {e}")
            return {"verified": False, "message": "Invalid NVIDIA payload JSON"}

        # Verify nonce matches (case-sensitive for security)
        if payload.get("nonce", "") != nonce:
            logger.warning("Nonce mismatch in NVIDIA payload")
            return {"verified": False, "message": "Nonce mismatch"}

        logger.debug("Verifying GPU attestation with NVIDIA NRAS")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.NVIDIA_NRAS_API_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()

                    # Parse JWT verdict
                    jwt_token = result[0][1] if result and len(result) > 0 else None
                    if jwt_token:
                        payload_b64 = jwt_token.split(".")[1]
                        padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
                        jwt_payload = json.loads(base64.urlsafe_b64decode(padded))
                        verdict = jwt_payload.get("x-nvidia-overall-att-result")
                        logger.debug(f"NVIDIA verdict: {verdict}")
                        # Verdict should be boolean True, but also accept "PASS" for compatibility
                        is_verified = (
                            verdict is True or verdict == "PASS" or verdict == True
                        )
                        return {"verified": is_verified, "verdict": verdict}

                    logger.warning("Invalid NVIDIA response format")
                    return {"verified": False, "message": "Invalid NVIDIA response"}
        except Exception as e:
            logger.error(f"GPU verification error: {e}")
            return {"verified": False, "message": f"Verification error: {str(e)}"}

    def _verify_nonce_binding(
        self, attestation: Dict, nonce: str, intel_quote: Dict
    ) -> bool:
        """
        Verify signing address and nonce are bound in TDX report data.

        CRITICAL SECURITY CHECK: The Intel TDX report data first 64 bytes contain:
        - Bytes 0-31: Signing address (may be left-padded with zeros or right-aligned)
        - Bytes 32-63: Request nonce

        This proves:
        1. The signing key was generated inside the TEE
        2. The attestation is fresh (contains your unique nonce)
        3. The signing address belongs to this verified TEE instance

        Args:
            attestation: Full attestation report
            nonce: Original nonce
            intel_quote: Parsed Intel quote

        Returns:
            True if both signing address and nonce are properly bound
        """
        report_data_hex = intel_quote.get("body", {}).get("reportdata", "")
        if not report_data_hex:
            logger.warning("No report data found in Intel quote")
            return False

        signing_address = attestation.get("signing_address")
        if not signing_address:
            logger.warning("No signing address in attestation")
            return False

        try:
            report_data = bytes.fromhex(report_data_hex.removeprefix("0x"))

            # Extract embedded nonce from report data (always at bytes 32-63)
            embedded_nonce = report_data[32:64]

            # Parse signing address based on algorithm
            signing_algo = attestation.get("signing_algo", "ecdsa")
            signing_address_bytes = bytes.fromhex(signing_address.removeprefix("0x"))
            address_len = len(signing_address_bytes)

            # Extract first 32 bytes for address verification
            embedded_address_field = report_data[:32]

            # Check address binding - support multiple formats:
            # Format 1: Left-padded with zeros (Ethereum style: 12 zero bytes + 20-byte address)
            expected_left_padded = signing_address_bytes.rjust(32, b"\x00")
            # Format 2: Right-padded with zeros (address at start, zeros at end)
            expected_right_padded = signing_address_bytes.ljust(32, b"\x00")
            # Format 3: Address at start of field (check first N bytes match)
            embedded_address_prefix = embedded_address_field[:address_len]

            address_verified = False
            if embedded_address_field == expected_left_padded:
                logger.debug("Address verified: left-padded format")
                address_verified = True
            elif embedded_address_field == expected_right_padded:
                logger.debug("Address verified: right-padded format")
                address_verified = True
            elif embedded_address_prefix == signing_address_bytes:
                logger.debug("Address verified: prefix match format")
                address_verified = True

            if not address_verified:
                logger.warning(
                    f"Signing address not found in TEE report data: "
                    f"address={signing_address_bytes.hex()}, "
                    f"report_data_first_32={embedded_address_field.hex()}"
                )
                return False

            # Verify nonce matches exactly
            nonce_bytes = bytes.fromhex(nonce)
            if embedded_nonce != nonce_bytes:
                logger.warning(
                    f"Nonce mismatch: expected {nonce[:16]}..., got {embedded_nonce.hex()[:16]}..."
                )
                return False

            logger.debug(
                "Report data binding verified: signing address and nonce match"
            )
            return True

        except Exception as e:
            logger.error(f"Report data binding verification error: {e}")
            return False
