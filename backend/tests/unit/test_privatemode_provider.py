"""
Unit tests for PrivateMode provider tool calling support.

Tests Phase 0: Provider Tool Support
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.llm.providers.privatemode import PrivateModeProvider
from app.services.llm.models import (
    ChatRequest,
    ChatMessage,
    ChatResponse,
    ToolCall,
)
from app.services.llm.config import ProviderConfig, ResilienceConfig


@pytest.fixture
def provider_config():
    """Create test provider configuration"""
    return ProviderConfig(
        name="privatemode",
        provider_type="privatemode",
        base_url="https://api.privatemode.ai/v1",
        api_key_env_var="PRIVATEMODE_API_KEY",
        enabled=True,
        supported_models=["gpt-oss-120b"],  # Add supported model for testing
        resilience=ResilienceConfig(),
    )


@pytest.fixture
def provider(provider_config):
    """Create PrivateMode provider instance"""
    return PrivateModeProvider(config=provider_config, api_key="test-key")


@pytest.mark.asyncio
async def test_create_completion_with_tools_in_request(provider):
    """Test that tools and tool_choice are included in request payload"""
    # Create request with tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    request = ChatRequest(
        model="gpt-oss-120b",
        messages=[ChatMessage(role="user", content="What's the weather?")],
        tools=tools,
        tool_choice="auto",
        user_id="123",
        api_key_id=1,
    )

    # Mock the HTTP response
    mock_response_data = {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": "gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Let me check the weather for you.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }

    with patch.object(provider, '_get_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        # Create proper async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session.post = MagicMock(return_value=mock_context)
        mock_get_session.return_value = mock_session

        # Execute request (response not needed - we're verifying the request payload)
        await provider.create_chat_completion(request)

        # Verify tools and tool_choice were sent in payload
        call_args = mock_session.post.call_args
        payload = call_args.kwargs['json']

        assert 'tools' in payload
        assert payload['tools'] == tools
        assert 'tool_choice' in payload
        assert payload['tool_choice'] == "auto"


@pytest.mark.asyncio
async def test_parse_response_with_tool_calls(provider):
    """Test parsing response with tool_calls"""
    request = ChatRequest(
        model="gpt-oss-120b",
        messages=[ChatMessage(role="user", content="Get weather")],
        user_id="123",
        api_key_id=1,
    )

    # Mock response with tool_calls
    mock_response_data = {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": "gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,  # Can be None when tool_calls present
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": json.dumps({"location": "London"})
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }

    with patch.object(provider, '_get_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        # Create proper async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session.post = MagicMock(return_value=mock_context)
        mock_get_session.return_value = mock_session

        # Execute request
        response = await provider.create_chat_completion(request)

        # Verify tool_calls were parsed correctly
        assert len(response.choices) == 1
        choice = response.choices[0]
        assert choice.message.tool_calls is not None
        assert len(choice.message.tool_calls) == 1

        tool_call = choice.message.tool_calls[0]
        assert tool_call.id == "call_123"
        assert tool_call.type == "function"
        assert tool_call.function["name"] == "get_weather"
        assert tool_call.function["arguments"] == json.dumps({"location": "London"})

        # Content can be None
        assert choice.message.content is None
        assert choice.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_parse_response_no_tool_calls(provider):
    """Test parsing normal response without tool_calls"""
    request = ChatRequest(
        model="gpt-oss-120b",
        messages=[ChatMessage(role="user", content="Hello")],
        user_id="123",
        api_key_id=1,
    )

    mock_response_data = {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": "gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 10,
            "total_tokens": 15,
        },
    }

    with patch.object(provider, '_get_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        # Create proper async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session.post = MagicMock(return_value=mock_context)
        mock_get_session.return_value = mock_session

        # Execute request
        response = await provider.create_chat_completion(request)

        # Verify no tool_calls
        assert len(response.choices) == 1
        choice = response.choices[0]
        assert choice.message.tool_calls is None
        assert choice.message.content == "Hello! How can I help?"
        assert choice.finish_reason == "stop"


@pytest.mark.asyncio
async def test_tool_message_serialization(provider):
    """Test that tool response messages are serialized correctly"""
    # Create request with tool response message
    request = ChatRequest(
        model="gpt-oss-120b",
        messages=[
            ChatMessage(role="user", content="Get weather"),
            ChatMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_123",
                        type="function",
                        function={"name": "get_weather", "arguments": json.dumps({"location": "London"})}
                    )
                ]
            ),
            ChatMessage(
                role="tool",
                content="Weather: Sunny, 20°C",
                tool_call_id="call_123",
            ),
        ],
        user_id="123",
        api_key_id=1,
    )

    mock_response_data = {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": "gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The weather in London is sunny and 20°C.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
        },
    }

    with patch.object(provider, '_get_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        # Create proper async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session.post = MagicMock(return_value=mock_context)
        mock_get_session.return_value = mock_session

        # Execute request (response not needed - we're verifying the request payload)
        await provider.create_chat_completion(request)

        # Verify message serialization
        call_args = mock_session.post.call_args
        payload = call_args.kwargs['json']
        messages = payload['messages']

        # First message: user
        assert messages[0]['role'] == 'user'
        assert messages[0]['content'] == 'Get weather'

        # Second message: assistant with tool_calls
        assert messages[1]['role'] == 'assistant'
        assert messages[1]['content'] is None
        assert 'tool_calls' in messages[1]
        assert len(messages[1]['tool_calls']) == 1
        assert messages[1]['tool_calls'][0]['id'] == 'call_123'

        # Third message: tool response
        assert messages[2]['role'] == 'tool'
        assert messages[2]['content'] == 'Weather: Sunny, 20°C'
        assert 'tool_call_id' in messages[2]
        assert messages[2]['tool_call_id'] == 'call_123'


@pytest.mark.asyncio
async def test_streaming_with_tool_calls(provider):
    """Test that tools are included in streaming requests"""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]

    request = ChatRequest(
        model="gpt-oss-120b",
        messages=[ChatMessage(role="user", content="Weather?")],
        tools=tools,
        tool_choice="auto",
        user_id="123",
        api_key_id=1,
        stream=True,
    )

    # Mock streaming response
    mock_chunks = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
        'data: {"choices":[{"delta":{"content":"Let"}}]}\n',
        'data: [DONE]\n',
    ]

    with patch.object(provider, '_get_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200

        # Create async generator for content
        async def mock_content():
            for chunk in mock_chunks:
                yield chunk.encode('utf-8')

        mock_response.content = mock_content()

        # Create proper async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session.post = MagicMock(return_value=mock_context)
        mock_get_session.return_value = mock_session

        # Execute streaming request
        chunks = []
        async for chunk in provider.create_chat_completion_stream(request):
            chunks.append(chunk)

        # Verify tools were sent in payload
        call_args = mock_session.post.call_args
        payload = call_args.kwargs['json']

        assert 'tools' in payload
        assert payload['tools'] == tools
        assert 'tool_choice' in payload
        assert payload['tool_choice'] == "auto"
        assert payload['stream'] is True


@pytest.mark.asyncio
async def test_finish_reason_tool_calls(provider):
    """Test that finish_reason='tool_calls' is detected correctly"""
    request = ChatRequest(
        model="gpt-oss-120b",
        messages=[ChatMessage(role="user", content="Test")],
        user_id="123",
        api_key_id=1,
    )

    mock_response_data = {
        "id": "test-id",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": "gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_456",
                            "type": "function",
                            "function": {
                                "name": "test_func",
                                "arguments": "{}"
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 5,
            "total_tokens": 10,
        },
    }

    with patch.object(provider, '_get_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        # Create proper async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        mock_session.post = MagicMock(return_value=mock_context)
        mock_get_session.return_value = mock_session

        # Execute request
        response = await provider.create_chat_completion(request)

        # Verify finish_reason
        assert response.choices[0].finish_reason == "tool_calls"
        assert response.choices[0].message.tool_calls is not None
        assert len(response.choices[0].message.tool_calls) == 1
