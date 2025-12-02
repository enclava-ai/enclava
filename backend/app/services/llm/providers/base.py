"""
Base LLM Provider Interface

Abstract base class for all LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging

from ..models import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelInfo,
    ProviderStatus,
)
from ..config import ProviderConfig

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, config: ProviderConfig, api_key: str):
        """
        Initialize provider

        Args:
            config: Provider configuration
            api_key: Decrypted API key for the provider
        """
        self.config = config
        self.api_key = api_key
        self.name = config.name
        self._session = None

        logger.info(f"Initializing {self.name} provider")

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name"""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """
        Check provider health status

        Returns:
            ProviderStatus with current health information
        """
        pass

    @abstractmethod
    async def get_models(self) -> List[ModelInfo]:
        """
        Get list of available models

        Returns:
            List of available models with their capabilities
        """
        pass

    @abstractmethod
    async def create_chat_completion(self, request: ChatRequest) -> ChatResponse:
        """
        Create chat completion

        Args:
            request: Chat completion request

        Returns:
            Chat completion response

        Raises:
            ProviderError: If provider-specific error occurs
            SecurityError: If security validation fails
            ValidationError: If request validation fails
        """
        pass

    @abstractmethod
    async def create_chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create streaming chat completion

        Args:
            request: Chat completion request with stream=True

        Yields:
            Streaming response chunks

        Raises:
            ProviderError: If provider-specific error occurs
            SecurityError: If security validation fails
            ValidationError: If request validation fails
        """
        pass

    @abstractmethod
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        Create embeddings

        Args:
            request: Embedding generation request

        Returns:
            Embedding response

        Raises:
            ProviderError: If provider-specific error occurs
            SecurityError: If security validation fails
            ValidationError: If request validation fails
        """
        pass

    async def initialize(self):
        """Initialize provider resources (override if needed)"""
        pass

    async def cleanup(self):
        """Cleanup provider resources"""
        if self._session and hasattr(self._session, "close"):
            await self._session.close()
            logger.debug(f"Cleaned up session for {self.name} provider")

    def supports_model(self, model_name: str) -> bool:
        """Check if provider supports a specific model"""
        return model_name in self.config.supported_models

    def supports_capability(self, capability: str) -> bool:
        """Check if provider supports a specific capability"""
        return capability in self.config.capabilities

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get information about a specific model (override for provider-specific info)"""
        if not self.supports_model(model_name):
            return None

        return ModelInfo(
            id=model_name,
            object="model",
            owned_by=self.name,
            provider=self.name,
            capabilities=self.config.capabilities,
            context_window=self.config.max_context_window,
            max_output_tokens=self.config.max_output_tokens,
            supports_streaming=self.config.supports_streaming,
            supports_function_calling=self.config.supports_function_calling,
        )

    def _validate_request(self, request: Any):
        """Base request validation (override for provider-specific validation)"""
        if hasattr(request, "model") and not self.supports_model(request.model):
            from ..exceptions import ValidationError

            raise ValidationError(
                f"Model '{request.model}' not supported by provider '{self.name}'",
                field="model",
            )

    def _create_headers(
        self, additional_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Create HTTP headers for requests"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": f"Enclava-LLM-Service/{self.name}",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _handle_http_error(
        self, status_code: int, response_text: str, provider_context: str = ""
    ):
        """Handle HTTP errors consistently across providers"""
        from ..exceptions import ProviderError, RateLimitError, ValidationError

        context = f"{self.name} {provider_context}".strip()

        if status_code == 401:
            raise ProviderError(
                f"Authentication failed for {context}",
                provider=self.name,
                error_code="AUTHENTICATION_ERROR",
                details={"status_code": status_code, "response": response_text},
            )
        elif status_code == 403:
            raise ProviderError(
                f"Access forbidden for {context}",
                provider=self.name,
                error_code="AUTHORIZATION_ERROR",
                details={"status_code": status_code, "response": response_text},
            )
        elif status_code == 429:
            raise RateLimitError(
                f"Rate limit exceeded for {context}",
                error_code="RATE_LIMIT_ERROR",
                details={
                    "status_code": status_code,
                    "response": response_text,
                    "provider": self.name,
                },
            )
        elif status_code == 400:
            raise ValidationError(
                f"Bad request for {context}: {response_text}",
                error_code="BAD_REQUEST",
                details={"status_code": status_code, "response": response_text},
            )
        elif 500 <= status_code < 600:
            raise ProviderError(
                f"Server error for {context}: {response_text}",
                provider=self.name,
                error_code="SERVER_ERROR",
                details={"status_code": status_code, "response": response_text},
            )
        else:
            raise ProviderError(
                f"HTTP error {status_code} for {context}: {response_text}",
                provider=self.name,
                error_code="HTTP_ERROR",
                details={"status_code": status_code, "response": response_text},
            )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, enabled={self.config.enabled})"
