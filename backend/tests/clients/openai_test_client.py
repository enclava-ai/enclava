"""
OpenAI-compatible test client for verifying API compatibility.
"""

import openai
from openai import OpenAI
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
import aiohttp
import json


class OpenAITestClient:
    """OpenAI client wrapper for testing Enclava compatibility"""
    
    def __init__(self, base_url: str = "http://localhost:3001/api/v1", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key or "test-api-key"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def list_models(self) -> List[Dict[str, Any]]:
        """Test /v1/models endpoint compatibility"""
        try:
            response = self.client.models.list()
            return [model.model_dump() for model in response.data]
        except Exception as e:
            raise OpenAICompatibilityError(f"Models list failed: {e}")
    
    def create_chat_completion(self,
                              model: str,
                              messages: List[Dict[str, str]],
                              stream: bool = False,
                              **kwargs) -> Dict[str, Any]:
        """Test chat completion endpoint compatibility"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=stream,
                **kwargs
            )
            
            if stream:
                return {"stream": response}
            else:
                return response.model_dump()
                
        except Exception as e:
            raise OpenAICompatibilityError(f"Chat completion failed: {e}")
    
    def create_completion(self,
                         model: str,
                         prompt: str,
                         **kwargs) -> Dict[str, Any]:
        """Test legacy completion endpoint compatibility"""
        try:
            response = self.client.completions.create(
                model=model,
                prompt=prompt,
                **kwargs
            )
            return response.model_dump()
        except Exception as e:
            raise OpenAICompatibilityError(f"Completion failed: {e}")
    
    def create_embedding(self,
                        model: str,
                        input_text: str,
                        **kwargs) -> Dict[str, Any]:
        """Test embeddings endpoint compatibility"""
        try:
            response = self.client.embeddings.create(
                model=model,
                input=input_text,
                **kwargs
            )
            return response.model_dump()
        except Exception as e:
            raise OpenAICompatibilityError(f"Embeddings failed: {e}")
    
    def test_streaming_completion(self,
                                 model: str,
                                 messages: List[Dict[str, str]],
                                 **kwargs) -> List[Dict[str, Any]]:
        """Test streaming chat completion"""
        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs
            )
            
            chunks = []
            for chunk in stream:
                chunks.append(chunk.model_dump())
            
            return chunks
        except Exception as e:
            raise OpenAICompatibilityError(f"Streaming completion failed: {e}")
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test error response compatibility"""
        test_cases = []
        
        # Test invalid model
        try:
            self.client.chat.completions.create(
                model="nonexistent-model",
                messages=[{"role": "user", "content": "test"}]
            )
        except openai.BadRequestError as e:
            test_cases.append({
                "test": "invalid_model",
                "error_type": type(e).__name__,
                "status_code": e.response.status_code,
                "error_body": e.response.text if hasattr(e.response, 'text') else str(e)
            })
        
        # Test missing API key
        try:
            no_key_client = OpenAI(base_url=self.base_url, api_key="")
            no_key_client.models.list()
        except openai.AuthenticationError as e:
            test_cases.append({
                "test": "missing_api_key",
                "error_type": type(e).__name__,
                "status_code": e.response.status_code,
                "error_body": e.response.text if hasattr(e.response, 'text') else str(e)
            })
        
        # Test rate limiting (if implemented)
        try:
            for _ in range(100):  # Attempt to trigger rate limiting
                self.client.chat.completions.create(
                    model="test-model",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
        except openai.RateLimitError as e:
            test_cases.append({
                "test": "rate_limiting",
                "error_type": type(e).__name__,
                "status_code": e.response.status_code,
                "error_body": e.response.text if hasattr(e.response, 'text') else str(e)
            })
        except Exception:
            # Rate limiting might not be triggered, that's okay
            test_cases.append({
                "test": "rate_limiting",
                "result": "no_rate_limit_triggered"
            })
        
        return {"error_tests": test_cases}


class AsyncOpenAITestClient:
    """Async version of OpenAI test client for concurrent testing"""
    
    def __init__(self, base_url: str = "http://localhost:3001/api/v1", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key or "test-api-key"
        
    async def test_concurrent_requests(self, num_requests: int = 10) -> List[Dict[str, Any]]:
        """Test concurrent API requests"""
        async def make_request(session: aiohttp.ClientSession, request_id: int) -> Dict[str, Any]:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "model": "test-model",
                "messages": [{"role": "user", "content": f"Request {request_id}"}],
                "max_tokens": 50
            }
            
            start_time = asyncio.get_event_loop().time()
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    end_time = asyncio.get_event_loop().time()
                    response_data = await response.json()
                    
                    return {
                        "request_id": request_id,
                        "status_code": response.status,
                        "response_time": end_time - start_time,
                        "success": response.status == 200,
                        "response": response_data if response.status == 200 else None,
                        "error": response_data if response.status != 200 else None
                    }
            except Exception as e:
                end_time = asyncio.get_event_loop().time()
                return {
                    "request_id": request_id,
                    "status_code": None,
                    "response_time": end_time - start_time,
                    "success": False,
                    "error": str(e)
                }
        
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session, i) for i in range(num_requests)]
            results = await asyncio.gather(*tasks)
            
            return results
    
    async def test_streaming_performance(self) -> Dict[str, Any]:
        """Test streaming response performance"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Generate a long response about AI"}],
            "stream": True,
            "max_tokens": 500
        }
        
        chunk_times = []
        chunks = []
        start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                
                if response.status != 200:
                    return {"error": f"Request failed with status {response.status}"}
                
                async for line in response.content:
                    if line:
                        current_time = asyncio.get_event_loop().time()
                        try:
                            # Parse SSE format
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]  # Remove 'data: ' prefix
                                if data_str != '[DONE]':
                                    chunk_data = json.loads(data_str)
                                    chunks.append(chunk_data)
                                    chunk_times.append(current_time - start_time)
                        except json.JSONDecodeError:
                            continue
        
        end_time = asyncio.get_event_loop().time()
        
        return {
            "total_time": end_time - start_time,
            "chunk_count": len(chunks),
            "chunk_times": chunk_times,
            "avg_chunk_interval": sum(chunk_times) / len(chunk_times) if chunk_times else 0,
            "first_chunk_time": chunk_times[0] if chunk_times else None
        }


class OpenAICompatibilityError(Exception):
    """Custom exception for OpenAI compatibility test failures"""
    pass


def validate_openai_response_format(response: Dict[str, Any], endpoint_type: str) -> List[str]:
    """Validate response format matches OpenAI specification"""
    errors = []
    
    if endpoint_type == "chat_completion":
        required_fields = ["id", "object", "created", "model", "choices"]
        for field in required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")
        
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" not in choice:
                errors.append("Missing 'message' in choice")
            elif "content" not in choice["message"]:
                errors.append("Missing 'content' in message")
        
        if "usage" in response:
            usage_fields = ["prompt_tokens", "completion_tokens", "total_tokens"]
            for field in usage_fields:
                if field not in response["usage"]:
                    errors.append(f"Missing usage field: {field}")
    
    elif endpoint_type == "models":
        if not isinstance(response, list):
            errors.append("Models response should be a list")
        else:
            for model in response:
                model_fields = ["id", "object", "created", "owned_by"]
                for field in model_fields:
                    if field not in model:
                        errors.append(f"Missing model field: {field}")
    
    elif endpoint_type == "embeddings":
        required_fields = ["object", "data", "model", "usage"]
        for field in required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")
        
        if "data" in response and len(response["data"]) > 0:
            embedding = response["data"][0]
            if "embedding" not in embedding:
                errors.append("Missing 'embedding' in data")
            elif not isinstance(embedding["embedding"], list):
                errors.append("Embedding should be a list of floats")
    
    return errors