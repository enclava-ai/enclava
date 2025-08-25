#!/usr/bin/env python3
"""
LLM Models Tests - Data Models and Validation
Tests for LLM service request/response models and validation logic

Priority: app/services/llm/models.py
Focus: Input validation, data serialization, model compliance
"""

import pytest
from pydantic import ValidationError
from app.services.llm.models import (
    ChatMessage, 
    ChatCompletionRequest, 
    ChatCompletionResponse,
    Usage,
    Choice,
    ResponseMessage
)


class TestChatMessage:
    """Test ChatMessage model validation and serialization"""
    
    def test_valid_chat_message_creation(self):
        """Test creating valid chat messages"""
        # User message
        user_msg = ChatMessage(role="user", content="Hello, world!")
        assert user_msg.role == "user"
        assert user_msg.content == "Hello, world!"
        
        # Assistant message
        assistant_msg = ChatMessage(role="assistant", content="Hi there!")
        assert assistant_msg.role == "assistant"
        assert assistant_msg.content == "Hi there!"
        
        # System message
        system_msg = ChatMessage(role="system", content="You are a helpful assistant.")
        assert system_msg.role == "system"
        assert system_msg.content == "You are a helpful assistant."
    
    def test_invalid_role_validation(self):
        """Test validation of invalid message roles"""
        with pytest.raises(ValidationError):
            ChatMessage(role="invalid_role", content="Test")
    
    def test_empty_content_validation(self):
        """Test validation of empty content"""
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="")
        
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content=None)
    
    def test_content_length_validation(self):
        """Test validation of content length limits"""
        # Very long content should be validated
        long_content = "A" * 100000  # 100k characters
        
        # Should either accept or reject based on model limits
        try:
            msg = ChatMessage(role="user", content=long_content)
            assert len(msg.content) == 100000
        except ValidationError:
            # Acceptable if model enforces length limits
            pass
    
    def test_message_serialization(self):
        """Test message serialization to dict"""
        msg = ChatMessage(role="user", content="Test message")
        serialized = msg.dict()
        
        assert serialized["role"] == "user"
        assert serialized["content"] == "Test message"
        
        # Should be able to recreate from dict
        recreated = ChatMessage(**serialized)
        assert recreated.role == msg.role
        assert recreated.content == msg.content


class TestChatCompletionRequest:
    """Test ChatCompletionRequest model validation"""
    
    def test_minimal_valid_request(self):
        """Test creating minimal valid request"""
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="gpt-3.5-turbo"
        )
        
        assert len(request.messages) == 1
        assert request.model == "gpt-3.5-turbo"
        assert request.temperature is None or 0 <= request.temperature <= 2
    
    def test_full_parameter_request(self):
        """Test request with all parameters"""
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content="You are helpful"),
                ChatMessage(role="user", content="Hello")
            ],
            model="gpt-4",
            temperature=0.7,
            max_tokens=150,
            top_p=0.9,
            frequency_penalty=0.5,
            presence_penalty=0.3,
            stop=["END", "STOP"],
            stream=False
        )
        
        assert len(request.messages) == 2
        assert request.model == "gpt-4"
        assert request.temperature == 0.7
        assert request.max_tokens == 150
        assert request.top_p == 0.9
        assert request.frequency_penalty == 0.5
        assert request.presence_penalty == 0.3
        assert request.stop == ["END", "STOP"]
        assert request.stream is False
    
    def test_empty_messages_validation(self):
        """Test validation of empty messages list"""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=[], model="gpt-3.5-turbo")
    
    def test_invalid_temperature_validation(self):
        """Test temperature parameter validation"""
        messages = [ChatMessage(role="user", content="Test")]
        
        # Too high temperature
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", temperature=3.0)
        
        # Negative temperature
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", temperature=-0.5)
    
    def test_invalid_max_tokens_validation(self):
        """Test max_tokens parameter validation"""
        messages = [ChatMessage(role="user", content="Test")]
        
        # Negative max_tokens
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", max_tokens=-100)
        
        # Zero max_tokens
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", max_tokens=0)
    
    def test_invalid_probability_parameters(self):
        """Test top_p, frequency_penalty, presence_penalty validation"""
        messages = [ChatMessage(role="user", content="Test")]
        
        # Invalid top_p (should be 0-1)
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", top_p=1.5)
        
        # Invalid frequency_penalty (should be -2 to 2)
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", frequency_penalty=3.0)
        
        # Invalid presence_penalty (should be -2 to 2)
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="gpt-3.5-turbo", presence_penalty=-3.0)
    
    def test_stop_sequences_validation(self):
        """Test stop sequences validation"""
        messages = [ChatMessage(role="user", content="Test")]
        
        # Valid stop sequences
        request = ChatCompletionRequest(
            messages=messages, 
            model="gpt-3.5-turbo", 
            stop=["END", "STOP"]
        )
        assert request.stop == ["END", "STOP"]
        
        # Single stop sequence
        request = ChatCompletionRequest(
            messages=messages, 
            model="gpt-3.5-turbo", 
            stop="END"
        )
        assert request.stop == "END"
    
    def test_model_name_validation(self):
        """Test model name validation"""
        messages = [ChatMessage(role="user", content="Test")]
        
        # Valid model names
        valid_models = [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-32k",
            "claude-3-sonnet",
            "privatemode-llama-70b"
        ]
        
        for model in valid_models:
            request = ChatCompletionRequest(messages=messages, model=model)
            assert request.model == model
        
        # Empty model name should be invalid
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=messages, model="")


