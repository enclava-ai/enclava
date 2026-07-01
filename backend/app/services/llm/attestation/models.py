"""
Attestation Result and Provider Health Models

Data models for tracking attestation verification results and provider health state.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AttestationResult(BaseModel):
    """
    Result of a single attestation check.

    Contains all verification details including Intel TDX, GPU attestation,
    and nonce binding verification results.
    """

    verified: bool
    provider_id: str
    model: str
    timestamp: datetime
    signing_address: Optional[str] = None
    intel_tdx_verified: bool = False
    gpu_attestation_verified: bool = False
    nonce_binding_verified: bool = False
    errors: List[str] = Field(default_factory=list)  # List of error messages
    error_details: Optional[Dict[str, Any]] = None  # Detailed error context


class ProviderHealth(BaseModel):
    """
    Provider health state. Binary: healthy or unhealthy.

    Healthy = attestation works AND inference works
    Unhealthy = attestation fails OR inference fails OR unreachable
    """

    provider_id: str
    healthy: bool
    last_check: Optional[AttestationResult] = None
    last_healthy_at: Optional[datetime] = None
    error: Optional[str] = None  # Why it's unhealthy
