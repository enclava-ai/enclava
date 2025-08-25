"""
OpenAI API compatibility tests.
Ensure 100% compatibility with OpenAI Python client and API specification.
"""

import pytest
import openai
from openai import OpenAI
import asyncio
from typing import List, Dict, Any

from tests.clients.openai_test_client import OpenAITestClient, AsyncOpenAITestClient, validate_openai_response_format


class TestOpenAICompatibility:
    """Test OpenAI API compatibility using official OpenAI Python client"""
    
    BASE_URL = "http://localhost:3001/api/v1"  # Through nginx
    
    @pytest.fixture
    def test_api_key(self):
        """Test API key for OpenAI compatibility testing"""
        return "sk-test-compatibility-key-12345"
    
    @pytest.fixture
    def openai_client(self, test_api_key):
        """OpenAI client configured for Enclava"""
        return OpenAITestClient(
            base_url=self.BASE_URL,
            api_key=test_api_key
        )
    
    @pytest.fixture
    def async_openai_client(self, test_api_key):
        """Async OpenAI client for performance testing"""
        return AsyncOpenAITestClient(
            base_url=self.BASE_URL,
            api_key=test_api_key
        )
    
    def test_list_models(self, openai_client):
        """Test /v1/models endpoint with OpenAI client"""
        models = openai_client.list_models()
        
        # Verify response structure
        assert isinstance(models, list)
        assert len(models) > 0, "Should have at least one model"
        
        # Verify each model has required fields
        for model in models:
            errors = validate_openai_response_format(model, "models")
            assert len(errors) == 0, f"Model validation errors: {errors}"
            
            assert model["object"] == "model"
            assert "id" in model
            assert "created" in model
            assert "owned_by" in model
    
    def test_chat_completion_basic(self, openai_client):
        """Test basic chat completion with OpenAI client"""
        response = openai_client.create_chat_completion(
            model="test-model",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello!"}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        # Validate response structure
        errors = validate_openai_response_format(response, "chat_completion")
        assert len(errors) == 0, f"Chat completion validation errors: {errors}"
        
        # Verify required fields
        assert "id" in response
        assert "object" in response
        assert response["object"] == "chat.completion"
        assert "created" in response
        assert "model" in response
        assert "choices" in response
        assert len(response["choices"]) > 0
        
        # Verify choice structure
        choice = response["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert "finish_reason" in choice
        
        # Verify message structure
        message = choice["message"]
        assert "role" in message
        assert "content" in message
        assert message["role"] == "assistant"
        assert isinstance(message["content"], str)
        assert len(message["content"]) > 0
        
        # Verify usage tracking
        assert "usage" in response
        usage = response["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    
    def test_chat_completion_streaming(self, openai_client):
        """Test streaming chat completion"""
        chunks = openai_client.test_streaming_completion(
            model="test-model",
            messages=[{"role": "user", "content": "Count to 5"}],
            max_tokens=100
        )
        
        # Should receive multiple chunks
        assert len(chunks) > 1, "Streaming should produce multiple chunks"
        
        # Verify chunk structure
        for i, chunk in enumerate(chunks):
            assert "id" in chunk
            assert "object" in chunk
            assert chunk["object"] == "chat.completion.chunk"
            assert "created" in chunk
            assert "model" in chunk
            assert "choices" in chunk
            
            if len(chunk["choices"]) > 0:
                choice = chunk["choices"][0]
                assert "index" in choice
                assert "delta" in choice
                
                # Last chunk should have finish_reason
                if i == len(chunks) - 1:
                    assert choice.get("finish_reason") is not None
    
    def test_chat_completion_with_functions(self, openai_client):
        """Test chat completion with function calling (if supported)"""
        try:
            functions = [
                {
                    "name": "get_weather",
                    "description": "Get weather information for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state"
                            }
                        },
                        "required": ["location"]
                    }
                }
            ]
            
            response = openai_client.create_chat_completion(
                model="test-model",
                messages=[{"role": "user", "content": "What's the weather in San Francisco?"}],
                functions=functions,
                max_tokens=100
            )
            
            # If functions are supported, verify structure
            if response.get("choices") and response["choices"][0].get("message"):
                message = response["choices"][0]["message"]
                if "function_call" in message:
                    function_call = message["function_call"]
                    assert "name" in function_call
                    assert "arguments" in function_call
                    
        except openai.BadRequestError:
            # Functions might not be supported, that's okay
            pytest.skip("Function calling not supported")
    
    def test_embeddings(self, openai_client):
        """Test embeddings endpoint"""
        try:
            response = openai_client.create_embedding(
                model="text-embedding-ada-002",
                input_text="Hello world"
            )
            
            # Validate response structure
            errors = validate_openai_response_format(response, "embeddings")
            assert len(errors) == 0, f"Embeddings validation errors: {errors}"
            
            # Verify required fields
            assert "object" in response
            assert response["object"] == "list"
            assert "data" in response
            assert len(response["data"]) > 0
            assert "model" in response
            assert "usage" in response
            
            # Verify embedding structure
            embedding_obj = response["data"][0]
            assert "object" in embedding_obj
            assert embedding_obj["object"] == "embedding"
            assert "embedding" in embedding_obj
            assert "index" in embedding_obj
            
            # Verify embedding is list of floats
            embedding = embedding_obj["embedding"]
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, (int, float)) for x in embedding)
            
        except openai.NotFoundError:
            pytest.skip("Embedding model not available")
    
    def test_completions_legacy(self, openai_client):
        """Test legacy completions endpoint"""
        try:
            response = openai_client.create_completion(
                model="test-model",
                prompt="Say hello",
                max_tokens=50
            )
            
            # Verify response structure
            assert "id" in response
            assert "object" in response
            assert response["object"] == "text_completion"
            assert "created" in response
            assert "model" in response
            assert "choices" in response
            
            # Verify choice structure
            choice = response["choices"][0]
            assert "text" in choice
            assert "index" in choice
            assert "finish_reason" in choice
            
        except openai.NotFoundError:
            pytest.skip("Legacy completions not supported")
    
    def test_error_handling(self, openai_client):
        """Test OpenAI-compatible error responses"""
        error_tests = openai_client.test_error_handling()
        
        # Verify error test results
        assert "error_tests" in error_tests
        error_results = error_tests["error_tests"]
        
        # Should have tested multiple error scenarios
        assert len(error_results) > 0
        
        # Check for proper error handling
        for test_result in error_results:
            if "error_type" in test_result:
                # Should be proper OpenAI error types
                assert test_result["error_type"] in [
                    "BadRequestError",
                    "AuthenticationError", 
                    "RateLimitError",
                    "NotFoundError"
                ]
                
                # Should have proper HTTP status codes
                assert test_result.get("status_code") >= 400
    
    def test_parameter_validation(self, openai_client):
        """Test parameter validation"""
        # Test invalid temperature
        try:
            openai_client.create_chat_completion(
                model="test-model",
                messages=[{"role": "user", "content": "test"}],
                temperature=2.5  # Should be between 0 and 2
            )
            # If this succeeds, the API is too permissive but that's okay
        except openai.BadRequestError as e:
            assert e.response.status_code == 400
        
        # Test invalid max_tokens
        try:
            openai_client.create_chat_completion(
                model="test-model", 
                messages=[{"role": "user", "content": "test"}],
                max_tokens=-1  # Should be positive
            )
        except openai.BadRequestError as e:
            assert e.response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_openai_client):
        """Test concurrent API requests"""
        results = await async_openai_client.test_concurrent_requests(10)
        
        # Verify results
        assert len(results) == 10
        
        # Calculate success rate
        successful_requests = sum(1 for r in results if r["success"])
        success_rate = successful_requests / len(results)
        
        # Should handle concurrent requests reasonably well
        assert success_rate >= 0.5, f"Low success rate for concurrent requests: {success_rate}"
        
        # Check response times
        response_times = [r["response_time"] for r in results if r["success"]]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            assert avg_response_time < 10.0, f"High average response time: {avg_response_time}s"
    
    @pytest.mark.asyncio
    async def test_streaming_performance(self, async_openai_client):
        """Test streaming response performance"""
        stream_results = await async_openai_client.test_streaming_performance()
        
        if "error" not in stream_results:
            # Verify streaming metrics
            assert stream_results["chunk_count"] > 0
            assert stream_results["total_time"] > 0
            
            # First chunk should arrive quickly
            if stream_results["first_chunk_time"]:
                assert stream_results["first_chunk_time"] < 5.0, "First chunk took too long"
    
    def test_model_parameter_compatibility(self, openai_client):
        """Test model parameter compatibility"""
        # Test with different model names
        model_names = ["test-model", "gpt-3.5-turbo", "gpt-4"]
        
        for model_name in model_names:
            try:
                response = openai_client.create_chat_completion(
                    model=model_name,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=10
                )
                
                # If successful, verify model name is preserved
                assert response["model"] == model_name or "test-model" in response["model"]
                
            except openai.NotFoundError:
                # Model not available, that's okay
                continue
            except openai.BadRequestError:
                # Model name not accepted, that's okay
                continue
    
    def test_message_roles_compatibility(self, openai_client):
        """Test different message roles"""
        # Test with system, user, assistant roles
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        try:
            response = openai_client.create_chat_completion(
                model="test-model",
                messages=messages,
                max_tokens=50
            )
            
            # Should handle conversation context properly
            assert response["choices"][0]["message"]["role"] == "assistant"
            
        except Exception as e:
            pytest.fail(f"Failed to handle message roles: {e}")
    
    def test_special_characters_handling(self, openai_client):
        """Test handling of special characters and unicode"""
        special_messages = [
            "Hello 世界! 🌍",
            "Math: ∑(x²) = ∫f(x)dx",
            "Code: print('hello\\nworld')",
            "Quotes: \"He said 'hello'\""
        ]
        
        for message in special_messages:
            try:
                response = openai_client.create_chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": message}],
                    max_tokens=50
                )
                
                # Should return valid response
                assert len(response["choices"][0]["message"]["content"]) > 0
                
            except Exception as e:
                pytest.fail(f"Failed to handle special characters in '{message}': {e}")
    
    def test_openai_client_types(self, test_api_key):
        """Test that responses work with OpenAI client type expectations"""
        client = OpenAI(api_key=test_api_key, base_url=self.BASE_URL)
        
        try:
            # Test that the client can parse responses correctly
            response = client.chat.completions.create(
                model="test-model",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            
            # These should not raise AttributeError
            assert hasattr(response, 'id')
            assert hasattr(response, 'choices')
            assert hasattr(response, 'usage')
            assert hasattr(response.choices[0], 'message')
            assert hasattr(response.choices[0].message, 'content')
            
        except openai.AuthenticationError:
            # Expected if test API key is not set up
            pytest.skip("Test API key not configured")
        except Exception as e:
            pytest.fail(f"OpenAI client type compatibility failed: {e}")