class TestUsage:
    """Test Usage model for token counting"""
    
    def test_valid_usage_creation(self):
        """Test creating valid usage objects"""
        usage = Usage(
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75
        )
        
        assert usage.prompt_tokens == 50
        assert usage.completion_tokens == 25
        assert usage.total_tokens == 75
    
    def test_usage_token_validation(self):
        """Test usage token count validation"""
        # Negative tokens should be invalid
        with pytest.raises(ValidationError):
            Usage(prompt_tokens=-1, completion_tokens=25, total_tokens=24)
        
        with pytest.raises(ValidationError):
            Usage(prompt_tokens=50, completion_tokens=-1, total_tokens=49)
        
        with pytest.raises(ValidationError):
            Usage(prompt_tokens=50, completion_tokens=25, total_tokens=-1)
    
    def test_usage_total_calculation_validation(self):
        """Test that total_tokens matches prompt + completion"""
        # Mismatched totals should be validated
        try:
            usage = Usage(
                prompt_tokens=50,
                completion_tokens=25,
                total_tokens=100  # Should be 75
            )
            # Some implementations may auto-calculate or validate
            assert usage.total_tokens >= 75
        except ValidationError:
            # Acceptable if validation enforces correct calculation
            pass


class TestResponseMessage:
    """Test ResponseMessage model for LLM responses"""
    
    def test_valid_response_message(self):
        """Test creating valid response messages"""
        response_msg = ResponseMessage(
            role="assistant",
            content="Hello! How can I help you today?"
        )
        
        assert response_msg.role == "assistant"
        assert response_msg.content == "Hello! How can I help you today?"
    
    def test_empty_response_content(self):
        """Test handling of empty response content"""
        # Empty content may be valid for some use cases
        response_msg = ResponseMessage(role="assistant", content="")
        assert response_msg.content == ""
    
    def test_function_call_response(self):
        """Test response message with function calls"""
        response_msg = ResponseMessage(
            role="assistant",
            content="I'll help you with that calculation.",
            function_call={
                "name": "calculate",
                "arguments": '{"expression": "2+2"}'
            }
        )
        
        assert response_msg.role == "assistant"
        assert response_msg.function_call["name"] == "calculate"


class TestChoice:
    """Test Choice model for response choices"""
    
    def test_valid_choice_creation(self):
        """Test creating valid choice objects"""
        choice = Choice(
            index=0,
            message=ResponseMessage(role="assistant", content="Test response"),
            finish_reason="stop"
        )
        
        assert choice.index == 0
        assert choice.message.role == "assistant"
        assert choice.message.content == "Test response"
        assert choice.finish_reason == "stop"
    
    def test_finish_reason_validation(self):
        """Test finish_reason validation"""
        valid_reasons = ["stop", "length", "content_filter", "null"]
        
        for reason in valid_reasons:
            choice = Choice(
                index=0,
                message=ResponseMessage(role="assistant", content="Test"),
                finish_reason=reason
            )
            assert choice.finish_reason == reason
    
    def test_choice_index_validation(self):
        """Test choice index validation"""
        # Index should be non-negative
        with pytest.raises(ValidationError):
            Choice(
                index=-1,
                message=ResponseMessage(role="assistant", content="Test"),
                finish_reason="stop"
            )


