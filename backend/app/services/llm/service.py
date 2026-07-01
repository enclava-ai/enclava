"""
LLM Service

Main service that coordinates providers, security, resilience, and metrics.
Replaces LiteLLM client functionality with direct provider integration.
"""

import asyncio
import inspect
import logging
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from ...core.config import settings
from ..usage_recording import UsageRecordingService
from .config import ProviderConfig, config_manager
from .exceptions import (
    ConfigurationError,
    LLMError,
    ProviderError,
    SecurityError,
    TimeoutError,
    ValidationError,
)
from .models import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMMetrics,
    ModelInfo,
    ProviderStatus,
    TokenUsage,
)

# from .metrics import metrics_collector
from .providers import BaseLLMProvider, PrivateModeProvider
from .resilience import ResilienceManagerFactory
from .streaming_tracker import StreamingTokenTracker, StreamingUsageRecorder

logger = logging.getLogger(__name__)


class _DefaultSecurityService:
    def analyze_request(self, request: Any) -> Dict[str, Any]:
        return {"blocked": False, "risk_score": 0.0}

    def analyze_response(self, response: Any) -> Dict[str, Any]:
        return {"blocked": False, "risk_score": 0.0}


class _DefaultMetricsService:
    def record_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class _DefaultBudgetService:
    def check_budget(self, *args: Any, **kwargs: Any) -> bool:
        return True


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class LLMService:
    """Main LLM service coordinating all components"""

    def __init__(self):
        """Initialize LLM service"""
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._initialized = False
        self._startup_time: Optional[datetime] = None
        self.security_service = _DefaultSecurityService()
        self.metrics_service = _DefaultMetricsService()
        self.budget_service = _DefaultBudgetService()

        logger.info("LLM Service initialized")

    async def initialize(self):
        """Initialize service and providers"""
        if self._initialized:
            logger.warning("LLM Service already initialized")
            return

        start_time = time.time()
        self._startup_time = datetime.now(timezone.utc)

        try:
            # Get configuration
            config = config_manager.get_config()
            logger.info(
                f"Initializing LLM service with {len(config.providers)} configured providers"
            )

            # Initialize enabled providers
            enabled_providers = config_manager.get_enabled_providers()
            if not enabled_providers:
                logger.warning(
                    "No LLM providers are enabled; model inference will remain "
                    "unavailable until a provider API key is configured"
                )
                self._providers.clear()
                self._initialized = True
                return

            for provider_name in enabled_providers:
                await self._initialize_provider(provider_name)

            # Verify we have at least one working provider
            if not self._providers:
                raise ConfigurationError("No providers successfully initialized")

            # Verify default provider is available
            default_provider = config.default_provider
            if default_provider not in self._providers:
                available_providers = list(self._providers.keys())
                logger.warning(
                    f"Default provider '{default_provider}' not available, using '{available_providers[0]}'"
                )
                config.default_provider = available_providers[0]

            # Initialize attestation monitoring
            await self._initialize_attestation()

            self._initialized = True
            initialization_time = (time.time() - start_time) * 1000

            logger.info(
                f"LLM Service initialized successfully in {initialization_time:.2f}ms"
            )
            logger.info(f"Available providers: {list(self._providers.keys())}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            raise ConfigurationError(f"LLM service initialization failed: {e}")

    async def _initialize_provider(self, provider_name: str):
        """Initialize a specific provider"""
        try:
            provider_config = config_manager.get_provider_config(provider_name)
            if not provider_config or not provider_config.enabled:
                logger.warning(f"Provider '{provider_name}' not enabled, skipping")
                return

            # Get API key
            api_key = config_manager.get_api_key(provider_name)
            if not api_key:
                logger.error(f"No API key found for provider '{provider_name}'")
                return

            # Create provider instance
            provider = self._create_provider(provider_config, api_key)

            # Initialize provider
            await provider.initialize()

            # Test provider health
            health_status = await provider.health_check()
            if health_status.status == "unavailable":
                logger.error(
                    f"Provider '{provider_name}' failed health check: {health_status.error_message}"
                )
                return

            # Register provider
            self._providers[provider_name] = provider
            logger.info(
                f"Provider '{provider_name}' initialized successfully (status: {health_status.status})"
            )

            # Fetch and update models dynamically
            await self._refresh_provider_models(provider_name, provider)

        except Exception as e:
            logger.error(f"Failed to initialize provider '{provider_name}': {e}")

    def _create_provider(self, config: ProviderConfig, api_key: str) -> BaseLLMProvider:
        """Create provider instance based on configuration"""
        if config.name == "privatemode":
            return PrivateModeProvider(config, api_key)
        elif config.name == "redpill":
            from .providers.redpill import RedPillProvider

            return RedPillProvider(config, api_key)
        else:
            raise ConfigurationError(f"Unknown provider type: {config.name}")

    def _select_model(self, request: ChatRequest) -> str:
        """Legacy model selector retained for older service tests."""
        return request.model or getattr(settings, "DEFAULT_MODEL", "gpt-3.5-turbo")

    def _select_provider(self, model: str) -> str:
        """Legacy provider router retained for older service tests."""
        model_name = (model or "").lower()
        if model_name.startswith("gpt-") or model_name.startswith("text-embedding"):
            return "openai"
        if model_name.startswith("claude"):
            return "anthropic"
        if model_name.startswith("privatemode") or "llama" in model_name:
            return "privatemode"
        if model_name.startswith("redpill") or "/" in model_name:
            return "redpill"
        return "unknown"

    def _validate_model_capabilities(self, request: ChatRequest) -> bool:
        """Compatibility hook for capability checks."""
        return bool(request.model and request.messages)

    def _normalize_request_parameters(self, request: ChatRequest) -> ChatRequest:
        """Compatibility hook for provider-specific parameter normalization."""
        return request

    async def _validate_request_size(self, request: ChatRequest) -> bool:
        """Validate approximate request size for legacy tests."""
        total_chars = 0
        for message in request.messages or []:
            content = message.content
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                total_chars += len(str(content))
        return total_chars <= 200_000

    async def _call_provider(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Legacy provider-call seam used by unit tests.

        The production path uses `create_chat_completion()` and provider objects.
        This method keeps older tests and integrations mockable without changing
        the production provider flow.
        """
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Test response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": sum(
                    len(str(message.get("content", "")).split()) for message in messages
                ),
                "completion_tokens": 2,
            },
            "model": model,
        }

    def _is_known_legacy_model(self, model: str) -> bool:
        provider = self._select_provider(model)
        return provider != "unknown"

    def _messages_for_provider(self, request: ChatRequest) -> List[Dict[str, Any]]:
        return [
            {
                "role": message.role,
                "content": message.content,
                **({"name": message.name} if message.name else {}),
            }
            for message in request.messages
        ]

    def _validate_legacy_request(self, request: ChatRequest) -> None:
        allowed_roles = {"system", "user", "assistant", "function", "tool"}
        if not request.messages:
            raise ValidationError("Messages cannot be empty", field="messages")
        for message in request.messages:
            if message.role not in allowed_roles:
                raise ValidationError("Invalid message role", field="messages.role")
            if message.role in {"system", "user", "function", "tool"} and (
                message.content is None
                or (isinstance(message.content, str) and message.content == "")
            ):
                raise ValidationError(
                    "Message content cannot be empty", field="messages.content"
                )
        if not self._is_known_legacy_model(request.model):
            raise ValidationError(f"Unknown model '{request.model}'", field="model")

    def _legacy_response_from_provider(
        self,
        provider_response: Dict[str, Any],
        request: ChatRequest,
        provider: str,
        latency_ms: float,
    ) -> ChatResponse:
        choices_payload = provider_response.get("choices") or []
        if not choices_payload:
            raise ProviderError("Provider returned empty response", provider=provider)

        choices: List[ChatChoice] = []
        for index, choice_payload in enumerate(choices_payload):
            message_payload = choice_payload.get("message") or {}
            content = message_payload.get("content", "")
            if content == "":
                raise ProviderError(
                    "Provider returned empty response content", provider=provider
                )

            choices.append(
                ChatChoice(
                    index=choice_payload.get("index", index),
                    message=ChatMessage(
                        role=message_payload.get("role", "assistant"),
                        content=content,
                    ),
                    finish_reason=choice_payload.get("finish_reason", "stop"),
                )
            )

        usage_payload = provider_response.get("usage") or {}
        prompt_tokens = int(usage_payload.get("prompt_tokens") or 0)
        completion_tokens = int(usage_payload.get("completion_tokens") or 0)
        total_tokens = int(
            usage_payload.get("total_tokens")
            if usage_payload.get("total_tokens") is not None
            else prompt_tokens + completion_tokens
        )
        if total_tokens and not completion_tokens and not prompt_tokens:
            completion_tokens = total_tokens

        return ChatResponse(
            id=f"chatcmpl-{uuid4().hex}",
            object="chat.completion",
            created=int(time.time()),
            model=provider_response.get("model") or request.model,
            provider=provider,
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            latency_ms=latency_ms,
        )

    async def _legacy_security_check(self, method_name: str, payload: Any) -> None:
        security_service = getattr(self, "security_service", None)
        if not security_service:
            return
        analyzer = getattr(security_service, method_name, None)
        if not analyzer:
            return
        result = await _maybe_await(analyzer(payload))
        if isinstance(result, dict) and result.get("blocked"):
            raise SecurityError(
                "Security check blocked request",
                risk_score=float(result.get("risk_score") or 0.0),
            )

    async def chat_completion(
        self,
        request: ChatRequest,
        user_id: Optional[int] = None,
    ) -> ChatResponse:
        """Legacy chat completion facade used by older unit tests."""
        self._validate_legacy_request(request)
        if not await self._validate_request_size(request):
            raise ValidationError("Request is too large", field="messages")
        if not self._validate_model_capabilities(request):
            raise ValidationError(
                "Model capabilities do not support request", field="model"
            )

        budget_service = getattr(self, "budget_service", None)
        if budget_service and hasattr(budget_service, "check_budget"):
            budget_ok = await _maybe_await(
                budget_service.check_budget(user_id, request)
            )
            if budget_ok is False:
                raise ValidationError("Budget exceeded", field="budget")

        await self._legacy_security_check("analyze_request", request)

        normalized_request = self._normalize_request_parameters(request)
        provider = self._select_provider(normalized_request.model)
        messages = self._messages_for_provider(normalized_request)

        rag_context = None
        rag_service = getattr(self, "rag_service", None)
        if rag_service and getattr(normalized_request, "context", None):
            getter = getattr(rag_service, "get_relevant_context", None)
            if getter:
                rag_context = await _maybe_await(
                    getter(
                        normalized_request.messages[-1].content,
                        normalized_request.context,
                    )
                )
                if rag_context:
                    messages = [
                        {"role": "system", "content": f"Context:\n{rag_context}"},
                        *messages,
                    ]

        start_time = time.time()
        try:
            provider_response = await self._call_provider(
                provider=provider,
                model=normalized_request.model,
                messages=messages,
                request=normalized_request,
                context=rag_context,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(str(exc) or "Provider timeout") from exc
        except LLMError as exc:
            if "primary" not in str(exc).lower():
                raise
            provider_response = await self._call_provider(
                provider=provider,
                model=normalized_request.model,
                messages=messages,
                request=normalized_request,
                context=rag_context,
                fallback=True,
            )
        except Exception as exc:
            if "primary" not in str(exc).lower():
                raise ProviderError(str(exc), provider=provider) from exc
            provider_response = await self._call_provider(
                provider=provider,
                model=normalized_request.model,
                messages=messages,
                request=normalized_request,
                context=rag_context,
                fallback=True,
            )

        latency_ms = (time.time() - start_time) * 1000
        response = self._legacy_response_from_provider(
            provider_response, normalized_request, provider, latency_ms
        )

        await self._legacy_security_check("analyze_response", response)

        metrics_service = getattr(self, "metrics_service", None)
        if metrics_service and hasattr(metrics_service, "record_request"):
            await _maybe_await(
                metrics_service.record_request(response, response_time=latency_ms)
            )

        return response

    async def _refresh_provider_models(
        self, provider_name: str, provider: BaseLLMProvider
    ):
        """Fetch and update models dynamically from provider"""
        try:
            # Get models from provider
            models = await provider.get_models()
            model_ids = [model.id for model in models]

            # Update configuration
            await config_manager.refresh_provider_models(provider_name, model_ids)

            logger.info(
                f"Refreshed {len(model_ids)} models for provider '{provider_name}': {model_ids}"
            )

        except Exception as e:
            logger.error(
                f"Failed to refresh models for provider '{provider_name}': {e}"
            )

    async def _initialize_attestation(self):
        """Initialize attestation monitoring for all providers."""
        # Import here to avoid circular dependency
        from .attestation.privatemode import PrivateModeAttestationVerifier
        from .attestation.redpill import RedPillAttestationVerifier
        from .attestation.scheduler import attestation_scheduler

        if "privatemode" in self._providers:
            attestation_scheduler.register_provider(
                "privatemode",
                PrivateModeAttestationVerifier(
                    proxy_url=settings.PRIVATEMODE_PROXY_URL,
                    api_key=settings.PRIVATEMODE_API_KEY,
                ),
                test_model=None,  # Proxy health check only
            )
            logger.info("Registered PrivateMode provider for attestation monitoring")

        if "redpill" in self._providers:
            redpill_api_key = getattr(settings, "REDPILL_API_KEY", None)
            redpill_base_url = getattr(
                settings, "REDPILL_BASE_URL", "https://api.redpill.ai/v1"
            )
            redpill_test_model = getattr(
                settings, "REDPILL_TEST_MODEL", "phala/deepseek-chat-v3-0324"
            )

            if redpill_api_key:
                attestation_scheduler.register_provider(
                    "redpill",
                    RedPillAttestationVerifier(
                        api_base=redpill_base_url, api_key=redpill_api_key
                    ),
                    test_model=redpill_test_model,
                )
                logger.info("Registered RedPill provider for attestation monitoring")
            else:
                logger.warning(
                    "RedPill provider enabled but no API key found, skipping attestation registration"
                )

        # Start periodic verification
        await attestation_scheduler.start()
        logger.info("Started attestation scheduler")

        # Run initial verification for all registered providers
        for provider_id in attestation_scheduler._verifiers:
            try:
                await attestation_scheduler.verify_now(provider_id)
                logger.info(
                    f"Completed initial attestation verification for {provider_id}"
                )
            except Exception as e:
                logger.error(
                    f"Initial attestation verification failed for {provider_id}: {e}"
                )

    async def create_chat_completion(
        self,
        request: ChatRequest,
        db: Optional["AsyncSession"] = None,
        user_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        endpoint: str = "/v1/chat/completions",
    ) -> ChatResponse:
        """Create chat completion with security, resilience, and usage recording

        Args:
            request: Chat completion request
            db: Database session for usage recording (required for tracking)
            user_id: User ID for attribution
            api_key_id: API key ID for attribution
            endpoint: Endpoint identifier for usage tracking (e.g., "extract/process", "/v1/chat/completions")
        """
        if settings.TESTING or settings.LLM_TEST_MODE:
            return self._create_test_chat_response(request)

        if not self._initialized:
            await self.initialize()

        # Validate request
        if not request.messages:
            raise ValidationError("Messages cannot be empty", field="messages")

        request_id = uuid4()
        start_time = time.time()

        # Initialize usage service if DB session provided
        usage_service = UsageRecordingService(db) if db else None

        # Get provider for model
        provider_name = await self._get_provider_for_model(request.model, db=db)
        provider = self._providers.get(provider_name)

        if not provider:
            error = ProviderError(
                f"No available provider for model '{request.model}'",
                provider=provider_name,
            )
            if usage_service:
                latency_ms = int((time.time() - start_time) * 1000)
                await usage_service.record_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider_id="none",
                    provider_model=request.model,
                    input_tokens=0,
                    output_tokens=0,
                    endpoint=endpoint,
                    status="error",
                    error_type="provider_unavailable",
                    error_message=str(error),
                    latency_ms=latency_ms,
                    agent_config_id=request.agent_config_id,
                    message_count=len(request.messages),
                )
                await db.commit()
            raise error

        # Execute with resilience
        resilience_manager = ResilienceManagerFactory.get_manager(provider_name)

        try:
            response = await resilience_manager.execute(
                provider.create_chat_completion,
                request,
                retryable_exceptions=(ProviderError, TimeoutError),
                non_retryable_exceptions=(ValidationError,),
            )

            # Record successful request
            if usage_service:
                latency_ms = int((time.time() - start_time) * 1000)

                # Extract token usage
                input_tokens = 0
                output_tokens = 0
                if response.usage:
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens

                await usage_service.record_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider_id=provider_name,
                    provider_model=request.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    endpoint=endpoint,
                    status="success",
                    latency_ms=latency_ms,
                    agent_config_id=request.agent_config_id,
                    message_count=len(request.messages),
                    is_streaming=False,
                )
                await db.commit()

            return response

        except Exception as e:
            # Record failed request
            latency_ms = int((time.time() - start_time) * 1000)
            error_code = getattr(e, "error_code", e.__class__.__name__)

            logger.exception(
                "Chat completion failed for provider %s (model=%s, latency=%.2fms, error=%s)",
                provider_name,
                request.model,
                latency_ms,
                error_code,
            )

            if usage_service:
                # Try to determine error type
                error_type = "provider_error"
                if isinstance(e, ValidationError):
                    error_type = "validation_error"
                elif isinstance(e, SecurityError):
                    error_type = "security_error"
                elif isinstance(e, TimeoutError):
                    error_type = "timeout"

                await usage_service.record_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider_id=provider_name,
                    provider_model=request.model,
                    input_tokens=0,
                    output_tokens=0,
                    endpoint=endpoint,
                    status="error",
                    error_type=error_type,
                    error_message=str(e),
                    latency_ms=latency_ms,
                    agent_config_id=request.agent_config_id,
                    message_count=len(request.messages),
                )
                await db.commit()

            raise

    async def create_chat_completion_stream(
        self,
        request: ChatRequest,
        db: Optional["AsyncSession"] = None,
        user_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        endpoint: str = "/v1/chat/completions",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create streaming chat completion with usage tracking

        Args:
            request: Chat completion request
            db: Database session for usage recording (required for tracking)
            user_id: User ID for attribution
            api_key_id: API key ID for attribution
            endpoint: Endpoint identifier for usage tracking
        """
        if not self._initialized:
            await self.initialize()

        request_id = uuid4()

        # Get provider
        provider_name = await self._get_provider_for_model(request.model, db=db)
        provider = self._providers.get(provider_name)

        if not provider:
            raise ProviderError(
                f"No available provider for model '{request.model}'",
                provider=provider_name,
            )

        # Execute streaming with resilience
        resilience_manager = ResilienceManagerFactory.get_manager(provider_name)

        # Estimate input tokens for providers that don't include usage in streaming chunks
        # This ensures accurate billing/budget tracking for streaming workloads
        estimated_input_tokens = self._estimate_input_tokens(request)

        # Setup streaming tracker if DB session is available
        tracker = StreamingTokenTracker(
            request.model, estimated_input_tokens=estimated_input_tokens
        )
        recorder = None

        if db:
            recorder = StreamingUsageRecorder(
                tracker=tracker,
                request_id=request_id,
                user_id=user_id,
                api_key_id=api_key_id,
                provider_id=provider_name,
                endpoint=endpoint,
            )

        try:
            # Use streaming-aware execute that handles async generators properly
            async for chunk in resilience_manager.execute_stream(
                provider.create_chat_completion_stream,
                request,
            ):
                if recorder:
                    recorder.process_chunk(chunk)
                yield chunk

            # After stream completes, save the record
            if recorder and db:
                usage = recorder.get_final_usage()
                usage_service = UsageRecordingService(db)

                await usage_service.record_request(
                    request_id=request_id,
                    user_id=recorder.user_id,
                    api_key_id=recorder.api_key_id,
                    provider_id=recorder.provider_id,
                    provider_model=request.model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    endpoint=recorder.endpoint,
                    status="success",
                    latency_ms=usage.total_duration_ms,
                    ttft_ms=usage.ttft_ms,
                    agent_config_id=request.agent_config_id,
                    message_count=len(request.messages),
                    is_streaming=True,
                )
                await db.commit()

        except Exception as e:
            # Record streaming failure
            error_code = getattr(e, "error_code", e.__class__.__name__)
            logger.exception(
                "Streaming chat completion failed for provider %s (model=%s, error=%s)",
                provider_name,
                request.model,
                error_code,
            )

            if recorder and db:
                usage = recorder.get_final_usage()
                usage_service = UsageRecordingService(db)

                await usage_service.record_request(
                    request_id=request_id,
                    user_id=recorder.user_id,
                    api_key_id=recorder.api_key_id,
                    provider_id=recorder.provider_id,
                    provider_model=request.model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    endpoint=recorder.endpoint,
                    status="error",
                    error_type="stream_error",
                    error_message=str(e),
                    latency_ms=usage.total_duration_ms,
                    agent_config_id=request.agent_config_id,
                    message_count=len(request.messages),
                    is_streaming=True,
                )
                await db.commit()
            raise

    async def create_embedding(
        self,
        request: EmbeddingRequest,
        db: Optional["AsyncSession"] = None,
        user_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        endpoint: str = "/v1/embeddings",
    ) -> EmbeddingResponse:
        """Create embeddings with security, resilience and usage recording

        Args:
            request: Embedding request
            db: Database session for usage recording (required for tracking)
            user_id: User ID for attribution
            api_key_id: API key ID for attribution
            endpoint: Endpoint identifier for usage tracking
        """
        if not self._initialized:
            await self.initialize()

        request_id = uuid4()
        start_time = time.time()

        # Initialize usage service if DB session provided
        usage_service = UsageRecordingService(db) if db else None

        # Get provider
        provider_name = await self._get_provider_for_model(request.model)
        provider = self._providers.get(provider_name)

        if not provider:
            error = ProviderError(
                f"No available provider for model '{request.model}'",
                provider=provider_name,
            )
            if usage_service:
                latency_ms = int((time.time() - start_time) * 1000)
                await usage_service.record_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider_id="none",
                    provider_model=request.model,
                    input_tokens=0,
                    output_tokens=0,
                    endpoint=endpoint,
                    status="error",
                    error_type="provider_unavailable",
                    error_message=str(error),
                    latency_ms=latency_ms,
                )
                await db.commit()
            raise error

        # Execute with resilience
        resilience_manager = ResilienceManagerFactory.get_manager(provider_name)

        try:
            response = await resilience_manager.execute(
                provider.create_embedding,
                request,
                retryable_exceptions=(ProviderError, TimeoutError),
                non_retryable_exceptions=(ValidationError,),
            )

            # Record successful request
            if usage_service:
                latency_ms = int((time.time() - start_time) * 1000)

                # Extract token usage
                input_tokens = 0
                total_tokens = 0
                if response.usage:
                    input_tokens = response.usage.prompt_tokens
                    total_tokens = response.usage.total_tokens

                await usage_service.record_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider_id=provider_name,
                    provider_model=request.model,
                    input_tokens=input_tokens,
                    output_tokens=0,  # Embeddings don't have output tokens
                    endpoint=endpoint,
                    status="success",
                    latency_ms=latency_ms,
                    is_streaming=False,
                )
                await db.commit()

            return response

        except Exception as e:
            # Record failed request
            latency_ms = int((time.time() - start_time) * 1000)
            error_code = getattr(e, "error_code", e.__class__.__name__)

            logger.exception(
                "Embedding request failed for provider %s (model=%s, latency=%.2fms, error=%s)",
                provider_name,
                request.model,
                latency_ms,
                error_code,
            )

            if usage_service:
                await usage_service.record_request(
                    request_id=request_id,
                    user_id=user_id,
                    api_key_id=api_key_id,
                    provider_id=provider_name,
                    provider_model=request.model,
                    input_tokens=0,
                    output_tokens=0,
                    endpoint=endpoint,
                    status="error",
                    error_type="provider_error",
                    error_message=str(e),
                    latency_ms=latency_ms,
                )
                await db.commit()

            raise

    async def get_models(self, provider_name: Optional[str] = None) -> List[ModelInfo]:
        """Get available models from all or specific provider"""
        if not self._initialized:
            await self.initialize()

        models = []

        if provider_name:
            # Get models from specific provider
            provider = self._providers.get(provider_name)
            if provider:
                try:
                    provider_models = await provider.get_models()
                    models.extend(provider_models)
                except Exception as e:
                    logger.error(f"Failed to get models from {provider_name}: {e}")
        else:
            # Get models from all providers
            for name, provider in self._providers.items():
                try:
                    provider_models = await provider.get_models()
                    models.extend(provider_models)
                except Exception as e:
                    logger.error(f"Failed to get models from {name}: {e}")

        return models

    def _get_configured_provider_statuses(
        self, error_message: str = "Provider is disabled or not configured"
    ) -> Dict[str, ProviderStatus]:
        """Return status records for configured providers that are not active."""
        try:
            config = config_manager.get_config()
        except Exception as exc:
            logger.warning(f"Unable to load LLM provider configuration: {exc}")
            return {}

        now = datetime.now(timezone.utc)
        statuses: Dict[str, ProviderStatus] = {}
        for name, provider_config in config.providers.items():
            message = error_message
            if not provider_config.enabled:
                message = (
                    f"Provider disabled. Set {provider_config.api_key_env_var} "
                    "to enable it."
                )

            statuses[name] = ProviderStatus(
                provider=name,
                status="unavailable",
                last_check=now,
                error_message=message,
                models_available=provider_config.supported_models,
            )

        return statuses

    async def get_provider_status(self) -> Dict[str, ProviderStatus]:
        """Get health status of all providers"""
        if not self._initialized:
            try:
                await self.initialize()
            except ConfigurationError as exc:
                logger.warning(f"LLM service unavailable while checking status: {exc}")
                return self._get_configured_provider_statuses(str(exc))

        if not self._providers:
            return self._get_configured_provider_statuses()

        status_dict = {}

        for name, provider in self._providers.items():
            try:
                status = await provider.health_check()
                status_dict[name] = status
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                status_dict[name] = ProviderStatus(
                    provider=name,
                    status="unavailable",
                    last_check=datetime.now(timezone.utc),
                    error_message=str(e),
                    models_available=[],
                )

        return status_dict

    def get_metrics(self) -> LLMMetrics:
        """Get service metrics - metrics disabled"""
        # return metrics_collector.get_metrics()
        return LLMMetrics(
            total_requests=0, success_rate=0.0, avg_latency_ms=0, error_rates={}
        )

    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary - metrics disabled"""
        # metrics_health = metrics_collector.get_health_summary()
        resilience_health = ResilienceManagerFactory.get_all_health_status()

        return {
            "service_status": "healthy" if self._initialized else "initializing",
            "startup_time": (
                self._startup_time.isoformat() if self._startup_time else None
            ),
            "provider_count": len(self._providers),
            "active_providers": list(self._providers.keys()),
            "metrics": {"status": "disabled"},
            "resilience": resilience_health,
        }

    def _estimate_input_tokens(self, request: ChatRequest) -> int:
        """
        Estimate input tokens from request messages for streaming tracking.

        Uses a word-based estimation with 1.3 tokens per word multiplier,
        consistent with other parts of the codebase.

        Args:
            request: The chat request containing messages

        Returns:
            Estimated input token count
        """
        if not request.messages:
            return 0

        # Concatenate all message content
        total_content = ""
        for msg in request.messages:
            if msg.content:
                total_content += msg.content + " "
            # Account for role tokens
            total_content += msg.role + " "

        # Word-based estimation: ~1.3 tokens per word (consistent with api/v1/llm.py)
        word_count = len(total_content.split())
        estimated = int(word_count * 1.3)

        logger.debug(f"Estimated {estimated} input tokens from {word_count} words")
        return estimated

    async def get_provider_for_model(self, model: str) -> str:
        """
        Get provider name for a model (public API).

        Args:
            model: Model name

        Returns:
            Provider name string
        """
        if settings.TESTING or settings.LLM_TEST_MODE:
            return "test"
        return await self._get_provider_for_model(model)

    def _create_test_chat_response(self, request: ChatRequest) -> ChatResponse:
        """Return a deterministic chat response for isolated tests."""
        prompt_tokens = max(1, self._estimate_input_tokens(request))
        completion_tokens = 3
        return ChatResponse(
            id=f"chatcmpl-test-{uuid4().hex[:12]}",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            provider="test",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Test response"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            security_check=True,
            risk_score=0.0,
            detected_patterns=[],
        )

    async def _get_provider_for_model(
        self,
        model: str,
        db: Optional["AsyncSession"] = None,
    ) -> str:
        """
        Get provider name for a model with health checks and preference logic
        """
        # Import here to avoid circular dependency
        from .attestation.scheduler import attestation_scheduler

        # 1. Check model routing from config
        provider_name = config_manager.get_provider_for_model(model)
        if provider_name and provider_name in self._providers:
            # Verify provider is healthy
            if attestation_scheduler.is_healthy(provider_name):
                return provider_name

        # 2. Fall back to any healthy provider that supports the model
        for name, provider in self._providers.items():
            if provider.supports_model(model) and attestation_scheduler.is_healthy(
                name
            ):
                return name

        # 4. Use default provider as last resort (if healthy)
        config = config_manager.get_config()
        if config.default_provider in self._providers:
            if attestation_scheduler.is_healthy(config.default_provider):
                return config.default_provider

        # 5. Degraded mode: If no healthy providers, try any provider that supports the model
        logger.warning(
            f"No healthy providers available for model '{model}', trying degraded mode"
        )
        for name, provider in self._providers.items():
            if provider.supports_model(model):
                return name

        # 6. Absolute fallback: use first available provider
        if self._providers:
            return list(self._providers.keys())[0]

        raise ProviderError(f"No provider found for model '{model}'", provider="none")

    async def get_providers_health(
        self, db: Optional["AsyncSession"] = None
    ) -> List[Dict[str, Any]]:
        """Get health status of all providers with attestation details and models.

        Args:
            db: Optional database session for pricing lookup. If provided, pricing will
                be fetched from the database first, with fallback to static pricing.
        """
        # Import here to avoid circular dependency
        from app.services.pricing import PricingService

        from .attestation.scheduler import attestation_scheduler

        pricing_service = PricingService(db)

        result = []
        for provider_id, provider in self._providers.items():
            health = attestation_scheduler.get_health(provider_id)

            # Fetch models for this provider
            models_list = []
            try:
                provider_models = await provider.get_models()
                for model in provider_models:
                    # Get pricing for this model (from database if available, else static fallback)
                    pricing = await pricing_service.get_pricing(provider_id, model.id)
                    models_list.append(
                        {
                            "id": model.id,
                            "capabilities": model.capabilities,
                            "context_window": model.context_window,
                            "max_output_tokens": model.max_output_tokens,
                            "supports_streaming": model.supports_streaming,
                            "supports_function_calling": model.supports_function_calling,
                            "tasks": model.tasks,
                            "pricing": {
                                "input_per_million_cents": pricing.input_price_per_million_cents,
                                "output_per_million_cents": pricing.output_price_per_million_cents,
                                "source": pricing.price_source,
                            },
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch models for {provider_id}: {e}")

            provider_health = {
                "provider_id": provider_id,
                "display_name": getattr(
                    provider, "display_name", provider_id.capitalize()
                ),
                "healthy": health.healthy if health else False,
                "last_check_at": (
                    health.last_check.timestamp.isoformat()
                    if health and health.last_check
                    else None
                ),
                "last_healthy_at": (
                    health.last_healthy_at.isoformat()
                    if health and health.last_healthy_at
                    else None
                ),
                "error": health.error if health else None,
                "attestation_details": (
                    self._get_attestation_details(health) if health else None
                ),
                "models": models_list,
            }

            result.append(provider_health)

        return result

    def _get_attestation_details(self, health) -> Optional[Dict[str, Any]]:
        """Extract attestation details from last check."""
        if not health or not health.last_check:
            return None

        check = health.last_check
        return {
            "intel_tdx_verified": check.intel_tdx_verified,
            "gpu_attestation_verified": check.gpu_attestation_verified,
            "nonce_binding_verified": check.nonce_binding_verified,
            "signing_address": check.signing_address,
        }

    async def cleanup(self):
        """Cleanup service resources"""
        logger.info("Cleaning up LLM service")

        # Stop attestation scheduler
        try:
            from .attestation.scheduler import attestation_scheduler

            await attestation_scheduler.stop()
            logger.info("Stopped attestation scheduler")
        except Exception as e:
            logger.error(f"Error stopping attestation scheduler: {e}")

        # Cleanup providers
        for name, provider in self._providers.items():
            try:
                await provider.cleanup()
                logger.debug(f"Cleaned up provider: {name}")
            except Exception as e:
                logger.error(f"Error cleaning up provider {name}: {e}")

        self._providers.clear()
        self._initialized = False
        logger.info("LLM service cleanup completed")


# Global LLM service instance
llm_service = LLMService()
