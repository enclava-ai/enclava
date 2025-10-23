"""
RAG API Endpoints
Provides REST API for RAG (Retrieval Augmented Generation) operations
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import io
import asyncio
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.rag_collection import RagCollection
from app.services.rag_service import RAGService
from app.utils.exceptions import APIException

# Import RAG module from module manager
from app.services.module_manager import module_manager


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
    """Get all RAG collections - live data directly from Qdrant (source of truth)"""
    try:
        from app.services.qdrant_stats_service import qdrant_stats_service

        # Get live stats from Qdrant
        stats_data = await qdrant_stats_service.get_collections_stats()
        collections = stats_data.get("collections", [])

        # Apply pagination
        start_idx = skip
        end_idx = skip + limit
        paginated_collections = collections[start_idx:end_idx]

        return {
            "success": True,
            "collections": paginated_collections,
            "total": len(collections),
            "total_documents": stats_data.get("total_documents", 0),
            "total_size_bytes": stats_data.get("total_size_bytes", 0)
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


@router.get("/stats", response_model=dict)
async def get_rag_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall RAG statistics - live data directly from Qdrant"""
    try:
        from app.services.qdrant_stats_service import qdrant_stats_service

        # Get live stats from Qdrant
        stats_data = await qdrant_stats_service.get_collections_stats()

        # Calculate active collections (collections with documents)
        active_collections = sum(1 for col in stats_data.get("collections", []) if col.get("document_count", 0) > 0)

        # Calculate processing documents from database
        processing_docs = 0
        try:
            from sqlalchemy import select
            from app.models.rag_document import RagDocument, ProcessingStatus

            result = await db.execute(
                select(RagDocument).where(RagDocument.status == ProcessingStatus.PROCESSING)
            )
            processing_docs = len(result.scalars().all())
        except Exception:
            pass  # If database query fails, default to 0

        response_data = {
            "success": True,
            "stats": {
                "collections": {
                    "total": stats_data.get("total_collections", 0),
                    "active": active_collections
                },
                "documents": {
                    "total": stats_data.get("total_documents", 0),
                    "processing": processing_docs,
                    "processed": stats_data.get("total_documents", 0)  # Indexed documents
                },
                "storage": {
                    "total_size_bytes": stats_data.get("total_size_bytes", 0),
                    "total_size_mb": round(stats_data.get("total_size_bytes", 0) / (1024 * 1024), 2)
                },
                "vectors": {
                    "total": stats_data.get("total_documents", 0)  # Same as documents for RAG
                },
                "last_updated": datetime.utcnow().isoformat()
            }
        }

        return response_data
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
    collection_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get documents, optionally filtered by collection"""
    try:
        # Handle collection_id filtering
        collection_id_int = None
        if collection_id:
            # Check if this is an external collection ID (starts with "ext_")
            if collection_id.startswith("ext_"):
                # External collections exist only in Qdrant and have no documents in PostgreSQL
                # Return empty list since they don't have managed documents
                return {
                    "success": True,
                    "documents": [],
                    "total": 0
                }
            else:
                # Try to convert to integer for managed collections
                try:
                    collection_id_int = int(collection_id)
                except (ValueError, TypeError):
                    # Attempt to resolve by Qdrant collection name
                    collection_row = await db.scalar(
                        select(RagCollection).where(RagCollection.qdrant_collection_name == collection_id)
                    )
                    if collection_row:
                        collection_id_int = collection_row.id
                    else:
                        # Unknown collection identifier; return empty result instead of erroring out
                        return {
                            "success": True,
                            "documents": [],
                            "total": 0
                        }
        
        rag_service = RAGService(db)
        documents = await rag_service.get_documents(
            collection_id=collection_id_int,
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
    collection_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process a document"""
    try:
        # Validate file can be read before processing
        filename = file.filename or "unknown"
        file_extension = filename.split('.')[-1].lower() if '.' in filename else ''

        # Read file content once and use it for all validations
        file_content = await file.read()

        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if len(file_content) > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")

        try:
            # Test file readability based on type
            if file_extension == 'jsonl':
                # Validate JSONL format - try to parse first few lines
                try:
                    content_str = file_content.decode('utf-8')
                    lines = content_str.strip().split('\n')[:5]  # Check first 5 lines
                    import json
                    for i, line in enumerate(lines):
                        if line.strip():  # Skip empty lines
                            json.loads(line)  # Will raise JSONDecodeError if invalid
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")
                except json.JSONDecodeError as e:
                    raise HTTPException(status_code=400, detail=f"Invalid JSONL format: {str(e)}")

            elif file_extension in ['txt', 'md', 'py', 'js', 'html', 'css', 'json']:
                # Validate text files can be decoded
                try:
                    file_content.decode('utf-8')
                except UnicodeDecodeError:
                    raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

            elif file_extension in ['pdf']:
                # For PDF files, just check if it starts with PDF signature
                if not file_content.startswith(b'%PDF'):
                    raise HTTPException(status_code=400, detail="Invalid PDF file format")

            elif file_extension in ['docx', 'xlsx', 'pptx']:
                # For Office documents, check ZIP signature
                if not file_content.startswith(b'PK'):
                    raise HTTPException(status_code=400, detail=f"Invalid {file_extension.upper()} file format")

            # For other file types, we'll rely on the document processor

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"File validation failed: {str(e)}")

        rag_service = RAGService(db)

        # Resolve collection identifier (supports both numeric IDs and Qdrant collection names)
        collection_identifier = (collection_id or "").strip()
        if not collection_identifier:
            raise HTTPException(status_code=400, detail="Collection identifier is required")

        resolved_collection_id: Optional[int] = None

        if collection_identifier.isdigit():
            resolved_collection_id = int(collection_identifier)
        else:
            qdrant_name = collection_identifier
            if qdrant_name.startswith("ext_"):
                qdrant_name = qdrant_name[4:]

            try:
                collection_record = await rag_service.ensure_collection_record(qdrant_name)
            except Exception as ensure_error:
                raise HTTPException(status_code=500, detail=str(ensure_error))

            resolved_collection_id = collection_record.id

        if resolved_collection_id is None:
            raise HTTPException(status_code=400, detail="Invalid collection identifier")

        document = await rag_service.upload_document(
            collection_id=resolved_collection_id,
            file_content=file_content,
            filename=filename,
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



# Debug Endpoints

@router.post("/debug/search")
async def search_with_debug(
    query: str,
    max_results: int = 10,
    score_threshold: float = 0.3,
    collection_name: str = None,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Enhanced search with comprehensive debug information
    """
    # Get RAG module from module manager
    rag_module = module_manager.modules.get('rag')
    if not rag_module or not rag_module.enabled:
        raise HTTPException(status_code=503, detail="RAG module not initialized")

    debug_info = {}
    start_time = datetime.utcnow()

    try:
        # Apply configuration if provided
        if config:
            # Update RAG config temporarily
            original_config = rag_module.config.copy()
            rag_module.config.update(config)

        # Generate query embedding (with or without prefix)
        if config and config.get("use_query_prefix"):
            optimized_query = f"query: {query}"
        else:
            optimized_query = query

        query_embedding = await rag_module._generate_embedding(optimized_query)

        # Store embedding info for debug
        if config and config.get("debug", {}).get("show_embeddings"):
            debug_info["query_embedding"] = query_embedding[:10]  # First 10 dimensions
            debug_info["embedding_dimension"] = len(query_embedding)
            debug_info["optimized_query"] = optimized_query

        # Perform search
        search_start = asyncio.get_event_loop().time()
        results = await rag_module.search_documents(
            query,
            max_results=max_results,
            score_threshold=score_threshold,
            collection_name=collection_name
        )
        search_time = (asyncio.get_event_loop().time() - search_start) * 1000

        # Calculate score statistics
        scores = [r.score for r in results if r.score is not None]
        if scores:
            import statistics
            debug_info["score_stats"] = {
                "min": min(scores),
                "max": max(scores),
                "avg": statistics.mean(scores),
                "stddev": statistics.stdev(scores) if len(scores) > 1 else 0
            }

        # Get collection statistics
        try:
            from qdrant_client.http.models import Filter
            collection_name = collection_name or rag_module.default_collection_name

            # Count total documents
            count_result = rag_module.qdrant_client.count(
                collection_name=collection_name,
                count_filter=Filter(must=[])
            )
            total_points = count_result.count

            # Get unique documents and languages
            scroll_result = rag_module.qdrant_client.scroll(
                collection_name=collection_name,
                limit=1000,  # Sample for stats
                with_payload=True,
                with_vectors=False
            )

            unique_docs = set()
            languages = set()

            for point in scroll_result[0]:
                payload = point.payload or {}
                doc_id = payload.get("document_id")
                if doc_id:
                    unique_docs.add(doc_id)

                language = payload.get("language")
                if language:
                    languages.add(language)

            debug_info["collection_stats"] = {
                "total_documents": len(unique_docs),
                "total_chunks": total_points,
                "languages": sorted(list(languages))
            }

        except Exception as e:
            debug_info["collection_stats_error"] = str(e)

        # Enhance results with debug info
        enhanced_results = []
        for result in results:
            enhanced_result = {
                "document": {
                    "id": result.document.id,
                    "content": result.document.content,
                    "metadata": result.document.metadata
                },
                "score": result.score,
                "debug_info": {}
            }

            # Add hybrid search debug info if available
            metadata = result.document.metadata or {}
            if "_vector_score" in metadata:
                enhanced_result["debug_info"]["vector_score"] = metadata["_vector_score"]
            if "_bm25_score" in metadata:
                enhanced_result["debug_info"]["bm25_score"] = metadata["_bm25_score"]

            enhanced_results.append(enhanced_result)

        # Note: Analytics logging disabled (module not available)

        return {
            "results": enhanced_results,
            "debug_info": debug_info,
            "search_time_ms": search_time,
            "timestamp": start_time.isoformat()
        }

    except Exception as e:
        # Note: Analytics logging disabled (module not available)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    finally:
        # Restore original config if modified
        if config and 'original_config' in locals():
            rag_module.config = original_config


@router.get("/debug/config")
async def get_current_config(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current RAG configuration"""
    # Get RAG module from module manager
    rag_module = module_manager.modules.get('rag')
    if not rag_module or not rag_module.enabled:
        raise HTTPException(status_code=503, detail="RAG module not initialized")

    return {
        "config": rag_module.config,
        "embedding_model": rag_module.embedding_model,
        "enabled": rag_module.enabled,
        "collections": await rag_module._get_collections_safely()
    }
