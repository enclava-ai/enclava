"""
Integration tests for the new LLM service.
Tests end-to-end functionality including provider integration, security, and performance.
"""
import pytest
import asyncio
import time
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock
import json


class TestLLMServiceIntegration:
    """Integration tests for LLM service."""

    @pytest.mark.asyncio
    async def test_full_chat_flow(self, client: AsyncClient):
        """Test complete chat completion flow with security and budget checks."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        # Mock successful LLM service response
        mock_response = ChatCompletionResponse(
            id="test-completion-123",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Hello! I'm a TEE-protected AI assistant. How can I help you today?"
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=25,
                completion_tokens=15,
                total_tokens=40
            ),
            security_analysis={
                "risk_score": 0.1,
                "threats_detected": [],
                "risk_level": "low",
                "analysis_time_ms": 12.5
            }
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat, \
             patch("app.services.budget_enforcement.BudgetEnforcementService.check_budget_compliance") as mock_budget:
            
            mock_chat.return_value = mock_response
            mock_budget.return_value = True  # Budget check passes
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Hello, what are your capabilities?"}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 150
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        # Verify response structure
        assert response.status_code == 200
        data = response.json()
        
        # Check standard OpenAI-compatible fields
        assert "id" in data
        assert "object" in data
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert "usage" in data
        
        # Check security integration
        assert "security_analysis" in data
        assert data["security_analysis"]["risk_level"] == "low"
        
        # Verify content
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "TEE-protected" in data["choices"][0]["message"]["content"]
        
        # Verify usage tracking
        assert data["usage"]["total_tokens"] == 40
        assert data["usage"]["prompt_tokens"] == 25
        assert data["usage"]["completion_tokens"] == 15

    @pytest.mark.asyncio
    async def test_embedding_integration(self, client: AsyncClient):
        """Test embedding generation with fallback handling."""
        from app.services.llm.models import EmbeddingResponse, EmbeddingData, Usage
        
        # Create realistic 1024-dimensional embedding
        embedding_vector = [0.1 * i for i in range(1024)]
        
        mock_response = EmbeddingResponse(
            object="list",
            data=[
                EmbeddingData(
                    object="embedding",
                    embedding=embedding_vector,
                    index=0
                )
            ],
            model="privatemode-embeddings",
            usage=Usage(
                prompt_tokens=8,
                total_tokens=8
            )
        )
        
        with patch("app.services.llm.service.llm_service.create_embedding") as mock_embedding:
            mock_embedding.return_value = mock_response
            
            response = await client.post(
                "/api/v1/llm/embeddings",
                json={
                    "model": "privatemode-embeddings",
                    "input": "This is a test document for embedding generation."
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify embedding structure
        assert "object" in data
        assert "data" in data
        assert "usage" in data
        assert len(data["data"]) == 1
        assert len(data["data"][0]["embedding"]) == 1024
        assert data["data"][0]["index"] == 0

    @pytest.mark.asyncio
    async def test_provider_health_integration(self, client: AsyncClient):
        """Test provider health monitoring integration."""
        mock_status = {
            "privatemode": {
                "provider": "PrivateMode.ai",
                "status": "healthy",
                "latency_ms": 245.8,
                "success_rate": 0.987,
                "last_check": "2025-01-01T12:00:00Z",
                "error_message": None,
                "models_available": [
                    "privatemode-llama-3-70b",
                    "privatemode-claude-3-sonnet",
                    "privatemode-gpt-4o",
                    "privatemode-embeddings"
                ]
            }
        }
        
        with patch("app.services.llm.service.llm_service.get_provider_status") as mock_provider:
            mock_provider.return_value = mock_status
            
            response = await client.get(
                "/api/v1/llm/providers/status",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "data" in data
        assert "privatemode" in data["data"]
        
        provider_data = data["data"]["privatemode"]
        assert provider_data["status"] == "healthy"
        assert provider_data["latency_ms"] < 300  # Reasonable latency
        assert provider_data["success_rate"] > 0.95  # High success rate
        assert len(provider_data["models_available"]) >= 4

    @pytest.mark.asyncio
    async def test_error_handling_and_fallback(self, client: AsyncClient):
        """Test error handling and fallback scenarios."""
        # Test provider unavailable scenario
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.side_effect = Exception("Provider temporarily unavailable")
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        # Should return error but not crash
        assert response.status_code in [500, 503]  # Server error or service unavailable

    @pytest.mark.asyncio
    async def test_security_threat_detection(self, client: AsyncClient):
        """Test security threat detection integration."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        # Mock response with security threat detected
        mock_response = ChatCompletionResponse(
            id="test-completion-security",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="I cannot help with that request as it violates security policies."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=15,
                completion_tokens=12,
                total_tokens=27
            ),
            security_analysis={
                "risk_score": 0.8,
                "threats_detected": ["potential_malicious_code"],
                "risk_level": "high",
                "blocked": True,
                "analysis_time_ms": 45.2
            }
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "user", "content": "How to create malicious code?"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200  # Request succeeds but content is filtered
        data = response.json()
        
        # Verify security analysis
        assert "security_analysis" in data
        assert data["security_analysis"]["risk_level"] == "high"
        assert data["security_analysis"]["blocked"] is True
        assert "malicious" in data["security_analysis"]["threats_detected"][0]

    @pytest.mark.asyncio
    async def test_performance_characteristics(self, client: AsyncClient):
        """Test performance characteristics of the LLM service."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        # Mock fast response
        mock_response = ChatCompletionResponse(
            id="test-perf",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Quick response for performance testing."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=8,
                total_tokens=18
            )
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            # Measure response time
            start_time = time.time()
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "user", "content": "Quick test"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
            
            response_time = time.time() - start_time
        
        assert response.status_code == 200
        # API should respond quickly (mocked, so should be very fast)
        assert response_time < 1.0  # Less than 1 second for mocked response

    @pytest.mark.asyncio
    async def test_model_capabilities_detection(self, client: AsyncClient):
        """Test model capabilities detection and reporting."""
        from app.services.llm.models import Model
        
        mock_models = [
            Model(
                id="privatemode-llama-3-70b",
                object="model",
                created=1234567890,
                owned_by="PrivateMode.ai",
                provider="PrivateMode.ai",
                capabilities=["tee", "chat", "function_calling"],
                context_window=32768,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True
            ),
            Model(
                id="privatemode-embeddings",
                object="model",
                created=1234567890,
                owned_by="PrivateMode.ai",
                provider="PrivateMode.ai",
                capabilities=["tee", "embeddings"],
                context_window=512,
                supports_streaming=False,
                supports_function_calling=False
            )
        ]
        
        with patch("app.services.llm.service.llm_service.get_models") as mock_models_call:
            mock_models_call.return_value = mock_models
            
            response = await client.get(
                "/api/v1/llm/models",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify model capabilities
        assert len(data["data"]) == 2
        
        # Check chat model capabilities
        chat_model = next(m for m in data["data"] if m["id"] == "privatemode-llama-3-70b")
        assert "tee" in chat_model["capabilities"]
        assert "chat" in chat_model["capabilities"]
        assert chat_model["supports_streaming"] is True
        assert chat_model["supports_function_calling"] is True
        assert chat_model["context_window"] == 32768
        
        # Check embedding model capabilities
        embed_model = next(m for m in data["data"] if m["id"] == "privatemode-embeddings")
        assert "tee" in embed_model["capabilities"]
        assert "embeddings" in embed_model["capabilities"]
        assert embed_model["supports_streaming"] is False
        assert embed_model["context_window"] == 512

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client: AsyncClient):
        """Test handling of concurrent requests."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        mock_response = ChatCompletionResponse(
            id="test-concurrent",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Concurrent response"
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=5,
                completion_tokens=3,
                total_tokens=8
            )
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            # Create multiple concurrent requests
            tasks = []
            for i in range(5):
                task = client.post(
                    "/api/v1/llm/chat/completions",
                    json={
                        "model": "privatemode-llama-3-70b",
                        "messages": [
                            {"role": "user", "content": f"Concurrent test {i}"}
                        ]
                    },
                    headers={"Authorization": "Bearer test-api-key"}
                )
                tasks.append(task)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks)
        
        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "choices" in data
            assert data["choices"][0]["message"]["content"] == "Concurrent response"

    @pytest.mark.asyncio
    async def test_budget_enforcement_integration(self, client: AsyncClient):
        """Test budget enforcement integration with LLM service."""
        # Test budget exceeded scenario
        with patch("app.services.budget_enforcement.BudgetEnforcementService.check_budget_compliance") as mock_budget:
            mock_budget.side_effect = Exception("Monthly budget limit exceeded")
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "user", "content": "Test budget enforcement"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 402  # Payment required
        
        # Test budget warning scenario
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        mock_response = ChatCompletionResponse(
            id="test-budget-warning",
            object="chat.completion", 
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Response with budget warning"
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=8,
                total_tokens=18
            ),
            budget_warnings=["Approaching monthly budget limit (85% used)"]
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat, \
             patch("app.services.budget_enforcement.BudgetEnforcementService.check_budget_compliance") as mock_budget:
            
            mock_chat.return_value = mock_response
            mock_budget.return_value = True  # Budget check passes but with warning
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "user", "content": "Test budget warning"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "budget_warnings" in data
        assert len(data["budget_warnings"]) > 0
        assert "85%" in data["budget_warnings"][0]