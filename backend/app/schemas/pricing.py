"""
Pricing Management Schemas
Pydantic models for provider pricing API
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class SetPricingRequest(BaseModel):
    """Request schema for setting manual pricing"""

    provider_id: str = Field(
        ..., min_length=1, max_length=50, description="Provider identifier"
    )
    model_id: str = Field(
        ..., min_length=1, max_length=255, description="Model identifier"
    )
    input_price_per_million_cents: int = Field(
        ..., ge=0, description="Input price in cents per million tokens"
    )
    output_price_per_million_cents: int = Field(
        ..., ge=0, description="Output price in cents per million tokens"
    )
    reason: str = Field(
        ..., min_length=1, max_length=500, description="Reason for the pricing change"
    )
    model_name: Optional[str] = Field(
        None, max_length=255, description="Human-readable model name"
    )

    @validator("provider_id")
    def validate_provider_id(cls, v):
        """Validate provider_id is lowercase and alphanumeric with underscores"""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Provider ID must be alphanumeric with underscores/hyphens"
            )
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": "privatemode",
                "model_id": "meta-llama/llama-3.1-70b-instruct",
                "input_price_per_million_cents": 40,
                "output_price_per_million_cents": 40,
                "reason": "Initial pricing for PrivateMode TEE-protected inference",
                "model_name": "Llama 3.1 70B Instruct",
            }
        }


class PricingResponse(BaseModel):
    """Response schema for pricing data"""

    id: int
    provider_id: str
    model_id: str
    model_name: Optional[str]
    input_price_per_million_cents: int
    output_price_per_million_cents: int
    input_price_per_million_dollars: float
    output_price_per_million_dollars: float
    currency: str = Field(
        default="USD", description="ISO 4217 currency code (USD, EUR)"
    )
    price_source: str
    is_override: bool
    override_reason: Optional[str]
    override_by_user_id: Optional[int]
    context_length: Optional[int]
    architecture: Optional[Dict[str, Any]]
    quantization: Optional[str]
    effective_from: datetime
    effective_until: Optional[datetime]
    is_current: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PricingHistoryResponse(BaseModel):
    """Response schema for pricing history"""

    id: int
    provider_id: str
    model_id: str
    model_name: Optional[str]
    input_price_per_million_cents: int
    output_price_per_million_cents: int
    currency: str = Field(
        default="USD", description="ISO 4217 currency code (USD, EUR)"
    )
    price_source: str
    is_override: bool
    override_reason: Optional[str]
    effective_from: datetime
    effective_until: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class PricingAuditLogResponse(BaseModel):
    """Response schema for pricing audit log entries"""

    id: int
    provider_id: str
    model_id: str
    action: str
    old_input_price_per_million_cents: Optional[int]
    old_output_price_per_million_cents: Optional[int]
    new_input_price_per_million_cents: int
    new_output_price_per_million_cents: int
    change_source: str
    changed_by_user_id: Optional[int]
    change_reason: Optional[str]
    sync_job_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SyncResultModel(BaseModel):
    """Result for a single model sync"""

    model_id: str
    model_name: Optional[str]
    action: str  # 'created', 'updated', 'unchanged'
    old_input_price: Optional[int]
    old_output_price: Optional[int]
    new_input_price: int
    new_output_price: int


class SyncResultResponse(BaseModel):
    """Response schema for sync operation results"""

    provider_id: str
    sync_job_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    total_models: int
    created_count: int
    updated_count: int
    unchanged_count: int
    error_count: int
    models: List[SyncResultModel]
    errors: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": "redpill",
                "sync_job_id": "123e4567-e89b-12d3-a456-426614174000",
                "started_at": "2025-01-15T10:30:00Z",
                "completed_at": "2025-01-15T10:30:05Z",
                "duration_ms": 5000,
                "total_models": 10,
                "created_count": 2,
                "updated_count": 1,
                "unchanged_count": 7,
                "error_count": 0,
                "models": [
                    {
                        "model_id": "phala/deepseek-r1-0528",
                        "model_name": "DeepSeek R1",
                        "action": "updated",
                        "old_input_price": 50,
                        "old_output_price": 200,
                        "new_input_price": 55,
                        "new_output_price": 219,
                    }
                ],
                "errors": [],
            }
        }


class PricingListResponse(BaseModel):
    """Response schema for listing all pricing"""

    pricing: List[PricingResponse]
    total: int
    providers: List[str]


class RemoveOverrideResponse(BaseModel):
    """Response schema for remove override operation"""

    success: bool
    provider_id: str
    model_id: str
    message: str
    previous_pricing: Optional[PricingResponse]


class PricingSummary(BaseModel):
    """Summary statistics for pricing"""

    total_models: int
    models_by_provider: Dict[str, int]
    override_count: int
    api_sync_count: int
    manual_count: int
    last_sync_at: Optional[datetime]


class BulkPricingRequest(BaseModel):
    """Request schema for bulk pricing updates"""

    pricing_updates: List[SetPricingRequest]

    @validator("pricing_updates")
    def validate_pricing_updates(cls, v):
        if len(v) > 100:
            raise ValueError("Cannot update more than 100 pricing entries at once")
        return v


class BulkPricingResponse(BaseModel):
    """Response schema for bulk pricing operations"""

    total_requested: int
    success_count: int
    error_count: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]


class ProviderMetadataResponse(BaseModel):
    """Response schema for provider metadata"""

    id: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Human-readable provider name")
    currency: str = Field(..., description="Native currency code (ISO 4217: USD, EUR)")
    currency_symbol: str = Field(..., description="Currency symbol ($, €)")
    supports_api_sync: bool = Field(
        ..., description="Whether pricing can be synced from API"
    )
    description: str = Field(..., description="Brief description of the provider")
    website: Optional[str] = Field(None, description="Provider website URL")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "privatemode",
                "display_name": "PrivateMode.ai",
                "currency": "EUR",
                "currency_symbol": "€",
                "supports_api_sync": False,
                "description": "Confidential AI inference with TEE protection",
                "website": "https://privatemode.ai",
            }
        }


class ProviderListResponse(BaseModel):
    """Response schema for listing all providers"""

    providers: List[ProviderMetadataResponse]
    total: int
