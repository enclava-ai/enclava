"""
Usage Statistics Schemas

Pydantic models for usage statistics API responses.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ProviderBreakdown(BaseModel):
    """Breakdown by provider"""

    provider_id: str = Field(..., description="Provider identifier")
    provider_name: str = Field(..., description="Provider display name")
    requests: int = Field(..., description="Total requests")
    tokens: int = Field(..., description="Total tokens used")
    cost_dollars: float = Field(..., description="Total cost in dollars")


class ModelBreakdown(BaseModel):
    """Breakdown by model"""

    model: str = Field(..., description="Model identifier")
    provider_id: str = Field(..., description="Provider identifier")
    requests: int = Field(..., description="Total requests")
    tokens: int = Field(..., description="Total tokens used")
    cost_dollars: float = Field(..., description="Total cost in dollars")


class DailyTrend(BaseModel):
    """Daily usage trend"""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    requests: int = Field(..., description="Total requests for the day")
    tokens: int = Field(..., description="Total tokens for the day")
    cost_dollars: float = Field(..., description="Total cost for the day in dollars")


class SourceBreakdown(BaseModel):
    """Breakdown by usage source"""

    source: str = Field(
        ..., description="Source identifier (agent, api_key, playground)"
    )
    source_name: str = Field(..., description="Source display name")
    total_requests: int = Field(..., description="Total requests from this source")
    total_tokens: int = Field(..., description="Total tokens from this source")
    total_cost_dollars: float = Field(..., description="Total cost from this source")


class UsageSummary(BaseModel):
    """Summary statistics"""

    total_requests: int = Field(..., description="Total number of requests")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_dollars: float = Field(..., description="Total cost in dollars")
    error_rate_percent: float = Field(..., description="Error rate as percentage")
    successful_requests: int = Field(..., description="Number of successful requests")
    failed_requests: int = Field(..., description="Number of failed requests")


class UsageStatsResponse(BaseModel):
    """Complete usage statistics response"""

    summary: UsageSummary
    by_provider: List[ProviderBreakdown]
    by_model: List[ModelBreakdown]
    daily_trend: List[DailyTrend]
    by_source: Optional[List[SourceBreakdown]] = Field(
        None, description="Breakdown by source (only for user-level stats)"
    )

    class Config:
        from_attributes = True


class UsageRecordResponse(BaseModel):
    """Individual usage record"""

    id: int
    request_id: str
    created_at: datetime
    provider_id: str
    provider_model: str
    normalized_model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_cents: int
    output_cost_cents: int
    total_cost_cents: int
    total_cost_dollars: float
    endpoint: str
    method: str
    agent_config_id: Optional[int] = None
    status: str
    error_type: Optional[str] = None
    is_streaming: bool
    latency_ms: Optional[int] = None
    ttft_ms: Optional[int] = None

    @field_validator("total_cost_dollars", mode="before")
    def calculate_cost_dollars(cls, v, info):
        """Calculate cost in dollars from cents"""
        if "total_cost_cents" in info.data:
            return info.data["total_cost_cents"] / 100
        return v

    class Config:
        from_attributes = True


class UsageRecordsListResponse(BaseModel):
    """Paginated list of usage records"""

    records: List[UsageRecordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UsageOverviewResponse(BaseModel):
    """System-wide usage overview"""

    summary: UsageSummary
    by_provider: List[ProviderBreakdown]
    top_models: List[ModelBreakdown]
    daily_trend: List[DailyTrend]
    period_start: datetime
    period_end: datetime


class TopUser(BaseModel):
    """Top user by spend"""

    user_id: int
    username: Optional[str]
    email: Optional[str]
    total_requests: int
    total_tokens: int
    total_cost_dollars: float
    api_key_count: int


class TopUsersResponse(BaseModel):
    """List of top users"""

    users: List[TopUser]
    period_start: datetime
    period_end: datetime


class TopAPIKey(BaseModel):
    """Top API key by spend"""

    api_key_id: int
    api_key_name: str
    key_prefix: str
    user_id: int
    total_requests: int
    total_tokens: int
    total_cost_dollars: float


class TopKeysResponse(BaseModel):
    """List of top API keys"""

    keys: List[TopAPIKey]
    period_start: datetime
    period_end: datetime


class ProviderStatsDetail(BaseModel):
    """Detailed provider statistics"""

    provider_id: str
    provider_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate_percent: float
    total_tokens: int
    total_cost_dollars: float
    average_latency_ms: Optional[float]
    average_tokens_per_request: float
    top_models: List[ModelBreakdown]


class ProviderBreakdownResponse(BaseModel):
    """Provider breakdown response"""

    providers: List[ProviderStatsDetail]
    period_start: datetime
    period_end: datetime
    total_requests: int
    total_cost_dollars: float
