"""Pydantic schemas for Extract."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Allowed primitive types for context values
ContextValue = Optional[Union[str, int, float, bool]]


class ExtractContext(BaseModel):
    """
    Schema for validating context passed to template processing.

    Context allows arbitrary string keys but validates that all values
    are primitives (str, int, float, bool, or None). Nested objects
    and arrays are rejected to prevent unexpected behavior during
    template placeholder substitution.

    Example valid context:
        {"company_name": "Acme Corp", "currency": "USD", "vat_rate": 0.21}

    Example invalid context:
        {"items": [{"name": "item1"}]}  # Arrays/nested objects not allowed
    """

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def validate_context_values(cls, values: Any) -> Any:
        """Validate that all values are primitives (no nested objects/arrays)."""
        if not isinstance(values, dict):
            raise ValueError("Context must be a JSON object")

        invalid_keys = []
        for key, value in values.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"Context keys must be strings, got {type(key).__name__} for key: {key}"
                )

            # Check for nested objects and arrays
            if isinstance(value, (dict, list)):
                invalid_keys.append(key)
            # Allow primitives: str, int, float, bool, None
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                invalid_keys.append(key)

        if invalid_keys:
            raise ValueError(
                f"Context values must be primitives (string, number, boolean, or null). "
                f"Nested objects or arrays found in keys: {', '.join(invalid_keys)}"
            )

        return values

    def to_dict(self) -> Dict[str, ContextValue]:
        """Convert to plain dictionary for use in template processing."""
        return dict(self)


# Template schemas
class TemplateCreate(BaseModel):
    """Schema for creating a new template."""

    id: str = Field(..., description="Unique template identifier")
    description: Optional[str] = Field(None, description="Template description")
    system_prompt: str = Field(..., description="System message for vision model")
    user_prompt: str = Field(
        ...,
        description="User message template (supports placeholders like {company_name})",
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="Expected JSON schema for validation"
    )
    context_schema: Optional[Dict[str, Any]] = Field(
        None, description="Defines context variables (e.g., company_name, currency)"
    )
    model: Optional[str] = Field(
        None, description="Vision model to use (overrides module default)"
    )


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""

    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    output_schema: Optional[Dict[str, Any]] = None
    context_schema: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


class TemplateResponse(BaseModel):
    """Schema for template response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    description: Optional[str]
    system_prompt: str
    user_prompt: str
    output_schema: Optional[Dict[str, Any]]
    context_schema: Optional[Dict[str, Any]]
    model: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class TemplateListResponse(BaseModel):
    """Schema for template list response."""

    templates: List[TemplateResponse]


# Job schemas
class JobStatus:
    """Job status constants."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobSummary(BaseModel):
    """Summary of a job for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: str
    template_id: str
    created_at: datetime
    completed_at: Optional[datetime]
    total_cost_cents: Optional[int]


class JobListResponse(BaseModel):
    """Response for job list endpoint."""

    jobs: List[JobSummary]
    total: int
    limit: int
    offset: int


class JobDetailResponse(BaseModel):
    """Detailed job response with results."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    user_id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    num_pages: int
    status: str
    template_id: str
    buyer_context: Optional[str] = Field(
        None, description="Context JSON string (legacy field name)"
    )
    model_used: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_cost_cents: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result: Optional[Dict[str, Any]] = Field(
        None, description="Extracted data from final result"
    )


# Processing schemas
class ProcessResult(BaseModel):
    """Result of document processing."""

    success: bool
    job_id: str
    data: Dict[str, Any]
    raw_response: str
    validation_errors: List[str]
    validation_warnings: List[str]
    processing_time_ms: int
    tokens_used: int
    cost_cents: int


class ProcessResponse(BaseModel):
    """Response for process endpoint."""

    success: bool
    job_id: str
    data: Dict[str, Any]
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    processing_time_ms: int
    tokens_used: int
    cost_cents: int


# Model schemas
class ModelInfo(BaseModel):
    """Information about a vision-capable model."""

    id: str
    name: str
    provider: str
    supports_vision: bool = True


class ModelsResponse(BaseModel):
    """Response for models endpoint."""

    models: List[ModelInfo]


# Settings schemas
class ExtractSettingsUpdate(BaseModel):
    """Schema for updating extract settings."""

    default_model: str = Field(
        ..., description="Default vision model for all templates"
    )


class ExtractSettingsResponse(BaseModel):
    """Schema for extract settings response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    default_model: Optional[str]  # Can be null until first vision model is selected
    created_at: datetime
    updated_at: Optional[datetime]
