"""
Test LLM API endpoints.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


class TestLLMEndpoints:
    """Test LLM API endpoints."""

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, client: AsyncClient):
        """Test successful chat completion."""
        # Mock the LiteLLM client response
        mock_response = {
            "choices": [
                {
                    "message": {
                        "content": "Hello! How can I help you today?",
                        "role": "assistant"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }
        
        with patch("app.services.litellm_client.LiteLLMClient.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
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
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            }
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_embeddings_success(self, client: AsyncClient):
        """Test successful embeddings generation."""
        mock_response = {
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "index": 0
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "total_tokens": 5
            }
        }
        
        with patch("app.services.litellm_client.LiteLLMClient.create_embedding") as mock_embeddings:
            mock_embeddings.return_value = mock_response
            
            response = await client.post(
                "/api/v1/llm/embeddings",
                json={
                    "model": "text-embedding-ada-002",
                    "input": "Hello world"
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"][0]["embedding"]) == 3

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, client: AsyncClient):
        """Test budget exceeded scenario."""
        with patch("app.services.budget_enforcement.BudgetEnforcementService.check_budget_compliance") as mock_check:
            mock_check.side_effect = Exception("Budget exceeded")
            
            response = await client.post(
                "/api/v1/llm/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                },
                headers={"Authorization": "Bearer test-api-key"}
            )
        
        assert response.status_code == 402  # Payment required

    @pytest.mark.asyncio
    async def test_model_validation(self, client: AsyncClient):
        """Test model validation."""
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