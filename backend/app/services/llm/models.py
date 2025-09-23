"""
LLM Service Data Models

Pydantic models for LLM requests and responses.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime


class ChatMessage(BaseModel):
    """Individual chat message"""
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(None, description="Optional message name")
    
    @validator('role')
    def validate_role(cls, v):
        allowed_roles = {'system', 'user', 'assistant', 'function'}
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v


class ChatRequest(BaseModel):
    """Chat completion request"""
    model: str = Field(..., description="Model identifier")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, ge=1, le=32000, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    top_k: Optional[int] = Field(None, ge=1, description="Top-k sampling parameter")
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop sequences")
    stream: Optional[bool] = Field(False, description="Stream response")
    user_id: str = Field(..., description="User identifier")
    api_key_id: int = Field(..., description="API key identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError("Messages cannot be empty")
        return v


class TokenUsage(BaseModel):
    """Token usage information"""
    prompt_tokens: int = Field(..., description="Tokens in the prompt")
    completion_tokens: int = Field(..., description="Tokens in the completion")
    total_tokens: int = Field(..., description="Total tokens used")


class ChatChoice(BaseModel):
    """Chat completion choice"""
    index: int = Field(..., description="Choice index")
    message: ChatMessage = Field(..., description="Generated message")
    finish_reason: Optional[str] = Field(None, description="Reason for completion finish")


class ChatResponse(BaseModel):
    """Chat completion response"""
    id: str = Field(..., description="Response identifier")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Provider used")
    choices: List[ChatChoice] = Field(..., description="Generated choices")
    usage: Optional[TokenUsage] = Field(None, description="Token usage")
    system_fingerprint: Optional[str] = Field(None, description="System fingerprint")
    
    # Security and audit information
    security_check: bool = Field(..., description="Whether security check passed")
    risk_score: float = Field(..., description="Security risk score")
    detected_patterns: List[str] = Field(default_factory=list, description="Detected security patterns")
    
    # Performance metrics
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    provider_latency_ms: Optional[float] = Field(None, description="Provider-specific latency")


class EmbeddingRequest(BaseModel):
    """Embedding generation request"""
    model: str = Field(..., description="Embedding model identifier")
    input: Union[str, List[str]] = Field(..., description="Text to embed")
    encoding_format: Optional[str] = Field("float", description="Encoding format")
    dimensions: Optional[int] = Field(None, ge=1, description="Number of dimensions")
    user_id: str = Field(..., description="User identifier")
    api_key_id: int = Field(..., description="API key identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('input')
    def validate_input(cls, v):
        if isinstance(v, str):
            if not v.strip():
                raise ValueError("Input text cannot be empty")
        elif isinstance(v, list):
            if not v or not all(isinstance(item, str) and item.strip() for item in v):
                raise ValueError("Input list cannot be empty and must contain non-empty strings")
        return v


class EmbeddingData(BaseModel):
    """Single embedding data"""
    object: str = Field("embedding", description="Object type")
    index: int = Field(..., description="Embedding index")
    embedding: List[float] = Field(..., description="Embedding vector")


class EmbeddingResponse(BaseModel):
    """Embedding generation response"""
    object: str = Field("list", description="Object type")
    data: List[EmbeddingData] = Field(..., description="Embedding data")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Provider used")
    usage: Optional[TokenUsage] = Field(None, description="Token usage")
    
    # Security and audit information
    security_check: bool = Field(..., description="Whether security check passed")
    risk_score: float = Field(..., description="Security risk score")
    
    # Performance metrics
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    provider_latency_ms: Optional[float] = Field(None, description="Provider-specific latency")


class ModelInfo(BaseModel):
    """Model information"""
    id: str = Field(..., description="Model identifier")
    object: str = Field("model", description="Object type")
    created: Optional[int] = Field(None, description="Creation timestamp")
    owned_by: str = Field(..., description="Model owner")
    provider: str = Field(..., description="Provider name")
    capabilities: List[str] = Field(default_factory=list, description="Model capabilities")
    context_window: Optional[int] = Field(None, description="Context window size")
    max_output_tokens: Optional[int] = Field(None, description="Maximum output tokens")
    supports_streaming: bool = Field(False, description="Whether model supports streaming")
    supports_function_calling: bool = Field(False, description="Whether model supports function calling")
    tasks: Optional[List[str]] = Field(None, description="Model tasks (e.g., generate, embed, vision)")


class ProviderStatus(BaseModel):
    """Provider health status"""
    provider: str = Field(..., description="Provider name")
    status: str = Field(..., description="Status (healthy, degraded, unavailable)")
    latency_ms: Optional[float] = Field(None, description="Average latency")
    success_rate: Optional[float] = Field(None, description="Success rate (0.0 to 1.0)")
    last_check: datetime = Field(..., description="Last health check timestamp")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")
    models_available: List[str] = Field(default_factory=list, description="Available models")


class LLMMetrics(BaseModel):
    """LLM service metrics"""
    total_requests: int = Field(0, description="Total requests processed")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    average_latency_ms: float = Field(0.0, description="Average response latency")
    average_risk_score: float = Field(0.0, description="Average security risk score")
    provider_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Per-provider metrics")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last metrics update")


class ResilienceConfig(BaseModel):
    """Configuration for resilience patterns"""
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay_ms: int = Field(1000, ge=100, le=30000, description="Initial retry delay")
    retry_exponential_base: float = Field(2.0, ge=1.1, le=5.0, description="Exponential backoff base")
    timeout_ms: int = Field(30000, ge=1000, le=300000, description="Request timeout")
    circuit_breaker_threshold: int = Field(5, ge=1, le=50, description="Circuit breaker failure threshold")
    circuit_breaker_reset_timeout_ms: int = Field(60000, ge=10000, le=600000, description="Circuit breaker reset timeout")