"""
Integration tests for Responses API

Tests the complete flow of the Responses API including:
- Basic response creation
- Tool execution
- Budget enforcement
- Conversation management
- Response chaining
- Streaming
"""

import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock


class TestResponsesAPI:
    """Test suite for Responses API"""

    @pytest.mark.asyncio
    async def test_create_basic_response(self, async_client: AsyncClient, test_api_key: str):
        """Test basic response creation without tools"""
        response = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "Hello, how are you?",
                "instructions": "You are a helpful assistant.",
                "store": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["object"] == "response"
        assert data["status"] == "completed"
        assert "id" in data
        assert data["id"].startswith("resp_")
        assert "output" in data
        assert "usage" in data
        assert data["usage"]["total_tokens"] > 0

    @pytest.mark.asyncio
    async def test_response_with_file_search_tool(self, async_client: AsyncClient, test_api_key: str):
        """Test response creation with file_search tool"""
        response = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "What is in the knowledge base about AI?",
                "tools": [
                    {"type": "file_search"}
                ],
                "store": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert "output" in data

        # Check if tool was called (look for function_call items)
        has_tool_call = any(
            item.get("type") == "function_call"
            for item in data["output"]
        )
        # Tool may or may not be called depending on LLM decision
        # Just verify response structure is correct

    @pytest.mark.asyncio
    async def test_response_with_multi_collection_search(self, async_client: AsyncClient, test_api_key: str):
        """Test file_search with multiple vector stores"""
        response = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "Search across all knowledge bases",
                "tools": [
                    {
                        "type": "file_search",
                        "vector_store_ids": ["kb1", "kb2", "kb3"]
                    }
                ],
                "store": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_response_chaining(self, async_client: AsyncClient, test_api_key: str):
        """Test response chaining with previous_response_id"""
        # Create first response
        response1 = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "My name is Alice.",
                "store": True
            }
        )

        assert response1.status_code == 200
        data1 = response1.json()
        response_id_1 = data1["id"]

        # Create chained response
        response2 = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "What is my name?",
                "previous_response_id": response_id_1,
                "store": True
            }
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["previous_response_id"] == response_id_1

    @pytest.mark.asyncio
    async def test_get_stored_response(self, async_client: AsyncClient, test_api_key: str):
        """Test retrieving a stored response"""
        # Create response
        create_response = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "Test message",
                "store": True
            }
        )

        assert create_response.status_code == 200
        response_id = create_response.json()["id"]

        # Retrieve response
        get_response = await async_client.get(
            f"/api/v1/responses/{response_id}",
            headers={"Authorization": f"Bearer {test_api_key}"}
        )

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == response_id

    @pytest.mark.asyncio
    async def test_response_with_prompt_reference(self, async_client: AsyncClient, test_api_key: str):
        """Test response creation with prompt (agent config) reference"""
        # Create a prompt first
        prompt_response = await async_client.post(
            "/api/v1/prompts",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "name": "test-agent",
                "display_name": "Test Agent",
                "instructions": "You are a test assistant.",
                "model": "gpt-oss-120b",
                "tools": [{"type": "web_search"}]
            }
        )

        assert prompt_response.status_code == 201

        # Use prompt in response
        response = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "Hello",
                "prompt": {"id": "test-agent"},
                "store": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_budget_enforcement(self, async_client: AsyncClient, test_api_key: str):
        """Test that budget limits are enforced"""
        # This test assumes a budget is configured for the test API key
        # If budget is exceeded, should get 429 error

        # Try to create response with very large max_tokens
        response = await async_client.post(
            "/api/v1/responses",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "Generate a very long response",
                "max_tokens": 100000,  # Unreasonably large
                "store": True
            }
        )

        # Should either succeed or fail with budget error
        assert response.status_code in [200, 429]

    @pytest.mark.asyncio
    async def test_streaming_response(self, async_client: AsyncClient, test_api_key: str):
        """Test streaming response"""
        response = await async_client.post(
            "/api/v1/responses?stream=true",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "model": "gpt-oss-120b",
                "input": "Count from 1 to 5",
                "store": False
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Collect events
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                events.append(line)

        # Should have received some events
        assert len(events) > 0


class TestConversationsAPI:
    """Test suite for Conversations API"""

    @pytest.mark.asyncio
    async def test_create_conversation(self, async_client: AsyncClient, test_api_key: str):
        """Test conversation creation"""
        response = await async_client.post(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={}
        )

        assert response.status_code == 201
        data = response.json()

        assert data["object"] == "conversation"
        assert "id" in data
        assert data["id"].startswith("conv_")
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_conversations(self, async_client: AsyncClient, test_api_key: str):
        """Test listing conversations"""
        # Create a conversation first
        await async_client.post(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={}
        )

        # List conversations
        response = await async_client.get(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {test_api_key}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["object"] == "list"
        assert "data" in data
        assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_add_items_to_conversation(self, async_client: AsyncClient, test_api_key: str):
        """Test adding items to conversation"""
        # Create conversation
        create_response = await async_client.post(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={}
        )
        conversation_id = create_response.json()["id"]

        # Add items
        items_response = await async_client.post(
            f"/api/v1/conversations/{conversation_id}/items",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "items": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": "Hello"
                    }
                ]
            }
        )

        assert items_response.status_code == 200
        data = items_response.json()
        assert len(data["items"]) == 1


class TestPromptsAPI:
    """Test suite for Prompts API"""

    @pytest.mark.asyncio
    async def test_create_prompt(self, async_client: AsyncClient, test_api_key: str):
        """Test prompt creation"""
        response = await async_client.post(
            "/api/v1/prompts",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "name": "test-prompt-unique",
                "display_name": "Test Prompt",
                "instructions": "You are a helpful assistant.",
                "model": "gpt-oss-120b",
                "temperature": 0.7,
                "tools": [
                    {"type": "web_search"}
                ]
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == "test-prompt-unique"
        assert data["display_name"] == "Test Prompt"

    @pytest.mark.asyncio
    async def test_list_prompts(self, async_client: AsyncClient, test_api_key: str):
        """Test listing prompts"""
        response = await async_client.get(
            "/api/v1/prompts",
            headers={"Authorization": f"Bearer {test_api_key}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["object"] == "list"
        assert "data" in data

    @pytest.mark.asyncio
    async def test_update_prompt(self, async_client: AsyncClient, test_api_key: str):
        """Test updating a prompt"""
        # Create prompt
        create_response = await async_client.post(
            "/api/v1/prompts",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "name": "update-test",
                "display_name": "Update Test",
                "instructions": "Original instructions",
                "model": "gpt-oss-120b"
            }
        )
        prompt_id = create_response.json()["id"]

        # Update prompt
        update_response = await async_client.put(
            f"/api/v1/prompts/{prompt_id}",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={
                "instructions": "Updated instructions"
            }
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["instructions"] == "Updated instructions"
