"""
RedPill.ai LLM Provider

Integration with RedPill.ai confidential inference service.
Only exposes confidential models (phala/*, tinfoil/*, nearai/*).
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

import aiohttp

from ..config import ProviderConfig
from ..exceptions import ProviderError, TimeoutError, ValidationError
from ..models import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelInfo,
    ProviderStatus,
    TokenUsage,
)
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Only expose confidential models (full TEE)
CONFIDENTIAL_MODEL_PREFIXES = ("phala/", "tinfoil/", "nearai/")


class RedPillProvider(BaseLLMProvider):
    """RedPill.ai provider with confidential computing support"""

    def __init__(self, config: ProviderConfig, api_key: str):
        super().__init__(config, api_key)
        self.base_url = config.base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

        # TEE-specific settings
        self.verify_ssl = True  # Always verify SSL for security
        self.trust_env = False  # Don't trust environment proxy settings

        logger.info(f"RedPill provider initialized with base URL: {self.base_url}")

    @property
    def provider_name(self) -> str:
        return "redpill"

    @property
    def display_name(self) -> str:
        return "RedPill.ai (Confidential)"

    def is_available(self) -> bool:
        """Provider is available only if attestation is healthy."""
        # Import here to avoid circular dependency
        from ..attestation.scheduler import attestation_scheduler

        return attestation_scheduler.is_healthy(self.provider_name)

    def supports_model(self, model: str) -> bool:
        """Only support confidential models when healthy."""
        if not model.lower().startswith(CONFIDENTIAL_MODEL_PREFIXES):
            return False
        return self.is_available()

    def _is_confidential_model(self, model: str) -> bool:
        """Check if model is a confidential (full TEE) model."""
        return model.lower().startswith(CONFIDENTIAL_MODEL_PREFIXES)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with security settings"""
        if self._session is None or self._session.closed:
            # Create secure connector
            connector = aiohttp.TCPConnector(
                verify_ssl=self.verify_ssl,
                limit=100,  # Connection pool limit
                limit_per_host=50,
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
            )

            # Create session with security headers
            timeout = aiohttp.ClientTimeout(
                total=self.config.resilience.timeout_ms / 1000.0
            )

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self._create_headers(),
                trust_env=False,  # Don't trust environment variables
            )

            logger.debug("Created new secure HTTP session for RedPill")

        return self._session

    async def health_check(self) -> ProviderStatus:
        """Check RedPill.ai service health"""
        start_time = time.time()

        try:
            session = await self._get_session()

            # Use a lightweight endpoint for health check
            async with session.get(f"{self.base_url}/models") as response:
                latency = (time.time() - start_time) * 1000

                if response.status == 200:
                    models_data = await response.json()
                    # Filter to only confidential models
                    all_models = [
                        model.get("id", "") for model in models_data.get("data", [])
                    ]
                    confidential_models = [
                        m for m in all_models if self._is_confidential_model(m)
                    ]

                    return ProviderStatus(
                        provider=self.provider_name,
                        status="healthy",
                        latency_ms=latency,
                        success_rate=1.0,
                        last_check=datetime.now(timezone.utc),
                        models_available=confidential_models,
                    )
                else:
                    error_text = await response.text()
                    return ProviderStatus(
                        provider=self.provider_name,
                        status="degraded",
                        latency_ms=latency,
                        success_rate=0.0,
                        last_check=datetime.now(timezone.utc),
                        error_message=f"HTTP {response.status}: {error_text}",
                        models_available=[],
                    )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"RedPill health check failed: {e}")

            return ProviderStatus(
                provider=self.provider_name,
                status="unavailable",
                latency_ms=latency,
                success_rate=0.0,
                last_check=datetime.now(timezone.utc),
                error_message=str(e),
                models_available=[],
            )

    async def get_models(self) -> List[ModelInfo]:
        """Get only confidential models from RedPill.ai"""
        try:
            session = await self._get_session()

            async with session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    models_data = data.get("data", [])

                    models = []
                    for model_data in models_data:
                        model_id = model_data.get("id", "")
                        if not model_id:
                            continue

                        # Only include confidential models
                        if not self._is_confidential_model(model_id):
                            continue

                        # Extract all information directly from API response
                        # Redpill API uses input_modalities/output_modalities instead of tasks
                        input_modalities = model_data.get("input_modalities", [])
                        output_modalities = model_data.get("output_modalities", [])
                        supported_features = model_data.get("supported_features", [])
                        capabilities = []

                        # All RedPill confidential models have TEE capability
                        capabilities.append("tee")
                        capabilities.append("attestation")

                        # Add capabilities based on modalities
                        # Chat capability: model accepts text input and produces text output
                        if "text" in input_modalities and "text" in output_modalities:
                            capabilities.append("chat")

                        # Embeddings capability: check model name for embedding models
                        model_name_lower = model_id.lower()
                        if (
                            "embed" in model_name_lower
                            or "embedding" in model_name_lower
                        ):
                            capabilities.append("embeddings")

                        # Vision capability: model accepts image input
                        if "image" in input_modalities:
                            capabilities.append("vision")

                        # Function calling support: check supported_features or infer from model type
                        # Many modern models support function calling even if not explicitly listed
                        supports_function_calling = (
                            "function_calling" in supported_features
                            or "tools" in supported_features
                            or model_data.get("supports_function_calling", False)
                        )
                        if supports_function_calling:
                            capabilities.append("function_calling")

                        model_info = ModelInfo(
                            id=model_id,
                            object="model",
                            created=model_data.get("created", int(time.time())),
                            owned_by=model_data.get("owned_by", "redpill"),
                            provider=self.provider_name,
                            capabilities=capabilities,
                            # Redpill uses context_length instead of context_window
                            context_window=model_data.get("context_length")
                            or model_data.get("context_window"),
                            # Redpill uses max_output_length instead of max_output_tokens
                            max_output_tokens=model_data.get("max_output_length")
                            or model_data.get("max_output_tokens"),
                            # Streaming is generally supported by all models
                            supports_streaming=model_data.get(
                                "supports_streaming", True
                            ),
                            supports_function_calling=supports_function_calling,
                            # Store modalities for reference
                            tasks=input_modalities,  # Store input_modalities as tasks for compatibility
                        )
                        models.append(model_info)

                    logger.info(
                        f"Retrieved {len(models)} confidential models from RedPill"
                    )
                    return models
                else:
                    error_text = await response.text()
                    self._handle_http_error(
                        response.status, error_text, "models endpoint"
                    )
                    return []  # Never reached due to exception

        except Exception as e:
            if isinstance(e, ProviderError):
                raise

            logger.error(f"Failed to get models from RedPill: {e}")
            raise ProviderError(
                "Failed to retrieve models from RedPill",
                provider=self.provider_name,
                error_code="MODEL_RETRIEVAL_ERROR",
                details={"error": str(e)},
            )

    async def create_chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create chat completion via RedPill.ai (only for confidential models)"""
        self._validate_request(request)

        # Additional validation for confidential models
        if not self._is_confidential_model(request.model):
            raise ValidationError(
                f"Model {request.model} is not a confidential model",
                field="model",
            )

        # Check if provider is healthy
        if not self.is_available():
            # Import here to avoid circular dependency
            from ..attestation.scheduler import attestation_scheduler

            health = attestation_scheduler.get_health(self.provider_name)
            error_msg = health.error if health else "unknown"
            raise ProviderError(
                f"Provider unhealthy: {error_msg}",
                provider=self.provider_name,
                error_code="PROVIDER_UNHEALTHY",
            )

        start_time = time.time()

        try:
            session = await self._get_session()

            # Prepare request payload
            payload = {
                "model": request.model,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        **({"name": msg.name} if msg.name else {}),
                        **(
                            {
                                "tool_calls": [
                                    {
                                        "id": tc.id,
                                        "type": tc.type,
                                        "function": tc.function,
                                    }
                                    for tc in msg.tool_calls
                                ]
                            }
                            if msg.tool_calls
                            else {}
                        ),
                        **(
                            {"tool_call_id": msg.tool_call_id}
                            if msg.tool_call_id
                            else {}
                        ),
                    }
                    for msg in request.messages
                ],
                "temperature": request.temperature,
                "stream": False,  # Non-streaming version
            }

            # Add optional parameters
            if request.max_tokens is not None:
                payload["max_tokens"] = request.max_tokens
            if request.top_p is not None:
                payload["top_p"] = request.top_p
            if request.frequency_penalty is not None:
                payload["frequency_penalty"] = request.frequency_penalty
            if request.presence_penalty is not None:
                payload["presence_penalty"] = request.presence_penalty
            if request.stop is not None:
                payload["stop"] = request.stop
            if request.response_format is not None:
                payload["response_format"] = request.response_format

            # Add tools and tool_choice for function calling
            if request.tools:
                payload["tools"] = request.tools
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice

            # Add user tracking
            payload["user"] = f"user_{request.user_id}"

            # Add metadata for TEE audit trail
            payload["metadata"] = {
                "user_id": request.user_id,
                "api_key_id": request.api_key_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "enclava_request_id": str(uuid.uuid4()),
                **(request.metadata or {}),
            }

            async with session.post(
                f"{self.base_url}/chat/completions", json=payload
            ) as response:
                provider_latency = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()

                    # Debug: Log raw response only at debug level
                    logger.debug(
                        f"Raw RedPill API response: {json.dumps(data, default=str)[:2000]}"
                    )

                    # Parse response
                    choices = []
                    for choice_data in data.get("choices", []):
                        message_data = choice_data.get("message", {})

                        # Parse tool_calls if present
                        tool_calls = None
                        if "tool_calls" in message_data and message_data["tool_calls"]:
                            from ..models import ToolCall

                            tool_calls = [
                                ToolCall(
                                    id=tc.get("id"),
                                    type=tc.get("type", "function"),
                                    function=tc.get("function", {}),
                                )
                                for tc in message_data.get("tool_calls", [])
                            ]

                        # Extract content - handle reasoning models (like gpt-oss-120b)
                        # These models have both 'content' and 'reasoning_content' fields.
                        # When max_tokens is hit during reasoning, content may be null but
                        # reasoning_content contains the actual response.
                        content = message_data.get("content")
                        reasoning_content = message_data.get("reasoning_content")
                        finish_reason = choice_data.get("finish_reason")

                        if content is None and reasoning_content:
                            # Reasoning model hit max_tokens during reasoning phase
                            # Use reasoning_content as the response with a note
                            if finish_reason == "length":
                                logger.warning(
                                    f"Reasoning model hit max_tokens during reasoning phase. "
                                    f"Using reasoning_content as response. Consider increasing max_tokens."
                                )
                                content = f"[Reasoning truncated due to max_tokens limit]\n\n{reasoning_content}"
                            else:
                                # Normal case - reasoning complete, use reasoning as content
                                content = reasoning_content

                        choice = ChatChoice(
                            index=choice_data.get("index", 0),
                            message=ChatMessage(
                                role=message_data.get("role", "assistant"),
                                content=content,
                                tool_calls=tool_calls,
                                tool_call_id=message_data.get("tool_call_id"),
                            ),
                            finish_reason=finish_reason,
                        )
                        choices.append(choice)

                    # Parse token usage
                    usage_data = data.get("usage", {})
                    usage = TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                    )

                    # Create response
                    chat_response = ChatResponse(
                        id=data.get("id", str(uuid.uuid4())),
                        object=data.get("object", "chat.completion"),
                        created=data.get("created", int(time.time())),
                        model=data.get("model", request.model),
                        provider=self.provider_name,
                        choices=choices,
                        usage=usage,
                        system_fingerprint=data.get("system_fingerprint"),
                        security_check=True,  # Will be set by security manager
                        risk_score=0.0,  # Will be set by security manager
                        latency_ms=provider_latency,
                        provider_latency_ms=provider_latency,
                    )

                    logger.debug(
                        f"RedPill chat completion successful in {provider_latency:.2f}ms"
                    )
                    return chat_response

                else:
                    error_text = await response.text()
                    self._handle_http_error(
                        response.status, error_text, "chat completion"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"RedPill request error: {e}")
            raise ProviderError(
                "Network error communicating with RedPill",
                provider=self.provider_name,
                error_code="NETWORK_ERROR",
                details={"error": str(e)},
            )
        except Exception as e:
            if isinstance(e, (ProviderError, ValidationError)):
                raise

            logger.error(f"Unexpected error in RedPill chat completion: {e}")
            raise ProviderError(
                "Unexpected error during chat completion",
                provider=self.provider_name,
                error_code="UNEXPECTED_ERROR",
                details={"error": str(e)},
            )

    async def create_chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create streaming chat completion"""
        self._validate_request(request)

        # Additional validation for confidential models
        if not self._is_confidential_model(request.model):
            raise ValidationError(
                f"Model {request.model} is not a confidential model",
                field="model",
            )

        # Check if provider is healthy
        if not self.is_available():
            # Import here to avoid circular dependency
            from ..attestation.scheduler import attestation_scheduler

            health = attestation_scheduler.get_health(self.provider_name)
            error_msg = health.error if health else "unknown"
            raise ProviderError(
                f"Provider unhealthy: {error_msg}",
                provider=self.provider_name,
                error_code="PROVIDER_UNHEALTHY",
            )

        try:
            session = await self._get_session()

            # Prepare streaming payload
            payload = {
                "model": request.model,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        **({"name": msg.name} if msg.name else {}),
                        **(
                            {
                                "tool_calls": [
                                    {
                                        "id": tc.id,
                                        "type": tc.type,
                                        "function": tc.function,
                                    }
                                    for tc in msg.tool_calls
                                ]
                            }
                            if msg.tool_calls
                            else {}
                        ),
                        **(
                            {"tool_call_id": msg.tool_call_id}
                            if msg.tool_call_id
                            else {}
                        ),
                    }
                    for msg in request.messages
                ],
                "temperature": request.temperature,
                "stream": True,
            }

            # Add optional parameters
            if request.max_tokens is not None:
                payload["max_tokens"] = request.max_tokens
            if request.top_p is not None:
                payload["top_p"] = request.top_p
            if request.frequency_penalty is not None:
                payload["frequency_penalty"] = request.frequency_penalty
            if request.presence_penalty is not None:
                payload["presence_penalty"] = request.presence_penalty
            if request.stop is not None:
                payload["stop"] = request.stop
            if request.response_format is not None:
                payload["response_format"] = request.response_format

            # Add tools and tool_choice for function calling
            if request.tools:
                payload["tools"] = request.tools
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice

            # Add user tracking
            payload["user"] = f"user_{request.user_id}"

            async with session.post(
                f"{self.base_url}/chat/completions", json=payload
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        line = line.decode("utf-8").strip()

                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix

                            if data_str == "[DONE]":
                                break

                            try:
                                chunk_data = json.loads(data_str)
                                yield chunk_data
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Failed to parse streaming chunk: {data_str}"
                                )
                                continue
                else:
                    error_text = await response.text()
                    self._handle_http_error(
                        response.status, error_text, "streaming chat completion"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"RedPill streaming error: {e}")
            raise ProviderError(
                "Network error during streaming",
                provider=self.provider_name,
                error_code="STREAMING_ERROR",
                details={"error": str(e)},
            )

    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Create embeddings via RedPill.ai"""
        self._validate_request(request)

        # Check if model is confidential
        if not self._is_confidential_model(request.model):
            raise ValidationError(
                f"Model {request.model} is not a confidential model",
                field="model",
            )

        # Check if provider is healthy
        if not self.is_available():
            # Import here to avoid circular dependency
            from ..attestation.scheduler import attestation_scheduler

            health = attestation_scheduler.get_health(self.provider_name)
            error_msg = health.error if health else "unknown"
            raise ProviderError(
                f"Provider unhealthy: {error_msg}",
                provider=self.provider_name,
                error_code="PROVIDER_UNHEALTHY",
            )

        start_time = time.time()

        try:
            session = await self._get_session()

            # Prepare embedding payload
            payload = {
                "model": request.model,
                "input": request.input,
                "user": f"user_{request.user_id}",
            }

            # Add optional parameters
            if request.encoding_format:
                payload["encoding_format"] = request.encoding_format
            if request.dimensions:
                payload["dimensions"] = request.dimensions

            # Add metadata
            payload["metadata"] = {
                "user_id": request.user_id,
                "api_key_id": request.api_key_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(request.metadata or {}),
            }

            async with session.post(
                f"{self.base_url}/embeddings", json=payload
            ) as response:
                provider_latency = (time.time() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()

                    # Parse embedding data
                    embeddings = []
                    for emb_data in data.get("data", []):
                        embedding = EmbeddingData(
                            object="embedding",
                            index=emb_data.get("index", 0),
                            embedding=emb_data.get("embedding", []),
                        )
                        embeddings.append(embedding)

                    # Parse usage
                    usage_data = data.get("usage", {})
                    usage = TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=0,  # No completion tokens for embeddings
                        total_tokens=usage_data.get(
                            "total_tokens", usage_data.get("prompt_tokens", 0)
                        ),
                    )

                    return EmbeddingResponse(
                        object="list",
                        data=embeddings,
                        model=data.get("model", request.model),
                        provider=self.provider_name,
                        usage=usage,
                        security_check=True,  # Will be set by security manager
                        risk_score=0.0,  # Will be set by security manager
                        latency_ms=provider_latency,
                        provider_latency_ms=provider_latency,
                    )

                else:
                    error_text = await response.text()
                    # Log the detailed error response from the provider
                    logger.error(
                        f"RedPill embedding error - Status {response.status}: {error_text}"
                    )
                    self._handle_http_error(response.status, error_text, "embeddings")

        except aiohttp.ClientError as e:
            logger.error(f"RedPill embedding error: {e}")
            raise ProviderError(
                "Network error during embedding generation",
                provider=self.provider_name,
                error_code="EMBEDDING_ERROR",
                details={"error": str(e)},
            )
        except Exception as e:
            if isinstance(e, (ProviderError, ValidationError)):
                raise

            logger.error(f"Unexpected error in RedPill embedding: {e}")
            raise ProviderError(
                "Unexpected error during embedding generation",
                provider=self.provider_name,
                error_code="UNEXPECTED_ERROR",
                details={"error": str(e)},
            )

    async def cleanup(self):
        """Cleanup RedPill provider resources"""
        # Close HTTP session to prevent memory leaks
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("Closed RedPill HTTP session")

        await super().cleanup()
        logger.debug("RedPill provider cleanup completed")
