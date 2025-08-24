"""
Performance tests for the new LLM service.
Tests response times, throughput, and resource usage.
"""
import pytest
import asyncio
import time
import statistics
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from typing import List


class TestLLMPerformance:
    """Performance tests for LLM service."""

    @pytest.mark.asyncio
    async def test_chat_completion_latency(self, client: AsyncClient):
        """Test chat completion response latency."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        # Mock fast response
        mock_response = ChatCompletionResponse(
            id="perf-test",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Performance test response."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
        )
        
        latencies = []
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            # Measure latency over multiple requests
            for i in range(10):
                start_time = time.time()
                
                response = await client.post(
                    "/api/v1/llm/chat/completions",
                    json={
                        "model": "privatemode-llama-3-70b",
                        "messages": [
                            {"role": "user", "content": f"Performance test {i}"}
                        ]
                    },
                    headers={"Authorization": "Bearer test-api-key"}
                )
                
                latency = (time.time() - start_time) * 1000  # Convert to milliseconds
                latencies.append(latency)
                
                assert response.status_code == 200
        
        # Analyze performance metrics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        print(f"Average latency: {avg_latency:.2f}ms")
        print(f"P95 latency: {p95_latency:.2f}ms")
        print(f"P99 latency: {p99_latency:.2f}ms")
        
        # Performance assertions (for mocked responses, should be very fast)
        assert avg_latency < 100  # Less than 100ms average
        assert p95_latency < 200   # Less than 200ms for 95% of requests
        assert p99_latency < 500   # Less than 500ms for 99% of requests

    @pytest.mark.asyncio
    async def test_concurrent_throughput(self, client: AsyncClient):
        """Test concurrent request throughput."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        mock_response = ChatCompletionResponse(
            id="throughput-test",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Throughput test response."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12
            )
        )
        
        concurrent_levels = [1, 5, 10, 20]
        throughput_results = {}
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            for concurrency in concurrent_levels:
                start_time = time.time()
                
                # Create concurrent requests
                tasks = []
                for i in range(concurrency):
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
                
                # Execute all requests
                responses = await asyncio.gather(*tasks)
                elapsed_time = time.time() - start_time
                
                # Verify all requests succeeded
                for response in responses:
                    assert response.status_code == 200
                
                # Calculate throughput (requests per second)
                throughput = concurrency / elapsed_time
                throughput_results[concurrency] = throughput
                
                print(f"Concurrency {concurrency}: {throughput:.2f} req/s")
        
        # Performance assertions
        assert throughput_results[1] > 10    # At least 10 req/s for single requests
        assert throughput_results[5] > 30    # At least 30 req/s for 5 concurrent
        assert throughput_results[10] > 50   # At least 50 req/s for 10 concurrent

    @pytest.mark.asyncio
    async def test_embedding_performance(self, client: AsyncClient):
        """Test embedding generation performance."""
        from app.services.llm.models import EmbeddingResponse, EmbeddingData, Usage
        
        # Create realistic embedding response
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
                prompt_tokens=10,
                total_tokens=10
            )
        )
        
        latencies = []
        
        with patch("app.services.llm.service.llm_service.create_embedding") as mock_embedding:
            mock_embedding.return_value = mock_response
            
            # Test different text lengths
            test_texts = [
                "Short text",
                "Medium length text that contains more words and should take a bit longer to process.",
                "Very long text that contains many words and sentences. " * 10,  # Repeat to make it longer
            ]
            
            for text in test_texts:
                start_time = time.time()
                
                response = await client.post(
                    "/api/v1/llm/embeddings",
                    json={
                        "model": "privatemode-embeddings",
                        "input": text
                    },
                    headers={"Authorization": "Bearer test-api-key"}
                )
                
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["data"][0]["embedding"]) == 1024
        
        # Performance assertions for embeddings
        avg_latency = statistics.mean(latencies)
        print(f"Average embedding latency: {avg_latency:.2f}ms")
        
        assert avg_latency < 150  # Less than 150ms average for embeddings

    @pytest.mark.asyncio
    async def test_provider_status_performance(self, client: AsyncClient):
        """Test provider status endpoint performance."""
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
        
        latencies = []
        
        with patch("app.services.llm.service.llm_service.get_provider_status") as mock_provider:
            mock_provider.return_value = mock_status
            
            # Measure status endpoint performance
            for i in range(10):
                start_time = time.time()
                
                response = await client.get(
                    "/api/v1/llm/providers/status",
                    headers={"Authorization": "Bearer test-api-key"}
                )
                
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                
                assert response.status_code == 200
        
        avg_latency = statistics.mean(latencies)
        print(f"Average provider status latency: {avg_latency:.2f}ms")
        
        # Status endpoint should be very fast
        assert avg_latency < 50  # Less than 50ms for status checks

    @pytest.mark.asyncio
    async def test_models_endpoint_performance(self, client: AsyncClient):
        """Test models listing endpoint performance."""
        from app.services.llm.models import Model
        
        # Create a realistic number of models
        mock_models = []
        for i in range(20):  # Simulate 20 available models
            mock_models.append(
                Model(
                    id=f"privatemode-model-{i}",
                    object="model",
                    created=1234567890,
                    owned_by="PrivateMode.ai",
                    provider="PrivateMode.ai",
                    capabilities=["tee", "chat"],
                    context_window=32768 if i % 2 == 0 else 8192,
                    supports_streaming=True,
                    supports_function_calling=i % 3 == 0
                )
            )
        
        latencies = []
        
        with patch("app.services.llm.service.llm_service.get_models") as mock_models_call:
            mock_models_call.return_value = mock_models
            
            # Measure models endpoint performance
            for i in range(10):
                start_time = time.time()
                
                response = await client.get(
                    "/api/v1/llm/models",
                    headers={"Authorization": "Bearer test-api-key"}
                )
                
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["data"]) == 20
        
        avg_latency = statistics.mean(latencies)
        print(f"Average models endpoint latency: {avg_latency:.2f}ms")
        
        # Models endpoint should be reasonably fast even with many models
        assert avg_latency < 100  # Less than 100ms for models listing

    @pytest.mark.asyncio
    async def test_error_handling_performance(self, client: AsyncClient):
        """Test that error handling doesn't significantly impact performance."""
        error_latencies = []
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.side_effect = Exception("Simulated provider error")
            
            # Measure error handling performance
            for i in range(5):
                start_time = time.time()
                
                response = await client.post(
                    "/api/v1/llm/chat/completions",
                    json={
                        "model": "privatemode-llama-3-70b",
                        "messages": [
                            {"role": "user", "content": f"Error test {i}"}
                        ]
                    },
                    headers={"Authorization": "Bearer test-api-key"}
                )
                
                latency = (time.time() - start_time) * 1000
                error_latencies.append(latency)
                
                # Should return error but quickly
                assert response.status_code in [500, 503]
        
        avg_error_latency = statistics.mean(error_latencies)
        print(f"Average error handling latency: {avg_error_latency:.2f}ms")
        
        # Error handling should be fast
        assert avg_error_latency < 200  # Less than 200ms for error responses

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, client: AsyncClient):
        """Test memory efficiency during concurrent operations."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        # Create a larger response to test memory handling
        large_content = "This is a large response. " * 100  # ~2.5KB content
        
        mock_response = ChatCompletionResponse(
            id="memory-test",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=large_content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=50,
                completion_tokens=500,
                total_tokens=550
            )
        )
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            # Create many concurrent requests to test memory efficiency
            tasks = []
            for i in range(50):  # 50 concurrent requests with large responses
                task = client.post(
                    "/api/v1/llm/chat/completions",
                    json={
                        "model": "privatemode-llama-3-70b",
                        "messages": [
                            {"role": "user", "content": f"Memory test {i}"}
                        ]
                    },
                    headers={"Authorization": "Bearer test-api-key"}
                )
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks)
            elapsed_time = time.time() - start_time
            
            # Verify all requests succeeded
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert len(data["choices"][0]["message"]["content"]) > 2000
        
        print(f"50 concurrent large requests completed in {elapsed_time:.2f}s")
        
        # Should handle 50 concurrent requests with large responses efficiently
        assert elapsed_time < 5.0  # Less than 5 seconds for 50 concurrent requests

    @pytest.mark.asyncio
    async def test_security_analysis_performance(self, client: AsyncClient):
        """Test performance impact of security analysis."""
        from app.services.llm.models import ChatCompletionResponse, ChatChoice, ChatMessage, Usage
        
        # Mock response with security analysis
        mock_response = ChatCompletionResponse(
            id="security-perf-test",
            object="chat.completion",
            created=int(time.time()),
            model="privatemode-llama-3-70b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Secure response with analysis."
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=15,
                completion_tokens=8,
                total_tokens=23
            ),
            security_analysis={
                "risk_score": 0.1,
                "threats_detected": [],
                "risk_level": "low",
                "analysis_time_ms": 25.5
            }
        )
        
        latencies = []
        
        with patch("app.services.llm.service.llm_service.create_chat_completion") as mock_chat:
            mock_chat.return_value = mock_response
            
            # Measure latency with security analysis
            for i in range(10):
                start_time = time.time()
                
                response = await client.post(
                    "/api/v1/llm/chat/completions",
                    json={
                        "model": "privatemode-llama-3-70b",
                        "messages": [
                            {"role": "user", "content": f"Security test {i}"}
                        ]
                    },
                    headers={"Authorization": "Bearer test-api-key"}
                )
                
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                
                assert response.status_code == 200
                data = response.json()
                assert "security_analysis" in data
        
        avg_latency = statistics.mean(latencies)
        print(f"Average latency with security analysis: {avg_latency:.2f}ms")
        
        # Security analysis should not significantly impact performance
        assert avg_latency < 150  # Less than 150ms with security analysis