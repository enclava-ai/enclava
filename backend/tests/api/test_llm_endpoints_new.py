"""
Test LLM API endpoints with new LLM service.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock
import json


class TestLLMEndpoints:
    """Test LLM API endpoints with new LLM service."""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, client: AsyncClient):
        """Test successful chat completion with new LLM service."""
        # Mock the new LLM service response
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        mock_response = ChatCompletionResponse(
            id="test-completion-123",
            object="chat.completion",
            created=1234567890,
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Hello! How can I help you today?"
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=15,
                total_tokens=25
            )
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
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
        
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_chat_completion_unauthorized(self, client: AsyncClient):
        """Test chat completion without API key."""
        response = await client.post(
            "/api/v1/llm/chat/completions",
            json={
                "model": "privatemode-llama-3-70b",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            }
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_embeddings_success(self, client: AsyncClient):
        """Test successful embeddings generation with new LLM service."""
        from app.services.llm.models import EmbeddingResponse, EmbeddingData, Usage
        
        mock_response = EmbeddingResponse(
            object="list",
            data=[
                EmbeddingData(
                    object="embedding",
                    embedding=[0.1, 0.2, 0.3] * 341 + [0.1, 0.2, 0.3],  # 1024 dimensions
                    index=0
                )
            ],
            model="privatemode-embeddings",
            usage=Usage(
                prompt_tokens=5,
                total_tokens=5
            )
        )
        
        with patch("app.services.llm.service.llm_service.create_embedding") as mock_embeddings:
            mock_embeddings.return_value = mock_response
            
            response = await client.post(
                "/api/v1/llm/embeddings",
                json={
                    "model": "privatemode-embeddings",
                    "input": "Hello world"
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"][0]["embedding"]) == 1024

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, client: AsyncClient):
        """Test budget exceeded scenario."""
        with patch("app.services.budget_enforcement.BudgetEnforcementService.check_budget_compliance") as mock_check:
            mock_check.side_effect = Exception("Budget exceeded")
            
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
        
        assert response.status_code == 402  # Payment required

    @pytest.mark.asyncio
    async def test_model_validation(self, client: AsyncClient):
        """Test model validation with new LLM service."""
        response = await client.post(
            "/api/v1/llm/chat/completions",
            json={
                "model": "invalid-model",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            },
            headers={"Authorization": "Bearer test-api-key"}
        )
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_provider_status_endpoint(self, client: AsyncClient):
        """Test provider status endpoint."""
        mock_status = {
            "privatemode": {
                "provider": "PrivateMode.ai",
                "status": "healthy",
                "latency_ms": 250.5,
                "success_rate": 0.98,
                "last_check": "2025-01-01T12:00:00Z",
                "models_available": ["privatemode-llama-3-70b", "privatemode-embeddings"]
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
        assert "data" in data
        assert "privatemode" in data["data"]
        assert data["data"]["privatemode"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_models_endpoint(self, client: AsyncClient):
        """Test models listing endpoint."""
        from app.services.llm.models import Model
        
        mock_models = [
            Model(
                id="privatemode-llama-3-70b",
                object="model",
                created=1234567890,
                owned_by="PrivateMode.ai",
                provider="PrivateMode.ai",
                capabilities=["tee", "chat"],
                context_window=32768,
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
                context_window=512
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
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "privatemode-llama-3-70b"
        assert "tee" in data["data"][0]["capabilities"]

    @pytest.mark.asyncio
    async def test_security_integration(self, client: AsyncClient):
        """Test security analysis integration."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        mock_response = ChatCompletionResponse(
            id="test-completion-123",
            object="chat.completion",
            created=1234567890,
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="I can help with that."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=8,
                total_tokens=18
            ),
            security_analysis={
                "risk_score": 0.1,
                "threats_detected": [],
                "risk_level": "low"
            }
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "privatemode-llama-3-70b",
                    "messages": [
                        {"role": "user", "content": "Help me with coding"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "security_analysis" in data
        assert data["security_analysis"]["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_tee_model_detection(self, client: AsyncClient):
        """Test TEE-protected model detection."""
        from app.services.llm.models import Model
        
        mock_models = [
            Model(
                id="privatemode-llama-3-70b",
                object="model",
                created=1234567890,
                owned_by="PrivateMode.ai",
                provider="PrivateMode.ai",
                capabilities=["tee", "chat"],
                context_window=32768,
                supports_streaming=True,
                supports_function_calling=True
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
        
        # Check that TEE capability is properly detected
        tee_models = [model for model in data["data"] if "tee" in model.get("capabilities", [])]
        assert len(tee_models) > 0
        assert tee_models[0]["id"] == "privatemode-llama-3-70b"

    @pytest.mark.asyncio 
    async def test_provider_health_monitoring(self, client: AsyncClient):
        """Test provider health monitoring."""
        mock_health = {
            "service_status": "healthy",
            "providers": {
                "privatemode": {
                    "status": "healthy",
                    "latency_ms": 250.5,
                    "success_rate": 0.98,
                    "last_check": "2025-01-01T12:00:00Z"
                }
            },
            "overall_health": 0.98
        }
        
        with patch("app.services.llm.service.llm_service.get_health_summary") as mock_health_call:
            mock_health_call.return_value = mock_health
            
            response = await client.get(
                "/api/v1/llm/health",
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["service_status"] == "healthy"
        assert "providers" in data
        assert data["providers"]["privatemode"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_streaming_support(self, client: AsyncClient):
        """Test streaming support indication."""
        from app.services.llm.models import Model
        
        mock_models = [
            Model(
                id="privatemode-llama-3-70b",
                object="model",
                created=1234567890,
                owned_by="PrivateMode.ai",
                provider="PrivateMode.ai",
                capabilities=["tee", "chat"],
                context_window=32768,
                supports_streaming=True,
                supports_function_calling=True
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
        streaming_models = [model for model in data["data"] if model.get("supports_streaming")]
        assert len(streaming_models) > 0
        assert streaming_models[0]["supports_streaming"] is True