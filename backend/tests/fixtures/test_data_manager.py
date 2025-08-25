"""
Comprehensive test data management for all components.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import tempfile
from pathlib import Path
import secrets


class TestDataManager:
    """Comprehensive test data management for all components"""
    
    def __init__(self, db_session: AsyncSession, qdrant_client: QdrantClient):
        self.db_session = db_session
        self.qdrant_client = qdrant_client
        self.created_resources = {
            "users": [],
            "api_keys": [],
            "budgets": [],
            "chatbots": [],
            "rag_collections": [],
            "rag_documents": [],
            "qdrant_collections": [],
            "temp_files": []
        }
    
    async def create_test_user(self, 
                              email: Optional[str] = None,
                              username: Optional[str] = None,
                              password: str = "testpass123") -> Dict[str, Any]:
        """Create test user account"""
        if not email:
            email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        if not username:
            username = f"testuser_{uuid.uuid4().hex[:8]}"
        
        from app.models.user import User
        from app.core.security import get_password_hash
        
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_verified=True
        )
        
        self.db_session.add(user)
        await self.db_session.commit()
        await self.db_session.refresh(user)
        
        user_data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "password": password  # Store for testing
        }
        
        self.created_resources["users"].append(user_data)
        return user_data
    
    async def create_test_api_key(self, 
                                 user_id: str,
                                 name: Optional[str] = None,
                                 scopes: List[str] = None,
                                 budget_limit: float = 100.0) -> Dict[str, Any]:
        """Create test API key"""
        if not name:
            name = f"Test API Key {uuid.uuid4().hex[:8]}"
        if not scopes:
            scopes = ["llm.chat", "llm.embeddings"]
        
        from app.models.api_key import APIKey
        from app.models.budget import Budget
        
        # Generate API key
        key = f"sk-test-{secrets.token_urlsafe(32)}"
        
        # Create budget
        budget = Budget(
            id=str(uuid.uuid4()),
            user_id=user_id,
            limit_amount=budget_limit,
            period="monthly",
            current_usage=0.0,
            is_active=True
        )
        
        self.db_session.add(budget)
        await self.db_session.commit()
        await self.db_session.refresh(budget)
        
        # Create API key
        api_key = APIKey(
            id=str(uuid.uuid4()),
            key_hash=key,  # In real code, this would be hashed
            name=name,
            user_id=user_id,
            scopes=scopes,
            budget_id=budget.id,
            is_active=True
        )
        
        self.db_session.add(api_key)
        await self.db_session.commit()
        await self.db_session.refresh(api_key)
        
        api_key_data = {
            "id": api_key.id,
            "key": key,
            "name": name,
            "scopes": scopes,
            "budget_id": budget.id
        }
        
        self.created_resources["api_keys"].append(api_key_data)
        self.created_resources["budgets"].append({"id": budget.id})
        return api_key_data
    
    async def create_qdrant_collection(self,
                                      collection_name: Optional[str] = None,
                                      vector_size: int = 1536) -> str:
        """Create Qdrant collection for testing"""
        if not collection_name:
            collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
        
        self.qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        
        self.created_resources["qdrant_collections"].append(collection_name)
        return collection_name
    
    async def create_test_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create test documents in Qdrant collection"""
        points = []
        created_docs = []
        
        for i, doc in enumerate(documents):
            doc_id = str(uuid.uuid4())
            point = PointStruct(
                id=doc_id,
                vector=doc.get("vector", [0.1] * 1536),  # Mock embedding
                payload={
                    "text": doc["text"],
                    "document_id": doc.get("document_id", f"doc_{i}"),
                    "filename": doc.get("filename", f"test_doc_{i}.txt"),
                    "chunk_index": doc.get("chunk_index", i),
                    "metadata": doc.get("metadata", {})
                }
            )
            points.append(point)
            created_docs.append({
                "id": doc_id,
                "text": doc["text"],
                "filename": doc.get("filename", f"test_doc_{i}.txt")
            })
        
        self.qdrant_client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        return created_docs
    
    async def create_test_rag_collection(self, 
                                       user_id: str,
                                       name: Optional[str] = None,
                                       documents: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create complete RAG collection with documents"""
        if not name:
            name = f"Test Collection {uuid.uuid4().hex[:8]}"
        
        # Create Qdrant collection
        qdrant_collection_name = await self.create_qdrant_collection()
        
        # Create database record
        from app.models.rag_collection import RagCollection
        
        rag_collection = RagCollection(
            id=str(uuid.uuid4()),
            name=name,
            description="Test collection for automated testing",
            owner_id=user_id,
            qdrant_collection_name=qdrant_collection_name,
            is_active=True
        )
        
        self.db_session.add(rag_collection)
        await self.db_session.commit()
        await self.db_session.refresh(rag_collection)
        
        # Add test documents if provided
        if documents:
            await self.create_test_documents(qdrant_collection_name, documents)
            
            # Also create document records in database
            from app.models.rag_document import RagDocument
            for i, doc in enumerate(documents):
                doc_record = RagDocument(
                    id=str(uuid.uuid4()),
                    filename=doc.get("filename", f"test_doc_{i}.txt"),
                    original_name=doc.get("filename", f"test_doc_{i}.txt"),
                    file_size=len(doc["text"]),
                    collection_id=rag_collection.id,
                    content_preview=doc["text"][:200] + "..." if len(doc["text"]) > 200 else doc["text"],
                    processing_status="completed",
                    chunk_count=1,
                    vector_count=1
                )
                self.db_session.add(doc_record)
                self.created_resources["rag_documents"].append({"id": doc_record.id})
            
            await self.db_session.commit()
        
        collection_data = {
            "id": rag_collection.id,
            "name": name,
            "qdrant_collection_name": qdrant_collection_name,
            "owner_id": user_id
        }
        
        self.created_resources["rag_collections"].append(collection_data)
        return collection_data
    
    async def create_test_chatbot(self,
                                user_id: str,
                                name: Optional[str] = None,
                                use_rag: bool = False,
                                rag_collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Create test chatbot"""
        if not name:
            name = f"Test Chatbot {uuid.uuid4().hex[:8]}"
        
        from app.models.chatbot import ChatbotInstance
        
        chatbot_config = {
            "name": name,
            "chatbot_type": "assistant",
            "model": "test-model",
            "system_prompt": "You are a helpful test assistant.",
            "use_rag": use_rag,
            "rag_collection": rag_collection_name if use_rag else None,
            "rag_top_k": 3,
            "temperature": 0.7,
            "max_tokens": 1000,
            "memory_length": 10,
            "fallback_responses": ["I'm not sure about that."]
        }
        
        chatbot = ChatbotInstance(
            id=str(uuid.uuid4()),
            name=name,
            description=f"Test chatbot: {name}",
            config=chatbot_config,
            created_by=user_id,
            is_active=True
        )
        
        self.db_session.add(chatbot)
        await self.db_session.commit()
        await self.db_session.refresh(chatbot)
        
        chatbot_data = {
            "id": chatbot.id,
            "name": name,
            "config": chatbot_config,
            "use_rag": use_rag,
            "rag_collection": rag_collection_name
        }
        
        self.created_resources["chatbots"].append(chatbot_data)
        return chatbot_data
    
    def create_temp_file(self, content: str, filename: str) -> Path:
        """Create temporary file for testing"""
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / f"test_{uuid.uuid4().hex[:8]}_{filename}"
        temp_file.write_text(content)
        
        self.created_resources["temp_files"].append(temp_file)
        return temp_file
    
    async def create_sample_rag_documents(self) -> List[Dict[str, Any]]:
        """Create sample documents for RAG testing"""
        return [
            {
                "text": "Enclava Platform is a comprehensive AI platform that provides secure LLM services. It features chatbot creation, RAG integration, and OpenAI-compatible API endpoints.",
                "filename": "platform_overview.txt",
                "document_id": "doc1",
                "chunk_index": 0,
                "metadata": {"category": "overview"}
            },
            {
                "text": "To create a chatbot in Enclava, navigate to the Chatbot section and click 'Create New Chatbot'. Configure the model, temperature, and system prompt according to your needs.",
                "filename": "chatbot_guide.txt", 
                "document_id": "doc2",
                "chunk_index": 0,
                "metadata": {"category": "tutorial"}
            },
            {
                "text": "RAG (Retrieval Augmented Generation) allows chatbots to use specific documents as knowledge sources. Upload documents to a collection, then link the collection to your chatbot for enhanced responses.",
                "filename": "rag_documentation.txt",
                "document_id": "doc3", 
                "chunk_index": 0,
                "metadata": {"category": "feature"}
            }
        ]
    
    async def cleanup_all(self):
        """Clean up all created test resources"""
        # Clean up temporary files
        for temp_file in self.created_resources["temp_files"]:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete temp file {temp_file}: {e}")
        
        # Clean up Qdrant collections
        for collection_name in self.created_resources["qdrant_collections"]:
            try:
                self.qdrant_client.delete_collection(collection_name)
            except Exception as e:
                print(f"Warning: Failed to delete Qdrant collection {collection_name}: {e}")
        
        # Clean up database records (order matters due to foreign keys)
        try:
            # Delete RAG documents
            if self.created_resources["rag_documents"]:
                from app.models.rag_document import RagDocument
                for doc in self.created_resources["rag_documents"]:
                    await self.db_session.execute(
                        delete(RagDocument).where(RagDocument.id == doc["id"])
                    )
            
            # Delete chatbots
            if self.created_resources["chatbots"]:
                from app.models.chatbot import ChatbotInstance
                for chatbot in self.created_resources["chatbots"]:
                    await self.db_session.execute(
                        delete(ChatbotInstance).where(ChatbotInstance.id == chatbot["id"])
                    )
            
            # Delete RAG collections
            if self.created_resources["rag_collections"]:
                from app.models.rag_collection import RagCollection
                for collection in self.created_resources["rag_collections"]:
                    await self.db_session.execute(
                        delete(RagCollection).where(RagCollection.id == collection["id"])
                    )
            
            # Delete API keys
            if self.created_resources["api_keys"]:
                from app.models.api_key import APIKey
                for api_key in self.created_resources["api_keys"]:
                    await self.db_session.execute(
                        delete(APIKey).where(APIKey.id == api_key["id"])
                    )
            
            # Delete budgets
            if self.created_resources["budgets"]:
                from app.models.budget import Budget
                for budget in self.created_resources["budgets"]:
                    await self.db_session.execute(
                        delete(Budget).where(Budget.id == budget["id"])
                    )
            
            # Delete users
            if self.created_resources["users"]:
                from app.models.user import User
                for user in self.created_resources["users"]:
                    await self.db_session.execute(
                        delete(User).where(User.id == user["id"])
                    )
            
            await self.db_session.commit()
            
        except Exception as e:
            print(f"Warning: Failed to cleanup database resources: {e}")
            await self.db_session.rollback()
        
        # Clear tracking
        for resource_type in self.created_resources:
            self.created_resources[resource_type].clear()