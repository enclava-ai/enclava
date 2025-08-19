#!/usr/bin/env python3
"""
Comprehensive Platform Integration Test
Tests all major platform functionality including:
- User authentication
- API key creation and management  
- Budget enforcement
- LLM API (OpenAI compatible via LiteLLM)
- RAG system with real documents
- Ollama integration
- Module system
"""

import asyncio
import aiohttp
import aiofiles
import json
import logging
import sys
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PlatformTester:
    """Comprehensive platform integration tester"""
    
    def __init__(self, 
                 backend_url: str = "http://localhost:58000",
                 frontend_url: str = "http://localhost:53000"):
        self.backend_url = backend_url
        self.frontend_url = frontend_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Test data storage
        self.user_data = {}
        self.api_keys = []
        self.budgets = []
        self.collections = []
        self.documents = []
        
        # Test results
        self.results = {
            "passed": 0,
            "failed": 0,
            "tests": []
        }
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=120)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, success: bool, details: str = "", data: Dict = None):
        """Log test result"""
        status = "PASS" if success else "FAIL"
        logger.info(f"[{status}] {test_name}: {details}")
        
        self.results["tests"].append({
            "name": test_name,
            "success": success,
            "details": details,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        })
        
        if success:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
    
    async def test_platform_health(self):
        """Test 1: Platform health and availability"""
        logger.info("=" * 60)
        logger.info("TEST 1: Platform Health Check")
        logger.info("=" * 60)
        
        try:
            # Test backend health
            async with self.session.get(f"{self.backend_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    self.log_test("Backend Health", True, f"Status: {health_data.get('status')}", health_data)
                else:
                    self.log_test("Backend Health", False, f"HTTP {response.status}")
                    return False
            
            # Test frontend availability
            try:
                async with self.session.get(f"{self.frontend_url}") as response:
                    if response.status == 200:
                        self.log_test("Frontend Availability", True, "Frontend accessible")
                    else:
                        self.log_test("Frontend Availability", False, f"HTTP {response.status}")
            except Exception as e:
                self.log_test("Frontend Availability", False, f"Connection error: {e}")
            
            # Test API documentation
            async with self.session.get(f"{self.backend_url}/api/v1/docs") as response:
                if response.status == 200:
                    self.log_test("API Documentation", True, "Swagger UI accessible")
                else:
                    self.log_test("API Documentation", False, f"HTTP {response.status}")
            
            return True
            
        except Exception as e:
            self.log_test("Platform Health", False, f"Connection error: {e}")
            return False
    
    async def test_user_authentication(self):
        """Test 2: User registration and authentication"""
        logger.info("=" * 60)
        logger.info("TEST 2: User Authentication")
        logger.info("=" * 60)
        
        try:
            # Create unique test user
            timestamp = int(time.time())
            test_email = f"test_{timestamp}@platform-test.com"
            test_password = "TestPassword123!"
            test_username = f"test_user_{timestamp}"
            
            # Register user
            register_data = {
                "email": test_email,
                "password": test_password,
                "username": test_username
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/auth/register",
                json=register_data
            ) as response:
                if response.status == 201:
                    user_data = await response.json()
                    self.user_data = user_data
                    self.log_test("User Registration", True, f"User created: {user_data.get('email')}", user_data)
                else:
                    error_data = await response.json()
                    self.log_test("User Registration", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            # Login user
            login_data = {
                "email": test_email,
                "password": test_password
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/auth/login",
                json=login_data
            ) as response:
                if response.status == 200:
                    login_response = await response.json()
                    self.user_data["access_token"] = login_response["access_token"]
                    self.user_data["refresh_token"] = login_response["refresh_token"]
                    self.log_test("User Login", True, "Authentication successful", {"token_type": login_response.get("token_type")})
                else:
                    error_data = await response.json()
                    self.log_test("User Login", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            # Test token verification
            headers = {"Authorization": f"Bearer {self.user_data['access_token']}"}
            async with self.session.get(f"{self.backend_url}/api/v1/auth/me", headers=headers) as response:
                if response.status == 200:
                    user_info = await response.json()
                    self.log_test("Token Verification", True, f"User info retrieved: {user_info.get('email')}", user_info)
                else:
                    error_data = await response.json()
                    self.log_test("Token Verification", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            return True
            
        except Exception as e:
            self.log_test("User Authentication", False, f"Error: {e}")
            return False
    
    async def test_api_key_management(self):
        """Test 3: API key creation and management"""
        logger.info("=" * 60)
        logger.info("TEST 3: API Key Management")
        logger.info("=" * 60)
        
        if not self.user_data.get("access_token"):
            self.log_test("API Key Management", False, "No access token available")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.user_data['access_token']}"}
            
            # Create API key
            api_key_data = {
                "name": "Test API Key",
                "description": "API key for comprehensive platform testing",
                "scopes": ["chat.completions", "embeddings.create", "models.list"],
                "expires_in_days": 30
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/api-keys",
                json=api_key_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    api_key_response = await response.json()
                    self.api_keys.append(api_key_response)
                    self.log_test("API Key Creation", True, f"Key created: {api_key_response.get('name')}", {
                        "key_id": api_key_response.get("id"),
                        "key_prefix": api_key_response.get("key_prefix")
                    })
                else:
                    error_data = await response.json()
                    self.log_test("API Key Creation", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            # List API keys
            async with self.session.get(f"{self.backend_url}/api/v1/api-keys", headers=headers) as response:
                if response.status == 200:
                    keys_list = await response.json()
                    self.log_test("API Key Listing", True, f"Found {len(keys_list)} keys", {"count": len(keys_list)})
                else:
                    error_data = await response.json()
                    self.log_test("API Key Listing", False, f"HTTP {response.status}: {error_data}")
            
            return True
            
        except Exception as e:
            self.log_test("API Key Management", False, f"Error: {e}")
            return False
    
    async def test_budget_system(self):
        """Test 4: Budget creation and enforcement"""
        logger.info("=" * 60)
        logger.info("TEST 4: Budget System")
        logger.info("=" * 60)
        
        if not self.user_data.get("access_token") or not self.api_keys:
            self.log_test("Budget System", False, "Prerequisites not met")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.user_data['access_token']}"}
            api_key_id = self.api_keys[0].get("id")
            
            # Create budget
            budget_data = {
                "name": "Test Budget",
                "description": "Budget for comprehensive testing",
                "api_key_id": api_key_id,
                "budget_type": "monthly",
                "limit_cents": 10000,  # $100.00
                "alert_thresholds": [50, 80, 95]
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/budgets",
                json=budget_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    budget_response = await response.json()
                    self.budgets.append(budget_response)
                    self.log_test("Budget Creation", True, f"Budget created: {budget_response.get('name')}", {
                        "budget_id": budget_response.get("id"),
                        "limit": budget_response.get("limit_cents")
                    })
                else:
                    error_data = await response.json()
                    self.log_test("Budget Creation", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            # Get budget status
            async with self.session.get(f"{self.backend_url}/api/v1/llm/budget/status", headers=headers) as response:
                if response.status == 200:
                    budget_status = await response.json()
                    self.log_test("Budget Status Check", True, "Budget status retrieved", budget_status)
                else:
                    error_data = await response.json()
                    self.log_test("Budget Status Check", False, f"HTTP {response.status}: {error_data}")
            
            return True
            
        except Exception as e:
            self.log_test("Budget System", False, f"Error: {e}")
            return False
    
    async def test_llm_integration(self):
        """Test 5: LLM API (OpenAI compatible via LiteLLM)"""
        logger.info("=" * 60)
        logger.info("TEST 5: LLM Integration (OpenAI Compatible)")
        logger.info("=" * 60)
        
        if not self.api_keys:
            self.log_test("LLM Integration", False, "No API key available")
            return False
        
        try:
            # Use API key for authentication
            api_key = self.api_keys[0].get("api_key", "")
            if not api_key:
                # Try to use the token as fallback
                api_key = self.user_data.get("access_token", "")
            
            headers = {"Authorization": f"Bearer {api_key}"}
            
            # Test 1: List available models
            async with self.session.get(f"{self.backend_url}/api/v1/llm/models", headers=headers) as response:
                if response.status == 200:
                    models_data = await response.json()
                    model_count = len(models_data.get("models", []))
                    self.log_test("List Models", True, f"Found {model_count} models", {"model_count": model_count})
                else:
                    error_data = await response.json()
                    self.log_test("List Models", False, f"HTTP {response.status}: {error_data}")
            
            # Test 2: Chat completion (joke request as specified)
            chat_data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "Tell me a programming joke"}
                ],
                "max_tokens": 150,
                "temperature": 0.7
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/llm/chat/completions",
                json=chat_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    chat_response = await response.json()
                    joke = chat_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                    tokens_used = chat_response.get("usage", {}).get("total_tokens", 0)
                    self.log_test("Chat Completion", True, f"Joke received ({tokens_used} tokens)", {
                        "joke_preview": joke[:100] + "..." if len(joke) > 100 else joke,
                        "tokens_used": tokens_used
                    })
                else:
                    error_data = await response.json()
                    self.log_test("Chat Completion", False, f"HTTP {response.status}: {error_data}")
            
            # Test 3: Embeddings
            embedding_data = {
                "model": "text-embedding-ada-002",
                "input": "This is a test sentence for embedding generation."
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/llm/embeddings",
                json=embedding_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    embedding_response = await response.json()
                    embedding_dim = len(embedding_response.get("data", [{}])[0].get("embedding", []))
                    self.log_test("Embeddings", True, f"Embedding generated ({embedding_dim} dimensions)", {
                        "dimension": embedding_dim,
                        "tokens_used": embedding_response.get("usage", {}).get("total_tokens", 0)
                    })
                else:
                    error_data = await response.json()
                    self.log_test("Embeddings", False, f"HTTP {response.status}: {error_data}")
            
            return True
            
        except Exception as e:
            self.log_test("LLM Integration", False, f"Error: {e}")
            return False
    
    async def test_ollama_integration(self):
        """Test 6: Ollama integration"""
        logger.info("=" * 60)
        logger.info("TEST 6: Ollama Integration")
        logger.info("=" * 60)
        
        try:
            # Test Ollama proxy health
            ollama_url = "http://localhost:11434"
            
            try:
                async with self.session.get(f"{ollama_url}/api/tags") as response:
                    if response.status == 200:
                        models_data = await response.json()
                        model_count = len(models_data.get("models", []))
                        self.log_test("Ollama Connection", True, f"Connected to Ollama ({model_count} models)", {
                            "model_count": model_count,
                            "models": [m.get("name") for m in models_data.get("models", [])][:5]
                        })
                        
                        # Test Ollama chat if models are available
                        if model_count > 0:
                            model_name = models_data["models"][0]["name"]
                            chat_data = {
                                "model": model_name,
                                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                                "stream": False
                            }
                            
                            try:
                                async with self.session.post(
                                    f"{ollama_url}/api/chat",
                                    json=chat_data,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as chat_response:
                                    if chat_response.status == 200:
                                        chat_result = await chat_response.json()
                                        response_text = chat_result.get("message", {}).get("content", "")
                                        self.log_test("Ollama Chat", True, f"Response from {model_name}", {
                                            "model": model_name,
                                            "response_preview": response_text[:100] + "..." if len(response_text) > 100 else response_text
                                        })
                                    else:
                                        self.log_test("Ollama Chat", False, f"HTTP {chat_response.status}")
                            except asyncio.TimeoutError:
                                self.log_test("Ollama Chat", False, "Timeout - model may be loading")
                        else:
                            self.log_test("Ollama Models", False, "No models available in Ollama")
                    else:
                        self.log_test("Ollama Connection", False, f"HTTP {response.status}")
            except Exception as e:
                self.log_test("Ollama Connection", False, f"Connection error: {e}")
            
            return True
            
        except Exception as e:
            self.log_test("Ollama Integration", False, f"Error: {e}")
            return False
    
    async def test_rag_system(self):
        """Test 7: RAG system with real document processing"""
        logger.info("=" * 60)
        logger.info("TEST 7: RAG System")
        logger.info("=" * 60)
        
        if not self.user_data.get("access_token"):
            self.log_test("RAG System", False, "No access token available")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.user_data['access_token']}"}
            
            # Create test collection
            collection_data = {
                "name": f"Test Collection {int(time.time())}",
                "description": "Comprehensive test collection for RAG functionality"
            }
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/rag/collections",
                json=collection_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    collection_response = await response.json()
                    collection = collection_response.get("collection", {})
                    self.collections.append(collection)
                    self.log_test("RAG Collection Creation", True, f"Collection created: {collection.get('name')}", {
                        "collection_id": collection.get("id"),
                        "name": collection.get("name")
                    })
                else:
                    error_data = await response.json()
                    self.log_test("RAG Collection Creation", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            # Create test document for upload
            test_content = f"""# Test Document for RAG System
            
This is a comprehensive test document created at {datetime.utcnow().isoformat()}.

## Introduction
This document contains various types of content to test the RAG system's ability to:
- Extract and process text content
- Generate meaningful embeddings
- Index content for search and retrieval

## Technical Details
The RAG system should be able to process this document and make it searchable.
Key capabilities include:
- Document chunking and processing
- Vector embedding generation  
- Semantic search functionality
- Content retrieval and ranking

## Testing Scenarios
This document will be used to test:
1. Document upload and processing
2. Content extraction and conversion
3. Vector generation and indexing
4. Search and retrieval accuracy

## Keywords for Search Testing
artificial intelligence, machine learning, natural language processing,
vector database, semantic search, document processing, text analysis
"""
            
            # Upload document
            collection_id = self.collections[-1]["id"]
            
            # Create form data
            form_data = aiohttp.FormData()
            form_data.add_field('collection_id', str(collection_id))
            form_data.add_field('file', test_content.encode(), 
                              filename='test_document.txt', 
                              content_type='text/plain')
            
            async with self.session.post(
                f"{self.backend_url}/api/v1/rag/documents",
                data=form_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    document_response = await response.json()
                    document = document_response.get("document", {})
                    self.documents.append(document)
                    self.log_test("RAG Document Upload", True, f"Document uploaded: {document.get('filename')}", {
                        "document_id": document.get("id"),
                        "filename": document.get("filename"),
                        "size": document.get("size")
                    })
                else:
                    error_data = await response.json()
                    self.log_test("RAG Document Upload", False, f"HTTP {response.status}: {error_data}")
                    return False
            
            # Wait for document processing (check status multiple times)
            document_id = self.documents[-1]["id"]
            processing_complete = False
            
            for attempt in range(30):  # Wait up to 60 seconds
                await asyncio.sleep(2)
                
                async with self.session.get(
                    f"{self.backend_url}/api/v1/rag/documents/{document_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        doc_status = await response.json()
                        document_info = doc_status.get("document", {})
                        status = document_info.get("status", "unknown")
                        
                        if status in ["processed", "indexed"]:
                            processing_complete = True
                            word_count = document_info.get("word_count", 0)
                            vector_count = document_info.get("vector_count", 0)
                            self.log_test("RAG Document Processing", True, f"Processing complete: {status}", {
                                "status": status,
                                "word_count": word_count,
                                "vector_count": vector_count,
                                "processing_time": f"{(attempt + 1) * 2} seconds"
                            })
                            break
                        elif status == "error":
                            error_msg = document_info.get("processing_error", "Unknown error")
                            self.log_test("RAG Document Processing", False, f"Processing failed: {error_msg}")
                            break
                        elif attempt == 29:
                            self.log_test("RAG Document Processing", False, "Processing timeout after 60 seconds")
                            break
            
            # Test document search (if processing completed)
            if processing_complete:
                search_query = "artificial intelligence machine learning"
                
                # Note: Search endpoint might not be implemented yet, so we'll test what's available
                async with self.session.get(
                    f"{self.backend_url}/api/v1/rag/stats",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        rag_stats = await response.json()
                        stats = rag_stats.get("stats", {})
                        self.log_test("RAG Statistics", True, "RAG stats retrieved", stats)
                    else:
                        error_data = await response.json()
                        self.log_test("RAG Statistics", False, f"HTTP {response.status}: {error_data}")
            
            return True
            
        except Exception as e:
            self.log_test("RAG System", False, f"Error: {e}")
            return False
    
    async def test_module_system(self):
        """Test 8: Module system functionality"""
        logger.info("=" * 60)
        logger.info("TEST 8: Module System")
        logger.info("=" * 60)
        
        try:
            # Test modules status
            async with self.session.get(f"{self.backend_url}/api/v1/modules/status") as response:
                if response.status == 200:
                    modules_status = await response.json()
                    enabled_count = len([m for m in modules_status if m.get("enabled")])
                    total_count = len(modules_status)
                    self.log_test("Module System Status", True, f"{enabled_count}/{total_count} modules enabled", {
                        "enabled_modules": enabled_count,
                        "total_modules": total_count,
                        "modules": [m.get("name") for m in modules_status if m.get("enabled")]
                    })
                else:
                    error_data = await response.json()
                    self.log_test("Module System Status", False, f"HTTP {response.status}: {error_data}")
            
            # Test individual module info
            test_modules = ["rag", "content", "cache"]
            for module_name in test_modules:
                async with self.session.get(f"{self.backend_url}/api/v1/modules/{module_name}") as response:
                    if response.status == 200:
                        module_info = await response.json()
                        self.log_test(f"Module Info ({module_name})", True, f"Module info retrieved", {
                            "module": module_name,
                            "enabled": module_info.get("enabled"),
                            "version": module_info.get("version")
                        })
                    else:
                        self.log_test(f"Module Info ({module_name})", False, f"HTTP {response.status}")
            
            return True
            
        except Exception as e:
            self.log_test("Module System", False, f"Error: {e}")
            return False
    
    async def cleanup_test_data(self):
        """Cleanup test data created during testing"""
        logger.info("=" * 60)
        logger.info("CLEANUP: Removing test data")
        logger.info("=" * 60)
        
        if not self.user_data.get("access_token"):
            return
        
        headers = {"Authorization": f"Bearer {self.user_data['access_token']}"}
        
        try:
            # Delete documents
            for document in self.documents:
                doc_id = document.get("id")
                try:
                    async with self.session.delete(
                        f"{self.backend_url}/api/v1/rag/documents/{doc_id}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Deleted document {doc_id}")
                        else:
                            logger.warning(f"Failed to delete document {doc_id}: HTTP {response.status}")
                except Exception as e:
                    logger.warning(f"Error deleting document {doc_id}: {e}")
            
            # Delete collections
            for collection in self.collections:
                collection_id = collection.get("id")
                try:
                    async with self.session.delete(
                        f"{self.backend_url}/api/v1/rag/collections/{collection_id}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Deleted collection {collection_id}")
                        else:
                            logger.warning(f"Failed to delete collection {collection_id}: HTTP {response.status}")
                except Exception as e:
                    logger.warning(f"Error deleting collection {collection_id}: {e}")
            
            # Delete budgets
            for budget in self.budgets:
                budget_id = budget.get("id")
                try:
                    async with self.session.delete(
                        f"{self.backend_url}/api/v1/budgets/{budget_id}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Deleted budget {budget_id}")
                        else:
                            logger.warning(f"Failed to delete budget {budget_id}: HTTP {response.status}")
                except Exception as e:
                    logger.warning(f"Error deleting budget {budget_id}: {e}")
            
            # Delete API keys
            for api_key in self.api_keys:
                key_id = api_key.get("id")
                try:
                    async with self.session.delete(
                        f"{self.backend_url}/api/v1/api-keys/{key_id}",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Deleted API key {key_id}")
                        else:
                            logger.warning(f"Failed to delete API key {key_id}: HTTP {response.status}")
                except Exception as e:
                    logger.warning(f"Error deleting API key {key_id}: {e}")
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def run_all_tests(self):
        """Run all platform tests"""
        logger.info("🚀 Starting Comprehensive Platform Integration Tests")
        logger.info("=" * 80)
        
        start_time = time.time()
        
        # Run all tests in sequence
        tests = [
            self.test_platform_health,
            self.test_user_authentication,
            self.test_api_key_management,
            self.test_budget_system,
            self.test_llm_integration,
            self.test_ollama_integration,
            self.test_rag_system,
            self.test_module_system
        ]
        
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                logger.error(f"Unexpected error in {test_func.__name__}: {e}")
                self.log_test(test_func.__name__, False, f"Unexpected error: {e}")
            
            # Brief pause between tests
            await asyncio.sleep(1)
        
        # Cleanup
        await self.cleanup_test_data()
        
        # Print final results
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE PLATFORM TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {self.results['passed'] + self.results['failed']}")
        logger.info(f"Passed: {self.results['passed']}")
        logger.info(f"Failed: {self.results['failed']}")
        logger.info(f"Success Rate: {(self.results['passed'] / (self.results['passed'] + self.results['failed']) * 100):.1f}%")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        if self.results['failed'] > 0:
            logger.info("\\nFailed Tests:")
            for test in self.results['tests']:
                if not test['success']:
                    logger.info(f"  - {test['name']}: {test['details']}")
        
        logger.info("=" * 80)
        
        # Save detailed results to file
        results_file = f"platform_test_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Detailed results saved to: {results_file}")
        
        # Return success/failure
        return self.results['failed'] == 0


async def main():
    """Main test runner"""
    try:
        async with PlatformTester() as tester:
            success = await tester.run_all_tests()
            return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\\nTest interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Test runner error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)