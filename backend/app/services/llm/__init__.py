"""
LLM Service Package

Direct LLM integration without proxy dependencies.
Provides secure, efficient access to LLM providers with integrated security.
"""

from .exceptions import LLMError, ProviderError, SecurityError
from .models import ChatRequest, ChatResponse, EmbeddingRequest, EmbeddingResponse
from .service import LLMService, llm_service

__all__ = [
    "LLMService",
    "llm_service",
    "ChatRequest",
    "ChatResponse",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "LLMError",
    "ProviderError",
    "SecurityError",
]