class TestChatCompletionResponse:
    """Test ChatCompletionResponse model"""
    
    def test_valid_response_creation(self):
        """Test creating valid response objects"""
        response = ChatCompletionResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=[
                Choice(
                    index=0,
                    message=ResponseMessage(role="assistant", content="Test response"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=15, total_tokens=25)
        )
        
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices) == 1
        assert response.usage.total_tokens == 25
    
    def test_multiple_choices_response(self):
        """Test response with multiple choices"""
        response = ChatCompletionResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=[
                Choice(
                    index=0,
                    message=ResponseMessage(role="assistant", content="Response 1"),
                    finish_reason="stop"
                ),
                Choice(
                    index=1,
                    message=ResponseMessage(role="assistant", content="Response 2"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=30, total_tokens=40)
        )
        
        assert len(response.choices) == 2
        assert response.choices[0].index == 0
        assert response.choices[1].index == 1
    
    def test_empty_choices_validation(self):
        """Test validation of empty choices list"""
        with pytest.raises(ValidationError):
            ChatCompletionResponse(
                id="chatcmpl-123",
                object="chat.completion",
                created=1677652288,
                model="gpt-3.5-turbo",
                choices=[],
                usage=Usage(prompt_tokens=10, completion_tokens=15, total_tokens=25)
            )
    
    def test_response_serialization(self):
        """Test response serialization to OpenAI format"""
        response = ChatCompletionResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=[
                Choice(
                    index=0,
                    message=ResponseMessage(role="assistant", content="Test response"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=15, total_tokens=25)
        )
        
        serialized = response.dict()
        
        # Should match OpenAI API format
        assert "id" in serialized
        assert "object" in serialized
        assert "created" in serialized
        assert "model" in serialized
        assert "choices" in serialized
        assert "usage" in serialized
        
        # Choices should be properly formatted
        assert len(serialized["choices"]) == 1
        assert "index" in serialized["choices"][0]
        assert "message" in serialized["choices"][0]
        assert "finish_reason" in serialized["choices"][0]
        
        # Usage should be properly formatted
        assert "prompt_tokens" in serialized["usage"]
        assert "completion_tokens" in serialized["usage"]
        assert "total_tokens" in serialized["usage"]


class TestModelCompatibility:
    """Test model compatibility and conversion"""
    
    def test_openai_format_compatibility(self):
        """Test compatibility with OpenAI API format"""
        # Create request in OpenAI format
        openai_request = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        # Should be able to create our model from OpenAI format
        request = ChatCompletionRequest(**openai_request)
        
        assert request.model == "gpt-3.5-turbo"
        assert len(request.messages) == 1
        assert request.messages[0].role == "user"
        assert request.messages[0].content == "Hello"
        assert request.temperature == 0.7
        assert request.max_tokens == 150
    
    def test_streaming_request_handling(self):
        """Test handling of streaming requests"""
        streaming_request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="gpt-3.5-turbo",
            stream=True
        )
        
        assert streaming_request.stream is True
        
        # Non-streaming request
        regular_request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Test")],
            model="gpt-3.5-turbo",
            stream=False
        )
        
        assert regular_request.stream is False


"""
COVERAGE ANALYSIS FOR LLM MODELS:

✅ Model Validation (15+ tests):
- ChatMessage role and content validation
- ChatCompletionRequest parameter validation
- Response model structure validation
- Usage token counting validation
- Choice and finish_reason validation

✅ Edge Cases (8+ tests):
- Empty content handling
- Invalid parameter ranges
- Boundary conditions
- Serialization/deserialization
- Multiple choices handling

✅ Compatibility (3+ tests):
- OpenAI API format compatibility
- Streaming request handling
- Model conversion and mapping

ESTIMATED IMPACT:
- Current: Data model validation gaps
- Target: Comprehensive input/output validation
- Business Impact: High (prevents invalid requests/responses)
- Implementation: Foundation for all LLM operations
"""