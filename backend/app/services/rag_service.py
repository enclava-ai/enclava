"""
RAG Service
Handles all RAG (Retrieval Augmented Generation) operations including
collections, documents, processing, and vector operations
"""

import os
import uuid
import mimetypes
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import hashlib
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models.rag_collection import RagCollection
from app.models.rag_document import RagDocument
from app.utils.exceptions import APIException

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.upload_dir = Path("storage/rag_documents")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Collection Operations
    
    async def create_collection(self, name: str, description: Optional[str] = None) -> RagCollection:
        """Create a new RAG collection"""
        # Check if collection name already exists
        stmt = select(RagCollection).where(RagCollection.name == name, RagCollection.is_active == True)
        existing = await self.db.scalar(stmt)
        if existing:
            raise APIException(status_code=400, error_code="COLLECTION_EXISTS", detail=f"Collection '{name}' already exists")
        
        # Generate unique Qdrant collection name
        qdrant_name = f"rag_{name.lower().replace(' ', '_').replace('-', '_')}_{uuid.uuid4().hex[:8]}"
        
        # Create collection
        collection = RagCollection(
            name=name,
            description=description,
            qdrant_collection_name=qdrant_name,
            status='active'
        )
        
        self.db.add(collection)
        await self.db.commit()
        await self.db.refresh(collection)
        
        # Create Qdrant collection
        await self._create_qdrant_collection(qdrant_name)
        
        return collection
    
    async def get_collections(self, skip: int = 0, limit: int = 100) -> List[RagCollection]:
        """Get all active collections"""
        stmt = (
            select(RagCollection)
            .where(RagCollection.is_active == True)
            .order_by(RagCollection.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_collection(self, collection_id: int) -> Optional[RagCollection]:
        """Get a collection by ID"""
        stmt = select(RagCollection).where(
            RagCollection.id == collection_id,
            RagCollection.is_active == True
        )
        return await self.db.scalar(stmt)

    async def get_collection_by_qdrant_name(self, qdrant_collection_name: str) -> Optional[RagCollection]:
        """Get a collection using its Qdrant collection name"""
        stmt = select(RagCollection).where(
            RagCollection.qdrant_collection_name == qdrant_collection_name
        )
        return await self.db.scalar(stmt)

    async def ensure_collection_record(self, qdrant_collection_name: str) -> RagCollection:
        """Ensure we have a managed record for a given Qdrant collection"""
        existing = await self.get_collection_by_qdrant_name(qdrant_collection_name)
        if existing:
            return existing

        # Create a friendly name from the Qdrant collection identifier
        friendly_name = qdrant_collection_name
        try:
            if qdrant_collection_name.startswith("rag_"):
                trimmed = qdrant_collection_name[4:]
                parts = [part for part in trimmed.split("_") if part]
                if parts:
                    friendly_name = " ".join(parts).title()
        except Exception:
            # Fall back to original identifier on any parsing issues
            friendly_name = qdrant_collection_name

        collection = RagCollection(
            name=friendly_name,
            description=f"Synced from Qdrant collection '{qdrant_collection_name}'",
            qdrant_collection_name=qdrant_collection_name,
            status='active',
            is_active=True
        )

        self.db.add(collection)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            # Another request might have created the collection concurrently; fetch again
            existing = await self.get_collection_by_qdrant_name(qdrant_collection_name)
            if existing:
                return existing
            raise

        await self.db.refresh(collection)
        return collection

    async def get_all_collections(self, skip: int = 0, limit: int = 100) -> List[dict]:
        """Get all collections from Qdrant (source of truth) with additional metadata from PostgreSQL."""
        logger.info("Getting all RAG collections from Qdrant (source of truth)")
        
        all_collections = []
        
        try:
            # Get RAG module instance to access Qdrant collections
            from app.services.module_manager import module_manager
            rag_module = module_manager.get_module("rag")
            
            if not rag_module or not hasattr(rag_module, 'qdrant_client'):
                logger.warning("RAG module or Qdrant client not available")
                # Fallback to PostgreSQL only
                managed_collections = await self.get_collections(skip=skip, limit=limit)
                return [
                    {
                        "id": collection.id,
                        "name": collection.name,
                        "description": collection.description or "",
                        "document_count": collection.document_count or 0,
                        "size_bytes": collection.size_bytes or 0,
                        "vector_count": collection.vector_count or 0,
                        "status": collection.status,
                        "created_at": collection.created_at.isoformat() if collection.created_at else "",
                        "updated_at": collection.updated_at.isoformat() if collection.updated_at else "",
                        "is_active": collection.is_active,
                        "qdrant_collection_name": collection.qdrant_collection_name,
                        "is_managed": True,
                        "source": "managed"
                    }
                    for collection in managed_collections
                ]
            
            # Get all collections from Qdrant (source of truth) using safe method
            qdrant_collection_names = await rag_module._get_collections_safely()
            logger.info(f"Found {len(qdrant_collection_names)} collections in Qdrant")
            
            # Get metadata from PostgreSQL for additional info
            db_metadata = await self.get_collections(skip=0, limit=1000)
            metadata_by_name = {col.qdrant_collection_name: col for col in db_metadata}
            
            # Process each Qdrant collection
            for qdrant_name in qdrant_collection_names:
                logger.info(f"Processing Qdrant collection: {qdrant_name}")
                
                try:
                    # Get detailed collection info from Qdrant using safe method
                    collection_info = await rag_module._get_collection_info_safely(qdrant_name)
                    point_count = collection_info.get("points_count", 0)
                    vector_size = collection_info.get("vector_size", 384)
                    
                    # Estimate collection size (points * vector_size * 4 bytes + metadata overhead)
                    estimated_size = int(point_count * vector_size * 4 * 1.2)  # 20% overhead for metadata
                    
                    # Get metadata from PostgreSQL if available
                    db_metadata_entry = metadata_by_name.get(qdrant_name)
                    
                    if db_metadata_entry:
                        # Use PostgreSQL metadata but Qdrant data for counts/size
                        collection_data = {
                            "id": db_metadata_entry.id,
                            "name": db_metadata_entry.name,
                            "description": db_metadata_entry.description or "",
                            "document_count": point_count,  # From Qdrant (real data)
                            "size_bytes": estimated_size,   # From Qdrant (real data)
                            "vector_count": point_count,    # From Qdrant (real data)
                            "status": db_metadata_entry.status,
                            "created_at": db_metadata_entry.created_at.isoformat() if db_metadata_entry.created_at else "",
                            "updated_at": db_metadata_entry.updated_at.isoformat() if db_metadata_entry.updated_at else "",
                            "is_active": db_metadata_entry.is_active,
                            "qdrant_collection_name": qdrant_name,
                            "is_managed": True,
                            "source": "managed"
                        }
                    else:
                        # Collection exists in Qdrant but not in our metadata
                        from datetime import datetime
                        now = datetime.utcnow()
                        collection_data = {
                            "id": f"ext_{qdrant_name}",  # External identifier
                            "name": qdrant_name,
                            "description": f"External Qdrant collection (vectors: {vector_size}d, points: {point_count})",
                            "document_count": point_count,  # From Qdrant
                            "size_bytes": estimated_size,   # From Qdrant
                            "vector_count": point_count,    # From Qdrant
                            "status": "active",
                            "created_at": now.isoformat(),
                            "updated_at": now.isoformat(),
                            "is_active": True,
                            "qdrant_collection_name": qdrant_name,
                            "is_managed": False,
                            "source": "external"
                        }
                    
                    all_collections.append(collection_data)
                    
                except Exception as e:
                    logger.error(f"Error processing collection {qdrant_name}: {e}")
                    # Still add the collection but with minimal info
                    from datetime import datetime
                    now = datetime.utcnow()
                    collection_data = {
                        "id": f"ext_{qdrant_name}",
                        "name": qdrant_name,
                        "description": f"External Qdrant collection (error loading details: {str(e)})",
                        "document_count": 0,
                        "size_bytes": 0,
                        "vector_count": 0,
                        "status": "error",
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                        "is_active": True,
                        "qdrant_collection_name": qdrant_name,
                        "is_managed": False,
                        "source": "external"
                    }
                    all_collections.append(collection_data)
                    
        except Exception as e:
            logger.error(f"Error fetching collections from Qdrant: {e}")
            # Fallback to managed collections only
            managed_collections = await self.get_collections(skip=skip, limit=limit)
            return [
                {
                    "id": collection.id,
                    "name": collection.name,
                    "description": collection.description or "",
                    "document_count": collection.document_count or 0,
                    "size_bytes": collection.size_bytes or 0,
                    "vector_count": collection.vector_count or 0,
                    "status": collection.status,
                    "created_at": collection.created_at.isoformat() if collection.created_at else "",
                    "updated_at": collection.updated_at.isoformat() if collection.updated_at else "",
                    "is_active": collection.is_active,
                    "qdrant_collection_name": collection.qdrant_collection_name,
                    "is_managed": True,
                    "source": "managed"
                }
                for collection in managed_collections
            ]
        
        # Apply pagination
        if skip > 0 or limit < len(all_collections):
            all_collections = all_collections[skip:skip + limit]
        
        logger.info(f"Total collections returned: {len(all_collections)}")
        return all_collections
    
    async def delete_collection(self, collection_id: int, cascade: bool = True) -> bool:
        """Delete a collection and optionally all its documents"""
        collection = await self.get_collection(collection_id)
        if not collection:
            return False
        
        # Get all documents in the collection
        stmt = select(RagDocument).where(
            RagDocument.collection_id == collection_id,
            RagDocument.is_deleted == False
        )
        result = await self.db.execute(stmt)
        documents = result.scalars().all()
        
        if documents and not cascade:
            raise APIException(
                status_code=400, 
                error_code="COLLECTION_HAS_DOCUMENTS",
                detail=f"Cannot delete collection with {len(documents)} documents. Set cascade=true to delete documents along with collection."
            )
        
        # Delete all documents in the collection (cascade deletion)
        if documents:
            for document in documents:
                # Soft delete document
                document.is_deleted = True
                document.deleted_at = datetime.utcnow()
                
                # Delete physical file if it exists
                try:
                    import os
                    if os.path.exists(document.file_path):
                        os.remove(document.file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete file {document.file_path}: {e}")
        
        # Soft delete collection
        collection.is_active = False
        collection.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Delete Qdrant collection
        try:
            await self._delete_qdrant_collection(collection.qdrant_collection_name)
        except Exception as e:
            logger.warning(f"Failed to delete Qdrant collection {collection.qdrant_collection_name}: {e}")
        
        return True
    
    # Document Operations
    
    async def upload_document(
        self, 
        collection_id: int, 
        file_content: bytes, 
        filename: str, 
        content_type: Optional[str] = None
    ) -> RagDocument:
        """Upload and process a document"""
        # Verify collection exists
        collection = await self.get_collection(collection_id)
        if not collection:
            raise APIException(status_code=404, error_code="COLLECTION_NOT_FOUND", detail="Collection not found")
        
        # Validate file type
        file_ext = Path(filename).suffix.lower()
        if not self._is_supported_file_type(file_ext):
            raise APIException(
                status_code=400, 
                error_code="UNSUPPORTED_FILE_TYPE",
                detail=f"Unsupported file type: {file_ext}. Supported: .pdf, .docx, .doc, .txt, .md, .html, .json, .jsonl, .csv, .xlsx, .xls"
            )
        
        # Generate safe filename
        safe_filename = self._generate_safe_filename(filename)
        file_path = self.upload_dir / f"{collection_id}" / safe_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Detect MIME type
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
        
        # Create document record
        document = RagDocument(
            collection_id=collection_id,
            filename=safe_filename,
            original_filename=filename,
            file_path=str(file_path),
            file_type=file_ext.lstrip('.'),
            file_size=len(file_content),
            mime_type=content_type,
            status='processing'
        )
        
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        # Load the collection relationship to avoid lazy loading issues
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        stmt = select(RagDocument).options(selectinload(RagDocument.collection)).where(RagDocument.id == document.id)
        result = await self.db.execute(stmt)
        document = result.scalar_one()
        
        # Add document to processing queue
        from app.services.document_processor import document_processor
        await document_processor.add_task(document.id, priority=1)
        
        return document
    
    async def get_documents(
        self, 
        collection_id: Optional[int] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[RagDocument]:
        """Get documents, optionally filtered by collection"""
        stmt = (
            select(RagDocument)
            .options(selectinload(RagDocument.collection))
            .where(RagDocument.is_deleted == False)
            .order_by(RagDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        if collection_id:
            stmt = stmt.where(RagDocument.collection_id == collection_id)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_document(self, document_id: int) -> Optional[RagDocument]:
        """Get a document by ID"""
        stmt = (
            select(RagDocument)
            .options(selectinload(RagDocument.collection))
            .where(
                RagDocument.id == document_id,
                RagDocument.is_deleted == False
            )
        )
        return await self.db.scalar(stmt)
    
    async def delete_document(self, document_id: int) -> bool:
        """Delete a document"""
        document = await self.get_document(document_id)
        if not document:
            return False
        
        # Soft delete document
        document.is_deleted = True
        document.deleted_at = datetime.utcnow()
        document.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Update collection statistics
        await self._update_collection_stats(document.collection_id)
        
        # Remove vectors from Qdrant
        await self._delete_document_vectors(document.id, document.collection.qdrant_collection_name)
        
        # Remove file
        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {document.file_path}: {e}")
        
        return True
    
    async def download_document(self, document_id: int) -> Optional[Tuple[bytes, str, str]]:
        """Download original document file"""
        document = await self.get_document(document_id)
        if not document or not os.path.exists(document.file_path):
            return None
        
        try:
            with open(document.file_path, 'rb') as f:
                content = f.read()
            
            return content, document.original_filename, document.mime_type or 'application/octet-stream'
        except Exception:
            return None
    
    # Stats and Analytics
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        # Collection stats
        collection_count_stmt = select(func.count(RagCollection.id)).where(RagCollection.is_active == True)
        total_collections = await self.db.scalar(collection_count_stmt)
        
        # Document stats
        doc_count_stmt = select(func.count(RagDocument.id)).where(RagDocument.is_deleted == False)
        total_documents = await self.db.scalar(doc_count_stmt)
        
        # Processing stats
        processing_stmt = select(func.count(RagDocument.id)).where(
            RagDocument.is_deleted == False,
            RagDocument.status == 'processing'
        )
        processing_documents = await self.db.scalar(processing_stmt)
        
        # Size stats
        size_stmt = select(func.sum(RagDocument.file_size)).where(RagDocument.is_deleted == False)
        total_size = await self.db.scalar(size_stmt) or 0
        
        # Vector stats
        vector_stmt = select(func.sum(RagDocument.vector_count)).where(RagDocument.is_deleted == False)
        total_vectors = await self.db.scalar(vector_stmt) or 0
        
        return {
            "collections": {
                "total": total_collections or 0,
                "active": total_collections or 0
            },
            "documents": {
                "total": total_documents or 0,
                "processing": processing_documents or 0,
                "processed": (total_documents or 0) - (processing_documents or 0)
            },
            "storage": {
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0
            },
            "vectors": {
                "total": total_vectors
            }
        }
    
    # Private Helper Methods
    
    def _is_supported_file_type(self, file_ext: str) -> bool:
        """Check if file type is supported"""
        supported_types = {'.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.json', '.jsonl', '.csv', '.xlsx', '.xls'}
        return file_ext.lower() in supported_types
    
    def _generate_safe_filename(self, filename: str) -> str:
        """Generate a safe filename for storage"""
        # Extract extension
        path = Path(filename)
        ext = path.suffix
        name = path.stem
        
        # Create hash of original filename for uniqueness
        hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:8]
        
        # Sanitize name
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        # Combine with timestamp and hash
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe_name}_{timestamp}_{hash_suffix}{ext}"
    
    async def _create_qdrant_collection(self, collection_name: str):
        """Create Qdrant collection with proper error handling"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            from qdrant_client.http import models
            from app.core.config import settings
            
            client = QdrantClient(
                host=getattr(settings, 'QDRANT_HOST', 'localhost'), 
                port=getattr(settings, 'QDRANT_PORT', 6333),
                timeout=30
            )
            
            # Check if collection already exists
            try:
                collections = client.get_collections()
                if collection_name in [c.name for c in collections.collections]:
                    logger.info(f"Collection {collection_name} already exists")
                    return True
            except Exception as e:
                logger.warning(f"Could not check existing collections: {e}")
                
            # Create collection with proper vector configuration  
            from app.services.embedding_service import embedding_service

            vector_dimension = getattr(embedding_service, 'dimension', 384) or 384

            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_dimension,
                    distance=Distance.COSINE
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                    deleted_threshold=0.2,
                    vacuum_min_vector_number=1000,
                    flush_interval_sec=5,
                    max_optimization_threads=1
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000
                )
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
            return True
            
        except ImportError as e:
            logger.error(f"Qdrant client not available: {e}")
            logger.warning("Install qdrant-client package to enable vector search: pip install qdrant-client")
            return False
            
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection {collection_name}: {e}")
            from app.utils.exceptions import APIException
            raise APIException(
                status_code=500,
                error_code="QDRANT_COLLECTION_ERROR", 
                detail=f"Vector database collection creation failed: {str(e)}"
            )
    
    async def _delete_qdrant_collection(self, collection_name: str):
        """Delete collection from Qdrant vector database"""
        try:
            from qdrant_client import QdrantClient
            from app.core.config import settings
            
            client = QdrantClient(
                host=getattr(settings, 'QDRANT_HOST', 'localhost'), 
                port=getattr(settings, 'QDRANT_PORT', 6333),
                timeout=30
            )
            
            # Check if collection exists before trying to delete
            try:
                collections = client.get_collections()
                if collection_name not in [c.name for c in collections.collections]:
                    logger.warning(f"Qdrant collection {collection_name} not found, nothing to delete")
                    return True
            except Exception as e:
                logger.warning(f"Could not check existing collections: {e}")
                
            # Delete the collection
            client.delete_collection(collection_name)
            logger.info(f"Deleted Qdrant collection: {collection_name}")
            return True
            
        except ImportError as e:
            logger.error(f"Qdrant client not available: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting Qdrant collection {collection_name}: {e}")
            # Don't re-raise the error for deletion as it's not critical if cleanup fails
            return False
    
    async def check_qdrant_health(self) -> Dict[str, Any]:
        """Check Qdrant database connectivity and health"""
        try:
            from qdrant_client import QdrantClient
            from app.core.config import settings
            
            client = QdrantClient(
                host=getattr(settings, 'QDRANT_HOST', 'localhost'), 
                port=getattr(settings, 'QDRANT_PORT', 6333),
                timeout=5  # Short timeout for health check
            )
            
            # Try to get collections (basic connectivity test)
            collections = client.get_collections()
            collection_count = len(collections.collections)
            
            return {
                "status": "healthy",
                "qdrant_host": getattr(settings, 'QDRANT_HOST', 'localhost'),
                "qdrant_port": getattr(settings, 'QDRANT_PORT', 6333),
                "collections_count": collection_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except ImportError:
            return {
                "status": "unavailable",
                "error": "Qdrant client not installed",
                "recommendation": "Install qdrant-client package",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "qdrant_host": getattr(settings, 'QDRANT_HOST', 'localhost'),
                "qdrant_port": getattr(settings, 'QDRANT_PORT', 6333),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _update_collection_stats(self, collection_id: int):
        """Update collection statistics (document count, size, etc.)"""
        try:
            # Get collection
            collection = await self.get_collection(collection_id) 
            if not collection:
                return
            
            # Count active documents
            stmt = select(func.count(RagDocument.id)).where(
                RagDocument.collection_id == collection_id,
                RagDocument.is_deleted == False
            )
            doc_count = await self.db.scalar(stmt) or 0
            
            # Sum file sizes
            stmt = select(func.sum(RagDocument.file_size)).where(
                RagDocument.collection_id == collection_id,
                RagDocument.is_deleted == False
            )
            total_size = await self.db.scalar(stmt) or 0
            
            # Sum vector counts
            stmt = select(func.sum(RagDocument.vector_count)).where(
                RagDocument.collection_id == collection_id,
                RagDocument.is_deleted == False
            )
            vector_count = await self.db.scalar(stmt) or 0
            
            # Update collection
            collection.document_count = doc_count
            collection.size_bytes = total_size
            collection.vector_count = vector_count
            collection.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update collection stats for {collection_id}: {e}")
    
    async def _delete_document_vectors(self, document_id: int, collection_name: str):
        """Delete document vectors from Qdrant"""
        try:
            # Get RAG module to delete the document vectors
            try:
                from app.services.module_manager import module_manager
                rag_module = module_manager.get_module('rag')
            except ImportError as e:
                logger.error(f"Failed to import module_manager: {e}")
                rag_module = None
            
            if rag_module and hasattr(rag_module, 'delete_document'):
                # Create a document ID that matches what was used during indexing
                doc_id = str(document_id)
                success = await rag_module.delete_document(doc_id, collection_name)
                if success:
                    logger.info(f"Deleted vectors for document {document_id} from collection {collection_name}")
                else:
                    logger.warning(f"No vectors found for document {document_id} in collection {collection_name}")
            else:
                logger.warning("RAG module not available for document vector deletion")
                
        except Exception as e:
            logger.error(f"Error deleting document vectors for {document_id} from {collection_name}: {e}")
            # Don't re-raise the error as document deletion should continue
    
    async def _get_qdrant_collections(self) -> List[str]:
        """Get list of all collection names from Qdrant"""
        try:
            # Get RAG module to access Qdrant collections
            from app.services.module_manager import module_manager
            rag_module = module_manager.get_module('rag')
            
            if rag_module and hasattr(rag_module, '_get_collections_safely'):
                return await rag_module._get_collections_safely()
            else:
                logger.warning("RAG module or safe collections method not available")
                return []
                
        except Exception as e:
            logger.error(f"Error getting Qdrant collections: {e}")
            return []
    
    async def _get_qdrant_collection_point_count(self, collection_name: str) -> int:
        """Get the number of points (documents) in a Qdrant collection"""
        try:
            # Get RAG module to access Qdrant collections
            from app.services.module_manager import module_manager
            rag_module = module_manager.get_module('rag')
            
            if rag_module and hasattr(rag_module, '_get_collection_info_safely'):
                collection_info = await rag_module._get_collection_info_safely(collection_name)
                return collection_info.get("points_count", 0)
            else:
                logger.warning("RAG module or safe collection info method not available")
                return 0
                
        except Exception as e:
            logger.warning(f"Could not get point count for collection {collection_name}: {e}")
            return 0
    
    async def _process_document(self, document_id: int):
        """Process document content and create vectors"""
        try:
            # Get fresh document from database
            async with self.db as session:
                document = await session.get(RagDocument, document_id)
                if not document:
                    return
                
                # Process with RAG module (now includes content processing)
                try:
                    from app.services.module_manager import module_manager
                    rag_module = module_manager.get_module('rag')
                except ImportError as e:
                    logger.error(f"Failed to import module_manager: {e}")
                    rag_module = None
                
                if rag_module:
                    # Read file content
                    with open(document.file_path, 'rb') as f:
                        file_content = f.read()
                    
                    # Process with RAG module
                    try:
                        # Pass file_path in metadata so JSONL indexing can reopen the source file
                        processed_doc = await rag_module.process_document(
                            file_content,
                            document.original_filename,
                            {"file_path": document.file_path}
                        )
                        
                        # Success case - update document with processed content
                        document.converted_content = processed_doc.content
                        document.word_count = processed_doc.word_count
                        document.character_count = len(processed_doc.content)
                        document.document_metadata = processed_doc.metadata
                        document.status = 'processed'
                        document.processed_at = datetime.utcnow()
                        
                        # Index the processed document in the correct Qdrant collection
                        try:
                            # Get the collection's Qdrant collection name
                            from sqlalchemy.orm import selectinload
                            from sqlalchemy import select
                            stmt = select(RagDocument).options(selectinload(RagDocument.collection)).where(RagDocument.id == document_id)
                            result = await session.execute(stmt)
                            doc_with_collection = result.scalar_one()
                            
                            qdrant_collection_name = doc_with_collection.collection.qdrant_collection_name
                            
                            # Index in Qdrant with the correct collection name
                            await rag_module.index_processed_document(processed_doc, qdrant_collection_name)
                            
                            # Calculate actual vector count (estimate based on content length)
                            document.vector_count = max(1, len(processed_doc.content) // 500)  # ~500 chars per chunk
                            document.status = 'indexed'
                            document.indexed_at = datetime.utcnow()
                            
                        except Exception as index_error:
                            logger.error(f"Failed to index document {document_id} in Qdrant: {index_error}")
                            document.status = 'error'
                            document.processing_error = f"Indexing failed: {str(index_error)}"
                        
                        # Update collection stats
                        if document.status == 'indexed':
                            collection = doc_with_collection.collection
                            collection.document_count += 1
                            collection.size_bytes += document.file_size
                            collection.vector_count += document.vector_count
                            collection.updated_at = datetime.utcnow()
                        
                    except Exception as e:
                        # Error case - mark document as failed
                        document.status = 'error'
                        document.processing_error = str(e)
                    
                    await session.commit()
                else:
                    # No RAG module available
                    document.status = 'error'
                    document.processing_error = 'RAG module not available'
                    await session.commit()
                    
        except Exception as e:
            # Update document with error status
            async with self.db as session:
                document = await session.get(RagDocument, document_id)
                if document:
                    document.status = 'error'
                    document.processing_error = str(e)
                    await session.commit()
    
    async def reprocess_document(self, document_id: int) -> bool:
        """Restart processing for a stuck or failed document"""
        try:
            # Get document from database
            document = await self.get_document(document_id)
            if not document:
                logger.error(f"Document {document_id} not found for reprocessing")
                return False
            
            # Check if document is in a state where reprocessing makes sense
            if document.status not in ['processing', 'error']:
                logger.warning(f"Document {document_id} status is '{document.status}', cannot reprocess")
                return False
            
            logger.info(f"Restarting processing for document {document_id} (current status: {document.status})")
            
            # Reset document status and clear errors
            document.status = 'pending'
            document.processing_error = None
            document.processed_at = None
            document.indexed_at = None
            document.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            # Re-queue document for processing
            try:
                from app.services.document_processor import document_processor
                success = await document_processor.add_task(document_id, priority=1)
                
                if success:
                    logger.info(f"Document {document_id} successfully re-queued for processing")
                else:
                    logger.error(f"Failed to re-queue document {document_id} for processing")
                    # Revert status back to error
                    document.status = 'error'
                    document.processing_error = "Failed to re-queue for processing"
                    await self.db.commit()
                
                return success
                
            except Exception as e:
                logger.error(f"Error re-queuing document {document_id}: {e}")
                # Revert status back to error
                document.status = 'error'
                document.processing_error = f"Failed to re-queue: {str(e)}"
                await self.db.commit()
                return False
                
        except Exception as e:
            logger.error(f"Error reprocessing document {document_id}: {e}")
            return False
