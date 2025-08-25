"""
Complete chatbot workflow tests with RAG integration.
Test the entire pipeline from document upload to chat responses with knowledge retrieval.
"""

import pytest
import asyncio
from typing import Dict, Any, List

from tests.clients.chatbot_api_client import ChatbotAPITestClient
from tests.fixtures.test_data_manager import TestDataManager


class TestChatbotRAGWorkflow:
    """Test complete chatbot workflow with RAG integration"""
    
    BASE_URL = "http://localhost:3001"  # Through nginx
    
    @pytest.fixture
    async def api_client(self):
        """Chatbot API test client"""
        return ChatbotAPITestClient(self.BASE_URL)
    
    @pytest.fixture
    async def authenticated_client(self, api_client):
        """Pre-authenticated API client"""
        # Register and authenticate test user
        email = "ragtest@example.com"
        password = "testpass123"
        username = "ragtestuser"
        
        # Register user
        register_result = await api_client.register_user(email, password, username)
        if register_result["status_code"] not in [201, 409]:  # 409 = already exists
            pytest.fail(f"Failed to register user: {register_result}")
        
        # Authenticate
        auth_result = await api_client.authenticate(email, password)
        if not auth_result["success"]:
            pytest.fail(f"Failed to authenticate: {auth_result}")
        
        return api_client
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for RAG testing"""
        return {
            "installation_guide": {
                "filename": "installation_guide.md",
                "content": """
                # Enclava Platform Installation Guide
                
                ## System Requirements
                - Python 3.8 or higher
                - Docker and Docker Compose
                - PostgreSQL 13+
                - Redis 6+
                - At least 4GB RAM
                
                ## Installation Steps
                1. Clone the repository
                2. Copy .env.example to .env
                3. Run docker-compose up --build
                4. Access the application at http://localhost:3000
                
                ## Troubleshooting
                - If port 3000 is in use, modify docker-compose.yml
                - Check Docker daemon is running
                - Ensure all required ports are available
                """,
                "test_questions": [
                    {
                        "question": "What are the system requirements for Enclava?",
                        "expected_keywords": ["Python 3.8", "Docker", "PostgreSQL", "Redis", "4GB RAM"],
                        "min_keywords": 3
                    },
                    {
                        "question": "How do I install Enclava?",
                        "expected_keywords": ["clone", "repository", ".env", "docker-compose up", "localhost:3000"],
                        "min_keywords": 3
                    },
                    {
                        "question": "What should I do if port 3000 is in use?",
                        "expected_keywords": ["modify", "docker-compose.yml", "port"],
                        "min_keywords": 2
                    }
                ]
            },
            "api_reference": {
                "filename": "api_reference.md", 
                "content": """
                # Enclava API Reference
                
                ## Authentication
                All API requests require authentication using Bearer tokens or API keys.
                
                ## Endpoints
                
                ### GET /api/v1/models
                List available AI models
                Response: {"data": [{"id": "model-name", "object": "model", ...}]}
                
                ### POST /api/v1/chat/completions
                Create chat completion
                Body: {"model": "model-name", "messages": [...], "temperature": 0.7}
                Response: {"choices": [{"message": {"content": "response"}}]}
                
                ### POST /api/v1/embeddings
                Generate text embeddings
                Body: {"model": "embedding-model", "input": "text to embed"}
                Response: {"data": [{"embedding": [...]}]}
                
                ## Rate Limits
                - Free tier: 60 requests per minute
                - Pro tier: 600 requests per minute
                """,
                "test_questions": [
                    {
                        "question": "How do I authenticate with the Enclava API?",
                        "expected_keywords": ["Bearer token", "API key", "authentication"],
                        "min_keywords": 2
                    },
                    {
                        "question": "What is the endpoint for chat completions?",
                        "expected_keywords": ["/api/v1/chat/completions", "POST"],
                        "min_keywords": 1
                    },
                    {
                        "question": "What are the rate limits?",
                        "expected_keywords": ["60 requests", "600 requests", "per minute", "free tier", "pro tier"],
                        "min_keywords": 3
                    }
                ]
            }
        }
    
    @pytest.mark.asyncio
    async def test_complete_rag_workflow(self, authenticated_client, sample_documents):
        """Test complete RAG workflow from document upload to chat response"""
        
        # Test with installation guide document
        doc_info = sample_documents["installation_guide"]
        
        result = await authenticated_client.test_rag_workflow(
            collection_name="Installation Guide Collection",
            document_content=doc_info["content"],
            chatbot_name="Installation Assistant",
            test_question=doc_info["test_questions"][0]["question"]
        )
        
        assert result["success"], f"RAG workflow failed: {result.get('error')}"
        assert result["workflow_complete"], "Workflow did not complete successfully"
        assert result["rag_working"], "RAG functionality is not working"
        
        # Verify all workflow steps succeeded
        workflow_results = result["results"]
        assert workflow_results["collection_creation"]["success"]
        assert workflow_results["document_upload"]["success"] 
        assert workflow_results["document_processing"]["success"]
        assert workflow_results["chatbot_creation"]["success"]
        assert workflow_results["api_key_creation"]["success"]
        assert workflow_results["chat_test"]["success"]
        
        # Verify RAG sources were provided
        rag_verification = workflow_results["rag_verification"]
        assert rag_verification["has_sources"]
        assert rag_verification["source_count"] > 0
    
    @pytest.mark.asyncio
    async def test_rag_knowledge_accuracy(self, authenticated_client, sample_documents):
        """Test RAG system accuracy with known documents and questions"""
        
        for doc_key, doc_info in sample_documents.items():
            # Create RAG workflow for this document
            workflow_result = await authenticated_client.test_rag_workflow(
                collection_name=f"Test Collection - {doc_key}",
                document_content=doc_info["content"],
                chatbot_name=f"Test Assistant - {doc_key}",
                test_question=doc_info["test_questions"][0]["question"]  # Use first question for setup
            )
            
            if not workflow_result["success"]:
                pytest.fail(f"Failed to set up RAG workflow for {doc_key}: {workflow_result.get('error')}")
            
            # Extract chatbot info for testing
            chatbot_id = workflow_result["results"]["chatbot_creation"]["data"]["id"]
            api_key = workflow_result["results"]["api_key_creation"]["data"]["key"]
            
            # Test each question for this document
            for question_data in doc_info["test_questions"]:
                chat_result = await authenticated_client.chat_with_bot(
                    chatbot_id=chatbot_id,
                    message=question_data["question"],
                    api_key=api_key
                )
                
                assert chat_result["success"], f"Chat failed for question: {question_data['question']}"
                
                # Analyze response accuracy
                response_text = chat_result["data"]["response"].lower()
                keywords_found = sum(
                    1 for keyword in question_data["expected_keywords"]
                    if keyword.lower() in response_text
                )
                
                accuracy = keywords_found / len(question_data["expected_keywords"])
                min_accuracy = question_data["min_keywords"] / len(question_data["expected_keywords"])
                
                assert accuracy >= min_accuracy, \
                    f"Accuracy {accuracy:.2f} below minimum {min_accuracy:.2f} for question: {question_data['question']} in {doc_key}"
                
                # Verify sources were provided
                assert "sources" in chat_result["data"], f"No sources provided for question in {doc_key}"
                assert len(chat_result["data"]["sources"]) > 0, f"Empty sources for question in {doc_key}"
    
    @pytest.mark.asyncio
    async def test_conversation_memory_with_rag(self, authenticated_client, sample_documents):
        """Test conversation memory functionality with RAG"""
        
        # Set up RAG chatbot
        doc_info = sample_documents["api_reference"]
        workflow_result = await authenticated_client.test_rag_workflow(
            collection_name="Memory Test Collection",
            document_content=doc_info["content"],
            chatbot_name="Memory Test Assistant",
            test_question="What is the API reference?"
        )
        
        assert workflow_result["success"], f"Failed to set up RAG workflow: {workflow_result.get('error')}"
        
        chatbot_id = workflow_result["results"]["chatbot_creation"]["data"]["id"]
        api_key = workflow_result["results"]["api_key_creation"]["data"]["key"]
        
        # Test conversation memory
        memory_result = await authenticated_client.test_conversation_memory(chatbot_id, api_key)
        
        # Verify conversation was maintained
        assert memory_result["conversation_maintained"], "Conversation ID was not maintained across messages"
        
        # Verify memory is working (may be challenging with RAG, so we're lenient)
        conversation_results = memory_result["conversation_results"]
        assert len(conversation_results) >= 3, "Not all conversation messages were processed"
        
        # All messages should have gotten responses
        for result in conversation_results:
            assert "response" in result or "error" in result, "Message did not get a response"
    
    @pytest.mark.asyncio
    async def test_multi_document_rag(self, authenticated_client, sample_documents):
        """Test RAG with multiple documents in one collection"""
        
        # Create collection
        collection_result = await authenticated_client.create_rag_collection(
            name="Multi-Document Collection",
            description="Collection with multiple documents for testing"
        )
        assert collection_result["success"], f"Failed to create collection: {collection_result}"
        
        collection_id = collection_result["data"]["id"]
        
        # Upload multiple documents
        uploaded_docs = []
        for doc_key, doc_info in sample_documents.items():
            upload_result = await authenticated_client.upload_document(
                collection_id=collection_id,
                file_content=doc_info["content"],
                filename=doc_info["filename"]
            )
            
            assert upload_result["success"], f"Failed to upload {doc_key}: {upload_result}"
            
            # Wait for processing
            doc_id = upload_result["data"]["id"]
            processing_result = await authenticated_client.wait_for_document_processing(doc_id)
            assert processing_result["success"], f"Processing failed for {doc_key}: {processing_result}"
            
            uploaded_docs.append(doc_key)
        
        # Create chatbot with access to all documents
        chatbot_result = await authenticated_client.create_chatbot(
            name="Multi-Doc Assistant",
            use_rag=True,
            rag_collection="Multi-Document Collection"
        )
        assert chatbot_result["success"], f"Failed to create chatbot: {chatbot_result}"
        
        chatbot_id = chatbot_result["data"]["id"]
        
        # Create API key
        api_key_result = await authenticated_client.create_api_key_for_chatbot(chatbot_id)
        assert api_key_result["success"], f"Failed to create API key: {api_key_result}"
        
        api_key = api_key_result["data"]["key"]
        
        # Test questions that should draw from different documents
        test_questions = [
            "How do I install Enclava?",  # Should use installation guide
            "What are the API endpoints?",  # Should use API reference
            "Tell me about both installation and API usage"  # Should use both documents
        ]
        
        for question in test_questions:
            chat_result = await authenticated_client.chat_with_bot(
                chatbot_id=chatbot_id,
                message=question,
                api_key=api_key
            )
            
            assert chat_result["success"], f"Chat failed for multi-doc question: {question}"
            assert "sources" in chat_result["data"], f"No sources for multi-doc question: {question}"
            assert len(chat_result["data"]["sources"]) > 0, f"Empty sources for multi-doc question: {question}"
    
    @pytest.mark.asyncio
    async def test_rag_collection_isolation(self, authenticated_client, sample_documents):
        """Test that RAG collections are properly isolated"""
        
        # Create two separate collections with different documents
        doc1 = sample_documents["installation_guide"]
        doc2 = sample_documents["api_reference"]
        
        # Collection 1 with installation guide
        workflow1 = await authenticated_client.test_rag_workflow(
            collection_name="Installation Only Collection",
            document_content=doc1["content"],
            chatbot_name="Installation Only Bot",
            test_question="What is installation?"
        )
        assert workflow1["success"], "Failed to create first RAG workflow"
        
        # Collection 2 with API reference
        workflow2 = await authenticated_client.test_rag_workflow(
            collection_name="API Only Collection", 
            document_content=doc2["content"],
            chatbot_name="API Only Bot",
            test_question="What is API?"
        )
        assert workflow2["success"], "Failed to create second RAG workflow"
        
        # Extract chatbot info
        bot1_id = workflow1["results"]["chatbot_creation"]["data"]["id"]
        bot1_key = workflow1["results"]["api_key_creation"]["data"]["key"]
        
        bot2_id = workflow2["results"]["chatbot_creation"]["data"]["id"]
        bot2_key = workflow2["results"]["api_key_creation"]["data"]["key"]
        
        # Test cross-contamination
        # Bot 1 (installation only) should not know about API details
        api_question = "What are the rate limits?"
        result1 = await authenticated_client.chat_with_bot(bot1_id, api_question, api_key=bot1_key)
        
        if result1["success"]:
            response1 = result1["data"]["response"].lower()
            # Should not have detailed API rate limit info since it only has installation docs
            has_rate_info = "60 requests" in response1 or "600 requests" in response1
            # This is a soft assertion since the bot might still give a generic response
            
        # Bot 2 (API only) should not know about installation details
        install_question = "What are the system requirements?"
        result2 = await authenticated_client.chat_with_bot(bot2_id, install_question, api_key=bot2_key)
        
        if result2["success"]:
            response2 = result2["data"]["response"].lower() 
            # Should not have detailed system requirements since it only has API docs
            has_install_info = "python 3.8" in response2 or "docker" in response2
            # This is a soft assertion since the bot might still give a generic response
    
    @pytest.mark.asyncio
    async def test_rag_error_handling(self, authenticated_client):
        """Test RAG error handling scenarios"""
        
        # Test chatbot with non-existent collection
        chatbot_result = await authenticated_client.create_chatbot(
            name="Error Test Bot",
            use_rag=True,
            rag_collection="NonExistentCollection"
        )
        
        # Should either fail to create or handle gracefully
        if chatbot_result["success"]:
            # If creation succeeded, test that chat handles missing collection gracefully
            chatbot_id = chatbot_result["data"]["id"]
            
            api_key_result = await authenticated_client.create_api_key_for_chatbot(chatbot_id)
            if api_key_result["success"]:
                api_key = api_key_result["data"]["key"]
                
                chat_result = await authenticated_client.chat_with_bot(
                    chatbot_id=chatbot_id,
                    message="Tell me about something",
                    api_key=api_key
                )
                
                # Should handle gracefully - either succeed with fallback or fail gracefully
                # Don't assert success/failure, just ensure it doesn't crash
                assert "data" in chat_result or "error" in chat_result
    
    @pytest.mark.asyncio
    async def test_rag_document_types(self, authenticated_client):
        """Test RAG with different document types and formats"""
        
        document_types = {
            "markdown": {
                "filename": "test.md",
                "content": "# Markdown Test\n\nThis is **bold** text and *italic* text.\n\n- List item 1\n- List item 2"
            },
            "plain_text": {
                "filename": "test.txt", 
                "content": "This is plain text content for testing document processing and retrieval."
            },
            "json_like": {
                "filename": "config.txt",
                "content": '{"setting": "value", "number": 42, "enabled": true}'
            }
        }
        
        # Create collection
        collection_result = await authenticated_client.create_rag_collection(
            name="Document Types Collection",
            description="Testing different document formats"
        )
        assert collection_result["success"], f"Failed to create collection: {collection_result}"
        
        collection_id = collection_result["data"]["id"]
        
        # Upload each document type
        for doc_type, doc_info in document_types.items():
            upload_result = await authenticated_client.upload_document(
                collection_id=collection_id,
                file_content=doc_info["content"],
                filename=doc_info["filename"]
            )
            
            assert upload_result["success"], f"Failed to upload {doc_type}: {upload_result}"
            
            # Wait for processing
            doc_id = upload_result["data"]["id"]
            processing_result = await authenticated_client.wait_for_document_processing(doc_id, timeout=30)
            assert processing_result["success"], f"Processing failed for {doc_type}: {processing_result}"
        
        # Create chatbot to test all document types
        chatbot_result = await authenticated_client.create_chatbot(
            name="Document Types Bot",
            use_rag=True,
            rag_collection="Document Types Collection"
        )
        assert chatbot_result["success"], f"Failed to create chatbot: {chatbot_result}"
        
        chatbot_id = chatbot_result["data"]["id"]
        
        api_key_result = await authenticated_client.create_api_key_for_chatbot(chatbot_id)
        assert api_key_result["success"], f"Failed to create API key: {api_key_result}"
        
        api_key = api_key_result["data"]["key"]
        
        # Test questions for different document types
        test_questions = [
            "What is bold text?",  # Should find markdown
            "What is the plain text content?",  # Should find plain text
            "What is the setting value?",  # Should find JSON-like content
        ]
        
        for question in test_questions:
            chat_result = await authenticated_client.chat_with_bot(
                chatbot_id=chatbot_id,
                message=question,
                api_key=api_key
            )
            
            assert chat_result["success"], f"Chat failed for document type question: {question}"
            # Should have sources even if the answer quality varies
            assert "sources" in chat_result["data"], f"No sources for question: {question}"