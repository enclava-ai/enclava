"""
LiteLLM Client Service
Handles communication with the LiteLLM proxy service
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import aiohttp
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class LiteLLMClient:
    """Client for communicating with LiteLLM proxy service"""
    
    def __init__(self):
        self.base_url = settings.LITELLM_BASE_URL
        self.master_key = settings.LITELLM_MASTER_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=600)  # 10 minutes timeout
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.master_key}"
                }
            )
        return self.session
    
    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check LiteLLM proxy health"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"LiteLLM health check failed: {response.status}")
                    return {"status": "unhealthy", "error": f"HTTP {response.status}"}
        except Exception as e:
            logger.error(f"LiteLLM health check error: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """Get available models from LiteLLM"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.error(f"Failed to get models: {response.status}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="LiteLLM service unavailable"
                    )
        except aiohttp.ClientError as e:
            logger.error(f"LiteLLM models request error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiteLLM service unavailable"
            )
    
    async def create_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        user_id: str,
        api_key_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Create chat completion via LiteLLM proxy"""
        try:
            # Prepare request payload
            payload = {
                "model": model,
                "messages": messages,
                "user": f"user_{user_id}",  # User identifier for tracking
                "metadata": {
                    "api_key_id": api_key_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                **kwargs
            }
            
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"LiteLLM chat completion failed: {response.status} - {error_text}")
                    
                    # Handle specific error cases
                    if response.status == 401:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid API key"
                        )
                    elif response.status == 429:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Rate limit exceeded"
                        )
                    elif response.status == 400:
                        try:
                            error_data = await response.json()
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=error_data.get("error", {}).get("message", "Bad request")
                            )
                        except:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid request"
                            )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="LiteLLM service error"
                        )
        except aiohttp.ClientError as e:
            logger.error(f"LiteLLM chat completion request error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiteLLM service unavailable"
            )
    
    async def create_embedding(
        self,
        model: str,
        input_text: str,
        user_id: str,
        api_key_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Create embedding via LiteLLM proxy"""
        try:
            payload = {
                "model": model,
                "input": input_text,
                "user": f"user_{user_id}",
                "metadata": {
                    "api_key_id": api_key_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                **kwargs
            }
            
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/embeddings",
                json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"LiteLLM embedding failed: {response.status} - {error_text}")
                    
                    if response.status == 401:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid API key"
                        )
                    elif response.status == 429:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Rate limit exceeded"
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="LiteLLM service error"
                        )
        except aiohttp.ClientError as e:
            logger.error(f"LiteLLM embedding request error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiteLLM service unavailable"
            )
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """Get available models from LiteLLM proxy"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    # Return models with exact names from upstream providers
                    models = data.get("data", [])
                    
                    # Pass through model names exactly as they come from upstream
                    # Don't modify model IDs - keep them as the original provider names
                    processed_models = []
                    for model in models:
                        # Keep the exact model ID from upstream provider
                        processed_models.append({
                            "id": model.get("id", ""),  # Exact model name from provider
                            "object": model.get("object", "model"),
                            "created": model.get("created", 1677610602),
                            "owned_by": model.get("owned_by", "openai")
                        })
                    
                    return processed_models
                else:
                    error_text = await response.text()
                    logger.error(f"LiteLLM models request failed: {response.status} - {error_text}")
                    return []
        except aiohttp.ClientError as e:
            logger.error(f"LiteLLM models request error: {e}")
            return []
    
    async def proxy_request(
        self,
        method: str,
        endpoint: str,
        payload: Dict[str, Any],
        user_id: str,
        api_key_id: int
    ) -> Dict[str, Any]:
        """Generic proxy request to LiteLLM"""
        try:
            # Add metadata to payload
            if isinstance(payload, dict):
                payload["metadata"] = {
                    "api_key_id": api_key_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                if "user" not in payload:
                    payload["user"] = f"user_{user_id}"
            
            session = await self._get_session()
            
            # Make the request
            async with session.request(
                method,
                f"{self.base_url}/{endpoint.lstrip('/')}",
                json=payload if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                params=payload if method.upper() == 'GET' else None
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"LiteLLM proxy request failed: {response.status} - {error_text}")
                    
                    if response.status == 401:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid API key"
                        )
                    elif response.status == 429:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Rate limit exceeded"
                        )
                    else:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"LiteLLM service error: {error_text}"
                        )
        except aiohttp.ClientError as e:
            logger.error(f"LiteLLM proxy request error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiteLLM service unavailable"
            )
    
    async def list_models(self) -> List[str]:
        """Get list of available model names/IDs"""
        try:
            models_data = await self.get_models()
            return [model.get("id", model.get("model", "")) for model in models_data if model.get("id") or model.get("model")]
        except Exception as e:
            logger.error(f"Error listing model names: {str(e)}")
            return []


# Global LiteLLM client instance
litellm_client = LiteLLMClient()