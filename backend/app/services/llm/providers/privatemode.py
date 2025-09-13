"""
PrivateMode.ai LLM Provider

Integration with PrivateMode.ai TEE-protected LLM service via proxy.
"""

import json
import logging
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime

import aiohttp

from .base import BaseLLMProvider
from ..models import (
    ChatRequest, ChatResponse, ChatMessage, ChatChoice, TokenUsage,
    EmbeddingRequest, EmbeddingResponse, EmbeddingData,
    ModelInfo, ProviderStatus
)
from ..config import ProviderConfig
from ..exceptions import ProviderError, ValidationError, TimeoutError

logger = logging.getLogger(__name__)


class PrivateModeProvider(BaseLLMProvider):
    """PrivateMode.ai provider with TEE security"""
    
    def __init__(self, config: ProviderConfig, api_key: str):
        super().__init__(config, api_key)
        self.base_url = config.base_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
        
        # TEE-specific settings
        self.verify_ssl = True  # Always verify SSL for security
        self.trust_env = False  # Don't trust environment proxy settings
        
        logger.info(f"PrivateMode provider initialized with base URL: {self.base_url}")
    
    @property
    def provider_name(self) -> str:
        return "privatemode"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with security settings"""
        if self._session is None or self._session.closed:
            # Create secure connector
            connector = aiohttp.TCPConnector(
                verify_ssl=self.verify_ssl,
                limit=100,  # Connection pool limit
                limit_per_host=50,
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True
            )
            
            # Create session with security headers
            timeout = aiohttp.ClientTimeout(total=self.config.resilience.timeout_ms / 1000.0)
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self._create_headers(),
                trust_env=False  # Don't trust environment variables
            )
            
            logger.debug("Created new secure HTTP session for PrivateMode")
        
        return self._session
    
    async def health_check(self) -> ProviderStatus:
        """Check PrivateMode.ai service health"""
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # Use a lightweight endpoint for health check
            async with session.get(f"{self.base_url}/models") as response:
                latency = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    models_data = await response.json()
                    models = [model.get("id", "") for model in models_data.get("data", [])]
                    
                    return ProviderStatus(
                        provider=self.provider_name,
                        status="healthy",
                        latency_ms=latency,
                        success_rate=1.0,
                        last_check=datetime.utcnow(),
                        models_available=models
                    )
                else:
                    error_text = await response.text()
                    return ProviderStatus(
                        provider=self.provider_name,
                        status="degraded",
                        latency_ms=latency,
                        success_rate=0.0,
                        last_check=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}",
                        models_available=[]
                    )
        
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"PrivateMode health check failed: {e}")
            
            return ProviderStatus(
                provider=self.provider_name,
                status="unavailable",
                latency_ms=latency,
                success_rate=0.0,
                last_check=datetime.utcnow(),
                error_message=str(e),
                models_available=[]
            )
    
    async def get_models(self) -> List[ModelInfo]:
        """Get available models from PrivateMode.ai"""
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
                        
                        # Extract all information directly from API response
                        # Determine capabilities based on tasks field
                        tasks = model_data.get("tasks", [])
                        capabilities = []
                        
                        # All PrivateMode models have TEE capability
                        capabilities.append("tee")
                        
                        # Add capabilities based on tasks
                        if "generate" in tasks:
                            capabilities.append("chat")
                        if "embed" in tasks or "embedding" in tasks:
                            capabilities.append("embeddings")
                        if "vision" in tasks:
                            capabilities.append("vision")
                        
                        # Check for function calling support in the API response
                        supports_function_calling = model_data.get("supports_function_calling", False)
                        if supports_function_calling:
                            capabilities.append("function_calling")
                        
                        model_info = ModelInfo(
                            id=model_id,
                            object="model",
                            created=model_data.get("created", int(time.time())),
                            owned_by=model_data.get("owned_by", "privatemode"),
                            provider=self.provider_name,
                            capabilities=capabilities,
                            context_window=model_data.get("context_window"),
                            max_output_tokens=model_data.get("max_output_tokens"),
                            supports_streaming=model_data.get("supports_streaming", True),
                            supports_function_calling=supports_function_calling,
                            tasks=tasks  # Pass through tasks field from PrivateMode API
                        )
                        models.append(model_info)
                    
                    logger.info(f"Retrieved {len(models)} models from PrivateMode")
                    return models
                else:
                    error_text = await response.text()
                    self._handle_http_error(response.status, error_text, "models endpoint")
                    return []  # Never reached due to exception
        
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            
            logger.error(f"Failed to get models from PrivateMode: {e}")
            raise ProviderError(
                "Failed to retrieve models from PrivateMode",
                provider=self.provider_name,
                error_code="MODEL_RETRIEVAL_ERROR",
                details={"error": str(e)}
            )
    
    async def create_chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Create chat completion via PrivateMode.ai"""
        self._validate_request(request)
        
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
                        **({"name": msg.name} if msg.name else {})
                    }
                    for msg in request.messages
                ],
                "temperature": request.temperature,
                "stream": False  # Non-streaming version
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
            
            # Add user tracking
            payload["user"] = f"user_{request.user_id}"
            
            # Add metadata for TEE audit trail
            payload["metadata"] = {
                "user_id": request.user_id,
                "api_key_id": request.api_key_id,
                "timestamp": datetime.utcnow().isoformat(),
                "enclava_request_id": str(uuid.uuid4()),
                **(request.metadata or {})
            }
            
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                provider_latency = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Parse response
                    choices = []
                    for choice_data in data.get("choices", []):
                        message_data = choice_data.get("message", {})
                        choice = ChatChoice(
                            index=choice_data.get("index", 0),
                            message=ChatMessage(
                                role=message_data.get("role", "assistant"),
                                content=message_data.get("content", "")
                            ),
                            finish_reason=choice_data.get("finish_reason")
                        )
                        choices.append(choice)
                    
                    # Parse token usage
                    usage_data = data.get("usage", {})
                    usage = TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0)
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
                        risk_score=0.0,       # Will be set by security manager
                        latency_ms=provider_latency,
                        provider_latency_ms=provider_latency
                    )
                    
                    logger.debug(f"PrivateMode chat completion successful in {provider_latency:.2f}ms")
                    return chat_response
                
                else:
                    error_text = await response.text()
                    self._handle_http_error(response.status, error_text, "chat completion")
        
        except aiohttp.ClientError as e:
            logger.error(f"PrivateMode request error: {e}")
            raise ProviderError(
                "Network error communicating with PrivateMode",
                provider=self.provider_name,
                error_code="NETWORK_ERROR",
                details={"error": str(e)}
            )
        except Exception as e:
            if isinstance(e, (ProviderError, ValidationError)):
                raise
            
            logger.error(f"Unexpected error in PrivateMode chat completion: {e}")
            raise ProviderError(
                "Unexpected error during chat completion",
                provider=self.provider_name,
                error_code="UNEXPECTED_ERROR",
                details={"error": str(e)}
            )
    
    async def create_chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Create streaming chat completion"""
        self._validate_request(request)
        
        try:
            session = await self._get_session()
            
            # Prepare streaming payload
            payload = {
                "model": request.model,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        **({"name": msg.name} if msg.name else {})
                    }
                    for msg in request.messages
                ],
                "temperature": request.temperature,
                "stream": True
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
            
            # Add user tracking
            payload["user"] = f"user_{request.user_id}"
            
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                yield chunk_data
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse streaming chunk: {data_str}")
                                continue
                else:
                    error_text = await response.text()
                    self._handle_http_error(response.status, error_text, "streaming chat completion")
        
        except aiohttp.ClientError as e:
            logger.error(f"PrivateMode streaming error: {e}")
            raise ProviderError(
                "Network error during streaming",
                provider=self.provider_name,
                error_code="STREAMING_ERROR",
                details={"error": str(e)}
            )
    
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Create embeddings via PrivateMode.ai"""
        self._validate_request(request)
        
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # Prepare embedding payload
            payload = {
                "model": request.model,
                "input": request.input,
                "user": f"user_{request.user_id}"
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
                "timestamp": datetime.utcnow().isoformat(),
                **(request.metadata or {})
            }
            
            async with session.post(
                f"{self.base_url}/embeddings",
                json=payload
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
                            embedding=emb_data.get("embedding", [])
                        )
                        embeddings.append(embedding)
                    
                    # Parse usage
                    usage_data = data.get("usage", {})
                    usage = TokenUsage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=0,  # No completion tokens for embeddings
                        total_tokens=usage_data.get("total_tokens", usage_data.get("prompt_tokens", 0))
                    )
                    
                    return EmbeddingResponse(
                        object="list",
                        data=embeddings,
                        model=data.get("model", request.model),
                        provider=self.provider_name,
                        usage=usage,
                        security_check=True,  # Will be set by security manager
                        risk_score=0.0,       # Will be set by security manager
                        latency_ms=provider_latency,
                        provider_latency_ms=provider_latency
                    )
                
                else:
                    error_text = await response.text()
                    self._handle_http_error(response.status, error_text, "embeddings")
        
        except aiohttp.ClientError as e:
            logger.error(f"PrivateMode embedding error: {e}")
            raise ProviderError(
                "Network error during embedding generation",
                provider=self.provider_name,
                error_code="EMBEDDING_ERROR",
                details={"error": str(e)}
            )
        except Exception as e:
            if isinstance(e, (ProviderError, ValidationError)):
                raise
            
            logger.error(f"Unexpected error in PrivateMode embedding: {e}")
            raise ProviderError(
                "Unexpected error during embedding generation",
                provider=self.provider_name,
                error_code="UNEXPECTED_ERROR",
                details={"error": str(e)}
            )
    
    async def cleanup(self):
        """Cleanup PrivateMode provider resources"""
        await super().cleanup()
        logger.debug("PrivateMode provider cleanup completed")