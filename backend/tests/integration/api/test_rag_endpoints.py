#!/usr/bin/env python3
"""
RAG API Endpoints Tests - Phase 2 API Coverage  
Priority: app/api/v1/rag.py (40% → 80% coverage)

Tests comprehensive RAG API functionality:
- Collection CRUD operations
- Document upload/processing
- Search functionality  
- File format validation
- Permission checking
- Error handling and validation
"""

import pytest
import json
import io
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi import status, UploadFile
from app.main import app
from app.models.user import User
from app.models.rag_collection import RagCollection
from app.models.rag_document import RagDocument


class TestRAGEndpoints:
    """Comprehensive test suite for RAG API endpoints"""
    
    @pytest.fixture
    async def client(self):
        """Create test HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for test user"""
        return {"Authorization": "Bearer test_access_token"}
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            is_active=True,
            role="user"
        )
    
    @pytest.fixture
    def sample_collection(self):
        """Sample RAG collection"""
        return RagCollection(
            id=1,
            name="test_collection",
            description="Test collection for RAG",
            qdrant_collection_name="test_collection_qdrant",
            is_active=True,
            created_at=datetime.utcnow(),
            user_id=1
        )
    
    @pytest.fixture
    def sample_document(self):
        """Sample RAG document"""
        return RagDocument(
            id=1,
            collection_id=1,
            filename="test_document.pdf",
            original_filename="Test Document.pdf",
            file_type="pdf",
            size=1024,
            status="completed",
            word_count=250,
            character_count=1500,
            vector_count=5,
            metadata={"author": "Test Author"},
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_pdf_file(self):
        """Sample PDF file for upload testing"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        return ("test.pdf", io.BytesIO(pdf_content), "application/pdf")

    # === COLLECTION MANAGEMENT TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_collections_success(self, client, auth_headers, mock_user, sample_collection):
        """Test successful collection listing"""
        collections_data = [
            {
                "id": "1",
                "name": "test_collection", 
                "description": "Test collection",
                "document_count": 5,
                "size_bytes": 10240,
                "vector_count": 25,
                "status": "active",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z",
                "is_active": True
            }
        ]
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_all_collections.return_value = collections_data
                    
                    response = await client.get(
                        "/api/v1/rag/collections",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert len(data["collections"]) == 1
                    assert data["collections"][0]["name"] == "test_collection"
                    assert data["collections"][0]["document_count"] == 5
                    assert data["total"] == 1
    
    @pytest.mark.asyncio
    async def test_get_collections_with_pagination(self, client, auth_headers, mock_user):
        """Test collection listing with pagination"""
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_all_collections.return_value = []
                    
                    response = await client.get(
                        "/api/v1/rag/collections?skip=10&limit=5",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    
                    # Verify pagination parameters were passed
                    mock_service.get_all_collections.assert_called_once_with(skip=10, limit=5)
    
    @pytest.mark.asyncio
    async def test_get_collections_unauthorized(self, client):
        """Test collection listing without authentication"""
        response = await client.get("/api/v1/rag/collections")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_create_collection_success(self, client, auth_headers, mock_user):
        """Test successful collection creation"""
        collection_data = {
            "name": "new_test_collection",
            "description": "A new test collection for RAG"
        }
        
        created_collection = {
            "id": "2",
            "name": "new_test_collection",
            "description": "A new test collection for RAG",
            "qdrant_collection_name": "new_test_collection_qdrant",
            "created_at": "2024-01-01T10:00:00Z"
        }
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.create_collection.return_value = created_collection
                    
                    response = await client.post(
                        "/api/v1/rag/collections",
                        json=collection_data,
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert data["collection"]["name"] == "new_test_collection"
                    assert data["collection"]["description"] == "A new test collection for RAG"
                    
                    # Verify service was called correctly
                    mock_service.create_collection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_collection_duplicate_name(self, client, auth_headers, mock_user):
        """Test collection creation with duplicate name"""
        collection_data = {
            "name": "existing_collection",
            "description": "This collection already exists"
        }
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.create_collection.side_effect = Exception("Collection already exists")
                    
                    response = await client.post(
                        "/api/v1/rag/collections",
                        json=collection_data,
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "already exists" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_create_collection_invalid_data(self, client, auth_headers, mock_user):
        """Test collection creation with invalid data"""
        invalid_data_cases = [
            {},  # Missing required fields
            {"name": ""},  # Empty name
            {"name": "a"},  # Too short name
            {"name": "x" * 256},  # Too long name
            {"description": "x" * 2000}  # Too long description
        ]
        
        for invalid_data in invalid_data_cases:
            response = await client.post(
                "/api/v1/rag/collections",
                json=invalid_data,
                headers=auth_headers
            )
            
            assert response.status_code in [
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_400_BAD_REQUEST
            ]
    
    @pytest.mark.asyncio
    async def test_delete_collection_success(self, client, auth_headers, mock_user, sample_collection):
        """Test successful collection deletion"""
        collection_id = "1"
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.delete_collection.return_value = True
                    
                    response = await client.delete(
                        f"/api/v1/rag/collections/{collection_id}",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["success"] is True
                    assert "deleted" in data["message"].lower()
                    
                    # Verify service was called
                    mock_service.delete_collection.assert_called_once_with(collection_id)
    
    @pytest.mark.asyncio
    async def test_delete_collection_not_found(self, client, auth_headers, mock_user):
        """Test deletion of non-existent collection"""
        collection_id = "999"
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.delete_collection.side_effect = Exception("Collection not found")
                    
                    response = await client.delete(
                        f"/api/v1/rag/collections/{collection_id}",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "not found" in data["detail"]

    # === DOCUMENT MANAGEMENT TESTS ===
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, client, auth_headers, mock_user):
        """Test successful document upload"""
        collection_id = "1"
        
        # Create file-like object for upload
        file_content = b"This is a test PDF document content for RAG processing."
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        
        uploaded_document = {
            "id": "doc_123",
            "collection_id": collection_id,
            "filename": "test.pdf",
            "original_filename": "test.pdf",
            "file_type": "pdf",
            "size": len(file_content),
            "status": "processing",
            "created_at": "2024-01-01T10:00:00Z"
        }
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.upload_document.return_value = uploaded_document
                    
                    response = await client.post(
                        f"/api/v1/rag/collections/{collection_id}/documents",
                        files=files,
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert data["document"]["filename"] == "test.pdf"
                    assert data["document"]["file_type"] == "pdf"
                    assert data["document"]["status"] == "processing"
    
    @pytest.mark.asyncio
    async def test_upload_document_unsupported_format(self, client, auth_headers, mock_user):
        """Test document upload with unsupported format"""
        collection_id = "1"
        
        # Upload an unsupported file type
        file_content = b"This is a test executable file"
        files = {"file": ("malware.exe", io.BytesIO(file_content), "application/x-msdownload")}
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.upload_document.side_effect = Exception("Unsupported file type")
                    
                    response = await client.post(
                        f"/api/v1/rag/collections/{collection_id}/documents",
                        files=files,
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "unsupported" in data["detail"].lower() or "file type" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_upload_document_too_large(self, client, auth_headers, mock_user):
        """Test document upload that exceeds size limit"""
        collection_id = "1"
        
        # Create a large file (simulate > 10MB)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")}
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            response = await client.post(
                f"/api/v1/rag/collections/{collection_id}/documents",
                files=files,
                headers=auth_headers
            )
            
            # Should be rejected due to size limit (implementation dependent)
            assert response.status_code in [
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]
    
    @pytest.mark.asyncio
    async def test_upload_document_empty_file(self, client, auth_headers, mock_user):
        """Test upload of empty document"""
        collection_id = "1"
        
        # Empty file
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            response = await client.post(
                f"/api/v1/rag/collections/{collection_id}/documents",
                files=files,
                headers=auth_headers
            )
            
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]
    
    @pytest.mark.asyncio
    async def test_get_documents_in_collection(self, client, auth_headers, mock_user, sample_document):
        """Test listing documents in a collection"""
        collection_id = "1"
        
        documents_data = [
            {
                "id": "doc_1",
                "collection_id": collection_id,
                "filename": "test1.pdf",
                "original_filename": "Test Document 1.pdf",
                "file_type": "pdf",
                "size": 1024,
                "status": "completed",
                "word_count": 250,
                "vector_count": 5,
                "created_at": "2024-01-01T10:00:00Z"
            },
            {
                "id": "doc_2", 
                "collection_id": collection_id,
                "filename": "test2.docx",
                "original_filename": "Test Document 2.docx",
                "file_type": "docx",
                "size": 2048,
                "status": "processing",
                "word_count": 0,
                "vector_count": 0,
                "created_at": "2024-01-01T10:05:00Z"
            }
        ]
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_documents.return_value = documents_data
                    
                    response = await client.get(
                        f"/api/v1/rag/collections/{collection_id}/documents",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert len(data["documents"]) == 2
                    assert data["documents"][0]["filename"] == "test1.pdf"
                    assert data["documents"][0]["status"] == "completed"
                    assert data["documents"][1]["filename"] == "test2.docx"
                    assert data["documents"][1]["status"] == "processing"
    
    @pytest.mark.asyncio
    async def test_delete_document_success(self, client, auth_headers, mock_user):
        """Test successful document deletion"""
        document_id = "doc_123"
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.delete_document.return_value = True
                    
                    response = await client.delete(
                        f"/api/v1/rag/documents/{document_id}",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["success"] is True
                    assert "deleted" in data["message"].lower()
                    
                    # Verify service was called
                    mock_service.delete_document.assert_called_once_with(document_id)

    # === SEARCH FUNCTIONALITY TESTS ===
    
    @pytest.mark.asyncio
    async def test_search_documents_success(self, client, auth_headers, mock_user):
        """Test successful document search"""
        collection_id = "1"
        search_query = "machine learning algorithms"
        
        search_results = [
            {
                "document_id": "doc_1",
                "filename": "ml_guide.pdf",
                "content": "Machine learning algorithms are powerful tools...",
                "score": 0.95,
                "metadata": {"page": 1, "chapter": "Introduction"}
            },
            {
                "document_id": "doc_2",
                "filename": "ai_basics.docx", 
                "content": "Various algorithms exist in machine learning...",
                "score": 0.87,
                "metadata": {"page": 3, "section": "Algorithms"}
            }
        ]
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.search.return_value = search_results
                    
                    response = await client.post(
                        f"/api/v1/rag/collections/{collection_id}/search",
                        json={
                            "query": search_query,
                            "top_k": 5,
                            "min_score": 0.7
                        },
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert len(data["results"]) == 2
                    assert data["results"][0]["score"] >= data["results"][1]["score"]  # Sorted by score
                    assert "machine learning" in data["results"][0]["content"].lower()
                    assert data["query"] == search_query
    
    @pytest.mark.asyncio
    async def test_search_documents_empty_query(self, client, auth_headers, mock_user):
        """Test search with empty query"""
        collection_id = "1"
        
        response = await client.post(
            f"/api/v1/rag/collections/{collection_id}/search",
            json={
                "query": "",  # Empty query
                "top_k": 5
            },
            headers=auth_headers
        )
        
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
        data = response.json()
        assert "query" in str(data).lower()
    
    @pytest.mark.asyncio
    async def test_search_documents_no_results(self, client, auth_headers, mock_user):
        """Test search with no matching results"""
        collection_id = "1"
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.search.return_value = []  # No results
                    
                    response = await client.post(
                        f"/api/v1/rag/collections/{collection_id}/search",
                        json={
                            "query": "nonexistent topic xyz123",
                            "top_k": 5
                        },
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["success"] is True
                    assert len(data["results"]) == 0
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, client, auth_headers, mock_user):
        """Test search with metadata filters"""
        collection_id = "1"
        
        search_results = [
            {
                "document_id": "doc_1",
                "filename": "chapter1.pdf",
                "content": "Introduction to AI concepts...",
                "score": 0.92,
                "metadata": {"chapter": 1, "author": "John Doe"}
            }
        ]
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.search.return_value = search_results
                    
                    response = await client.post(
                        f"/api/v1/rag/collections/{collection_id}/search",
                        json={
                            "query": "AI introduction",
                            "top_k": 5,
                            "filters": {
                                "chapter": 1,
                                "author": "John Doe"
                            }
                        },
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["success"] is True
                    assert len(data["results"]) == 1
                    
                    # Verify filters were applied
                    mock_service.search.assert_called_once()
                    call_args = mock_service.search.call_args[1]
                    assert "filters" in call_args

    # === STATISTICS AND ANALYTICS TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_rag_stats_success(self, client, auth_headers, mock_user):
        """Test successful RAG statistics retrieval"""
        stats_data = {
            "collections": {
                "total": 5,
                "active": 4,
                "processing": 1
            },
            "documents": {
                "total": 150,
                "completed": 140,
                "processing": 8,
                "failed": 2
            },
            "storage": {
                "total_bytes": 104857600,  # 100MB
                "total_human": "100 MB"
            },
            "vectors": {
                "total": 15000,
                "avg_per_document": 100
            }
        }
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_stats.return_value = stats_data
                    
                    response = await client.get(
                        "/api/v1/rag/stats",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    
                    assert data["success"] is True
                    assert data["stats"]["collections"]["total"] == 5
                    assert data["stats"]["documents"]["total"] == 150
                    assert data["stats"]["storage"]["total_bytes"] == 104857600
                    assert data["stats"]["vectors"]["total"] == 15000

    # === PERMISSION AND SECURITY TESTS ===
    
    @pytest.mark.asyncio
    async def test_collection_access_control(self, client, auth_headers):
        """Test collection access control"""
        # Test access to other user's collection
        other_user_collection_id = "999"
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_user = User(id=1, username="testuser", email="test@example.com")
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_collection.side_effect = Exception("Access denied")
                    
                    response = await client.get(
                        f"/api/v1/rag/collections/{other_user_collection_id}",
                        headers=auth_headers
                    )
                    
                    assert response.status_code in [
                        status.HTTP_403_FORBIDDEN,
                        status.HTTP_404_NOT_FOUND,
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    ]
    
    @pytest.mark.asyncio
    async def test_file_upload_security(self, client, auth_headers, mock_user):
        """Test file upload security measures"""
        collection_id = "1"
        
        # Test malicious file types
        malicious_files = [
            ("script.js", b"alert('xss')", "application/javascript"),
            ("malware.exe", b"MZ executable", "application/x-msdownload"),
            ("shell.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
            ("config.conf", b"password=secret123", "text/plain")
        ]
        
        for filename, content, mime_type in malicious_files:
            files = {"file": (filename, io.BytesIO(content), mime_type)}
            
            with patch('app.api.v1.rag.get_current_user') as mock_get_user:
                mock_get_user.return_value = mock_user
                
                response = await client.post(
                    f"/api/v1/rag/collections/{collection_id}/documents", 
                    files=files,
                    headers=auth_headers
                )
                
                # Should reject dangerous file types
                assert response.status_code in [
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ]

    # === ERROR HANDLING AND EDGE CASES ===
    
    @pytest.mark.asyncio
    async def test_collection_not_found_error(self, client, auth_headers, mock_user):
        """Test handling of non-existent collection"""
        nonexistent_collection_id = "99999"
        
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_documents.side_effect = Exception("Collection not found")
                    
                    response = await client.get(
                        f"/api/v1/rag/collections/{nonexistent_collection_id}/documents",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "not found" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_qdrant_service_unavailable(self, client, auth_headers, mock_user):
        """Test handling of Qdrant service unavailability"""
        with patch('app.api.v1.rag.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.rag.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.rag.RAGService') as mock_rag_service:
                    mock_service = AsyncMock()
                    mock_rag_service.return_value = mock_service
                    mock_service.get_all_collections.side_effect = ConnectionError("Qdrant service unavailable")
                    
                    response = await client.get(
                        "/api/v1/rag/collections",
                        headers=auth_headers
                    )
                    
                    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    data = response.json()
                    assert "unavailable" in data["detail"].lower() or "connection" in data["detail"].lower()


"""
COVERAGE ANALYSIS FOR RAG API ENDPOINTS:

✅ Collection Management (6+ tests):
- Collection listing with pagination
- Collection creation with validation
- Collection deletion
- Duplicate name handling
- Unauthorized access handling
- Invalid data handling

✅ Document Management (6+ tests):
- Document upload with multiple formats
- File size and type validation
- Empty file handling
- Document listing in collections
- Document deletion
- Unsupported format rejection

✅ Search Functionality (4+ tests):
- Successful document search with ranking
- Empty query handling
- Search with no results
- Search with metadata filters

✅ Statistics (1+ test):
- RAG system statistics retrieval

✅ Security & Permissions (2+ tests):
- Collection access control
- File upload security measures

✅ Error Handling (2+ tests):
- Non-existent collection handling
- External service unavailability

ESTIMATED COVERAGE IMPROVEMENT:
- Current: 40% → Target: 80%
- Test Count: 20+ comprehensive API tests
- Business Impact: High (document management and search)
- Implementation: Complete RAG API flow validation
"""