"""
Chatbot API test client for comprehensive workflow testing.
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
import json
import time
from pathlib import Path


class ChatbotAPITestClient:
    """Test client for chatbot API workflows"""
    
    def __init__(self, base_url: str = "http://localhost:3001"):
        self.base_url = base_url.rstrip('/')
        self.session_timeout = aiohttp.ClientTimeout(total=60)
        self.auth_token = None
        self.api_key = None
    
    async def authenticate(self, email: str = "test@example.com", password: str = "testpass123") -> Dict[str, Any]:
        """Authenticate user and get JWT token"""
        login_data = {"email": email, "password": password}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api-internal/v1/auth/login",
                json=login_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.auth_token = result.get("access_token")
                    return {"success": True, "token": self.auth_token}
                else:
                    error = await response.text()
                    return {"success": False, "error": error, "status": response.status}
    
    async def register_user(self, email: str, password: str, username: str) -> Dict[str, Any]:
        """Register a new user"""
        user_data = {
            "email": email,
            "password": password,
            "username": username
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api-internal/v1/auth/register",
                json=user_data
            ) as response:
                result = await response.json() if response.content_type == 'application/json' else await response.text()
                return {
                    "status_code": response.status,
                    "success": response.status == 201,
                    "data": result
                }
    
    async def create_rag_collection(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a RAG collection"""
        if not self.auth_token:
            return {"error": "Not authenticated"}
        
        collection_data = {
            "name": name,
            "description": description,
            "processing_config": {
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        }
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api-internal/v1/rag/collections",
                json=collection_data,
                headers=headers
            ) as response:
                result = await response.json() if response.content_type == 'application/json' else await response.text()
                return {
                    "status_code": response.status,
                    "success": response.status == 201,
                    "data": result
                }
    
    async def upload_document(self, collection_id: str, file_content: str, filename: str) -> Dict[str, Any]:
        """Upload document to RAG collection"""
        if not self.auth_token:
            return {"error": "Not authenticated"}
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        # Create form data
        data = aiohttp.FormData()
        data.add_field('file', file_content, filename=filename, content_type='text/plain')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api-internal/v1/rag/collections/{collection_id}/upload",
                data=data,
                headers=headers
            ) as response:
                result = await response.json() if response.content_type == 'application/json' else await response.text()
                return {
                    "status_code": response.status,
                    "success": response.status == 201,
                    "data": result
                }
    
    async def wait_for_document_processing(self, document_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Wait for document processing to complete"""
        if not self.auth_token:
            return {"error": "Not authenticated"}
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < timeout:
                async with session.get(
                    f"{self.base_url}/api-internal/v1/rag/documents/{document_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        doc = await response.json()
                        status = doc.get("processing_status")
                        
                        if status == "completed":
                            return {"success": True, "status": "completed", "document": doc}
                        elif status == "failed":
                            return {"success": False, "status": "failed", "document": doc}
                        
                        await asyncio.sleep(1)
                    else:
                        return {"success": False, "error": f"Failed to check status: {response.status}"}
        
        return {"success": False, "error": "Timeout waiting for processing"}
    
    async def create_chatbot(self, 
                           name: str,
                           chatbot_type: str = "assistant",
                           use_rag: bool = False,
                           rag_collection: str = None,
                           **config) -> Dict[str, Any]:
        """Create a chatbot"""
        if not self.auth_token:
            return {"error": "Not authenticated"}
        
        chatbot_data = {
            "name": name,
            "chatbot_type": chatbot_type,
            "model": "test-model",
            "system_prompt": "You are a helpful assistant.",
            "use_rag": use_rag,
            "rag_collection": rag_collection,
            "rag_top_k": 3,
            "temperature": 0.7,
            "max_tokens": 1000,
            **config
        }
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api-internal/v1/chatbot/create",
                json=chatbot_data,
                headers=headers
            ) as response:
                result = await response.json() if response.content_type == 'application/json' else await response.text()
                return {
                    "status_code": response.status,
                    "success": response.status == 201,
                    "data": result
                }
    
    async def create_api_key_for_chatbot(self, chatbot_id: str, name: str = "Test API Key") -> Dict[str, Any]:
        """Create API key for chatbot"""
        if not self.auth_token:
            return {"error": "Not authenticated"}
        
        api_key_data = {
            "name": name,
            "scopes": ["chatbot.chat"],
            "budget_limit": 100.0,
            "chatbot_id": chatbot_id
        }
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api-internal/v1/chatbot/{chatbot_id}/api-key",
                json=api_key_data,
                headers=headers
            ) as response:
                result = await response.json() if response.content_type == 'application/json' else await response.text()
                if response.status == 201 and isinstance(result, dict):
                    self.api_key = result.get("key")
                return {
                    "status_code": response.status,
                    "success": response.status == 201,
                    "data": result
                }
    
    async def chat_with_bot(self, 
                          chatbot_id: str, 
                          message: str, 
                          conversation_id: Optional[str] = None,
                          api_key: Optional[str] = None) -> Dict[str, Any]:
        """Send message to chatbot"""
        if not api_key and not self.api_key:
            return {"error": "No API key available"}
        
        chat_data = {
            "message": message,
            "conversation_id": conversation_id
        }
        
        headers = {"Authorization": f"Bearer {api_key or self.api_key}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/chatbot/{chatbot_id}/chat",
                json=chat_data,
                headers=headers
            ) as response:
                result = await response.json() if response.content_type == 'application/json' else await response.text()
                return {
                    "status_code": response.status,
                    "success": response.status == 200,
                    "data": result
                }
    
    async def test_rag_workflow(self,
                              collection_name: str,
                              document_content: str,
                              chatbot_name: str,
                              test_question: str) -> Dict[str, Any]:
        """Test complete RAG workflow from document upload to chat"""
        workflow_results = {}
        
        # Step 1: Create RAG collection
        collection_result = await self.create_rag_collection(collection_name, "Test collection for workflow")
        workflow_results["collection_creation"] = collection_result
        
        if not collection_result["success"]:
            return {"success": False, "error": "Failed to create collection", "results": workflow_results}
        
        collection_id = collection_result["data"]["id"]
        
        # Step 2: Upload document
        document_result = await self.upload_document(collection_id, document_content, "test_doc.txt")
        workflow_results["document_upload"] = document_result
        
        if not document_result["success"]:
            return {"success": False, "error": "Failed to upload document", "results": workflow_results}
        
        document_id = document_result["data"]["id"]
        
        # Step 3: Wait for processing
        processing_result = await self.wait_for_document_processing(document_id)
        workflow_results["document_processing"] = processing_result
        
        if not processing_result["success"]:
            return {"success": False, "error": "Document processing failed", "results": workflow_results}
        
        # Step 4: Create chatbot with RAG
        chatbot_result = await self.create_chatbot(
            name=chatbot_name,
            use_rag=True,
            rag_collection=collection_name
        )
        workflow_results["chatbot_creation"] = chatbot_result
        
        if not chatbot_result["success"]:
            return {"success": False, "error": "Failed to create chatbot", "results": workflow_results}
        
        chatbot_id = chatbot_result["data"]["id"]
        
        # Step 5: Create API key
        api_key_result = await self.create_api_key_for_chatbot(chatbot_id)
        workflow_results["api_key_creation"] = api_key_result
        
        if not api_key_result["success"]:
            return {"success": False, "error": "Failed to create API key", "results": workflow_results}
        
        # Step 6: Test chat with RAG
        chat_result = await self.chat_with_bot(chatbot_id, test_question)
        workflow_results["chat_test"] = chat_result
        
        if not chat_result["success"]:
            return {"success": False, "error": "Chat test failed", "results": workflow_results}
        
        # Step 7: Verify RAG sources in response
        chat_response = chat_result["data"]
        has_sources = "sources" in chat_response and len(chat_response["sources"]) > 0
        workflow_results["rag_verification"] = {
            "has_sources": has_sources,
            "source_count": len(chat_response.get("sources", [])),
            "sources": chat_response.get("sources", [])
        }
        
        return {
            "success": True,
            "workflow_complete": True,
            "rag_working": has_sources,
            "results": workflow_results
        }
    
    async def test_conversation_memory(self, chatbot_id: str, api_key: str = None) -> Dict[str, Any]:
        """Test conversation memory functionality"""
        messages = [
            "My name is Alice and I like cats.",
            "What's my name?",
            "What do I like?"
        ]
        
        conversation_id = None
        results = []
        
        for i, message in enumerate(messages):
            result = await self.chat_with_bot(chatbot_id, message, conversation_id, api_key)
            
            if result["success"]:
                conversation_id = result["data"].get("conversation_id")
                results.append({
                    "message_index": i,
                    "message": message,
                    "response": result["data"].get("response"),
                    "conversation_id": conversation_id
                })
            else:
                results.append({
                    "message_index": i,
                    "message": message,
                    "error": result.get("error"),
                    "status_code": result.get("status_code")
                })
        
        # Analyze memory performance
        memory_working = False
        if len(results) >= 3:
            # Check if the bot remembers the name in the second response
            response2 = results[1].get("response", "").lower()
            response3 = results[2].get("response", "").lower()
            memory_working = "alice" in response2 and ("cat" in response3 or "like" in response3)
        
        return {
            "conversation_results": results,
            "memory_working": memory_working,
            "conversation_maintained": all(r.get("conversation_id") == results[0].get("conversation_id") for r in results if r.get("conversation_id"))
        }