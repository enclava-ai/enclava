"""
RAG API Endpoints
Provides REST API for RAG (Retrieval Augmented Generation) operations
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import io

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.rag_service import RAGService
from app.utils.exceptions import APIException


router = APIRouter(tags=["RAG"])


# Request/Response Models

class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str
    document_count: int
    size_bytes: int
    vector_count: int
    status: str
    created_at: str
    updated_at: str
    is_active: bool


class DocumentResponse(BaseModel):
    id: str
    collection_id: str
    collection_name: Optional[str]
    filename: str
    original_filename: str
    file_type: str
    size: int
    mime_type: Optional[str]
    status: str
    processing_error: Optional[str]
    converted_content: Optional[str]
    word_count: int
    character_count: int
    vector_count: int
    metadata: dict
    created_at: str
    processed_at: Optional[str]
    indexed_at: Optional[str]
    updated_at: str


class StatsResponse(BaseModel):
    collections: dict
    documents: dict
    storage: dict
    vectors: dict


# Collection Endpoints

@router.get("/collections", response_model=dict)
async def get_collections(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all RAG collections from Qdrant (source of truth) with PostgreSQL metadata"""
    try:
        rag_service = RAGService(db)
        collections_data = await rag_service.get_all_collections(skip=skip, limit=limit)
        return {
            "success": True,
            "collections": collections_data,
            "total": len(collections_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections", response_model=dict)
async def create_collection(
    collection_data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new RAG collection"""
    try:
        rag_service = RAGService(db)
        collection = await rag_service.create_collection(
            name=collection_data.name,
            description=collection_data.description
        )
        
        return {
            "success": True,
            "collection": collection.to_dict(),
            "message": "Collection created successfully"
        }
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_id}", response_model=dict)
async def get_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific collection"""
    try:
        rag_service = RAGService(db)
        collection = await rag_service.get_collection(collection_id)
        
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        return {
            "success": True,
            "collection": collection.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: int,
    cascade: bool = True,  # Default to cascade deletion for better UX
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a collection and optionally all its documents"""
    try:
        rag_service = RAGService(db)
        success = await rag_service.delete_collection(collection_id, cascade=cascade)
        
        if not success:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        return {
            "success": True,
            "message": "Collection deleted successfully" + (" (with documents)" if cascade else "")
        }
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Document Endpoints

@router.get("/documents", response_model=dict)
async def get_documents(
    collection_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get documents, optionally filtered by collection"""
    try:
        rag_service = RAGService(db)
        documents = await rag_service.get_documents(
            collection_id=collection_id,
            skip=skip,
            limit=limit
        )
        
        return {
            "success": True,
            "documents": [doc.to_dict() for doc in documents],
            "total": len(documents)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents", response_model=dict)
async def upload_document(
    collection_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process a document"""
    try:
        # Read file content
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        if len(file_content) > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        
        rag_service = RAGService(db)
        document = await rag_service.upload_document(
            collection_id=collection_id,
            file_content=file_content,
            filename=file.filename or "unknown",
            content_type=file.content_type
        )
        
        return {
            "success": True,
            "document": document.to_dict(),
            "message": "Document uploaded and processing started"
        }
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}", response_model=dict)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific document"""
    try:
        rag_service = RAGService(db)
        document = await rag_service.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "document": document.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}", response_model=dict)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document"""
    try:
        rag_service = RAGService(db)
        success = await rag_service.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "message": "Document deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/reprocess", response_model=dict)
async def reprocess_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Restart processing for a stuck or failed document"""
    try:
        rag_service = RAGService(db)
        success = await rag_service.reprocess_document(document_id)
        
        if not success:
            # Get document to check if it exists and its current status
            document = await rag_service.get_document(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot reprocess document with status '{document.status}'. Only 'processing' or 'error' documents can be reprocessed."
                )
        
        return {
            "success": True,
            "message": "Document reprocessing started successfully"
        }
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download the original document file"""
    try:
        rag_service = RAGService(db)
        result = await rag_service.download_document(document_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Document not found or file not available")
        
        content, filename, mime_type = result
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=mime_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Stats Endpoint

@router.get("/stats", response_model=dict)
async def get_rag_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get RAG system statistics"""
    try:
        rag_service = RAGService(db)
        stats = await rag_service.get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))