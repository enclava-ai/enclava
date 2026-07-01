"""
Attestation Module

Provider attestation verification for confidential AI providers.

This module provides:
- AttestationScheduler: Periodic verification of provider attestations
- BaseAttestationVerifier: Abstract base for provider-specific verifiers
- PrivateModeAttestationVerifier: Simple proxy health check
- RedPillAttestationVerifier: Full TDX + GPU attestation
- AttestationResult, ProviderHealth: Data models
"""

from .base import BaseAttestationVerifier
from .models import AttestationResult, ProviderHealth
from .privatemode import PrivateModeAttestationVerifier
from .redpill import RedPillAttestationVerifier
from .scheduler import AttestationScheduler, attestation_scheduler

__all__ = [
    # Models
    "AttestationResult",
    "ProviderHealth",
    # Base
    "BaseAttestationVerifier",
    # Verifiers
    "PrivateModeAttestationVerifier",
    "RedPillAttestationVerifier",
    # Scheduler
    "AttestationScheduler",
    "attestation_scheduler",
]
