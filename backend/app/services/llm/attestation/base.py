"""
Base Attestation Verifier Interface

Abstract base class for provider-specific attestation verification.
"""

from abc import ABC, abstractmethod

from .models import AttestationResult


class BaseAttestationVerifier(ABC):
    """
    Abstract base class for attestation verification.

    Each provider implements this to verify their specific TEE attestation
    mechanism (e.g., Intel TDX, AMD SEV-SNP, NVIDIA H100 attestation).
    """

    @abstractmethod
    async def verify_provider(self, model: str) -> AttestationResult:
        """
        Verify provider attestation for a specific model.

        Args:
            model: Model name to verify (some providers require model-specific checks)

        Returns:
            AttestationResult with verification details

        This method should:
        1. Generate fresh nonce (if applicable)
        2. Fetch attestation report
        3. Verify TEE components (TDX, GPU, etc.)
        4. Check nonce binding
        5. Return comprehensive result
        """
        pass
