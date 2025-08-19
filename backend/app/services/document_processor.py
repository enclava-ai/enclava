"""
Document Processor Service
Handles async document processing with queue management
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.rag_document import RagDocument
from app.models.rag_collection import RagCollection

logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    INDEXED = "indexed"
    ERROR = "error"


@dataclass
class ProcessingTask:
    """Document processing task"""
    document_id: int
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class DocumentProcessor:
    """Async document processor with queue management"""
    
    def __init__(self, max_workers: int = 3, max_queue_size: int = 100):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.processing_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.workers: List[asyncio.Task] = []
        self.running = False
        self.stats = {
            "processed_count": 0,
            "error_count": 0,
            "queue_size": 0,
            "active_workers": 0
        }
        
    async def start(self):
        """Start the document processor"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Starting document processor with {self.max_workers} workers")
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info("Document processor started")
    
    async def stop(self):
        """Stop the document processor"""
        if not self.running:
            return
            
        self.running = False
        logger.info("Stopping document processor...")
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Document processor stopped")
    
    async def add_task(self, document_id: int, priority: int = 1) -> bool:
        """Add a document processing task to the queue"""
        try:
            task = ProcessingTask(document_id=document_id, priority=priority)
            
            # Check if queue is full
            if self.processing_queue.full():
                logger.warning(f"Processing queue is full, dropping task for document {document_id}")
                return False
            
            await self.processing_queue.put(task)
            self.stats["queue_size"] = self.processing_queue.qsize()
            
            logger.info(f"Added processing task for document {document_id} (priority: {priority})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add processing task for document {document_id}: {e}")
            return False
    
    async def _worker(self, worker_name: str):
        """Worker coroutine that processes documents"""
        logger.info(f"Started worker: {worker_name}")
        
        while self.running:
            try:
                # Get task from queue (wait up to 1 second)
                task = await asyncio.wait_for(
                    self.processing_queue.get(), 
                    timeout=1.0
                )
                
                self.stats["active_workers"] += 1
                self.stats["queue_size"] = self.processing_queue.qsize()
                
                logger.info(f"{worker_name}: Processing document {task.document_id}")
                
                # Process the document
                success = await self._process_document(task)
                
                if success:
                    self.stats["processed_count"] += 1
                    logger.info(f"{worker_name}: Successfully processed document {task.document_id}")
                else:
                    # Retry logic
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        await asyncio.sleep(2 ** task.retry_count)  # Exponential backoff
                        await self.processing_queue.put(task)
                        logger.warning(f"{worker_name}: Retrying document {task.document_id} (attempt {task.retry_count})")
                    else:
                        self.stats["error_count"] += 1
                        logger.error(f"{worker_name}: Failed to process document {task.document_id} after {task.max_retries} retries")
                
                self.stats["active_workers"] -= 1
                
            except asyncio.TimeoutError:
                # No tasks in queue, continue
                continue
            except asyncio.CancelledError:
                # Worker cancelled, exit
                break
            except Exception as e:
                self.stats["active_workers"] -= 1
                logger.error(f"{worker_name}: Unexpected error: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing
        
        logger.info(f"Worker stopped: {worker_name}")
    
    async def _process_document(self, task: ProcessingTask) -> bool:
        """Process a single document"""
        from app.db.database import async_session_factory
        async with async_session_factory() as session:
            try:
                # Get document from database
                stmt = (
                    select(RagDocument)
                    .options(selectinload(RagDocument.collection))
                    .where(RagDocument.id == task.document_id)
                )
                result = await session.execute(stmt)
                document = result.scalar_one_or_none()
                
                if not document:
                    logger.error(f"Document {task.document_id} not found")
                    return False
                
                # Update status to processing
                document.status = ProcessingStatus.PROCESSING
                await session.commit()
                
                # Get RAG module for processing (now includes content processing)
                try:
                    from app.services.module_manager import module_manager
                    rag_module = module_manager.get_module('rag')
                except Exception as e:
                    logger.error(f"Failed to get RAG module: {e}")
                    raise Exception(f"RAG module not available: {e}")
                
                if not rag_module:
                    raise Exception("RAG module not available")
                
                logger.info(f"RAG module loaded successfully for document {task.document_id}")
                
                # Read file content
                logger.info(f"Reading file content for document {task.document_id}: {document.file_path}")
                with open(document.file_path, 'rb') as f:
                    file_content = f.read()
                
                logger.info(f"File content read successfully for document {task.document_id}, size: {len(file_content)} bytes")
                
                # Process with RAG module
                logger.info(f"Starting document processing for document {task.document_id} with RAG module")
                try:
                    # Add timeout to prevent hanging
                    processed_doc = await asyncio.wait_for(
                        rag_module.process_document(
                            file_content, 
                            document.original_filename, 
                            {}
                        ),
                        timeout=300.0  # 5 minute timeout
                    )
                    logger.info(f"Document processing completed for document {task.document_id}")
                except asyncio.TimeoutError:
                    logger.error(f"Document processing timed out for document {task.document_id}")
                    raise Exception("Document processing timed out after 5 minutes")
                except Exception as e:
                    logger.error(f"Document processing failed for document {task.document_id}: {e}")
                    raise
                
                # Update document with processed content
                document.converted_content = processed_doc.content
                document.word_count = processed_doc.word_count
                document.character_count = len(processed_doc.content)
                document.document_metadata = processed_doc.metadata
                document.status = ProcessingStatus.PROCESSED
                document.processed_at = datetime.utcnow()
                
                # Index in RAG system using same RAG module
                if rag_module and document.converted_content:
                    try:
                        logger.info(f"Starting indexing for document {task.document_id} in collection {document.collection.qdrant_collection_name}")
                        
                        # Index the document content in the correct Qdrant collection
                        doc_metadata = {
                            "collection_id": document.collection_id,
                            "document_id": document.id,
                            "filename": document.original_filename,
                            "file_type": document.file_type,
                            **document.document_metadata
                        }
                        
                        # Use the correct Qdrant collection name for this document
                        await asyncio.wait_for(
                            rag_module.index_document(
                                content=document.converted_content,
                                metadata=doc_metadata,
                                collection_name=document.collection.qdrant_collection_name
                            ),
                            timeout=120.0  # 2 minute timeout for indexing
                        )
                        
                        logger.info(f"Document {task.document_id} indexed successfully in collection {document.collection.qdrant_collection_name}")
                        
                        # Update vector count (approximate)
                        document.vector_count = max(1, len(document.converted_content) // 1000)
                        document.status = ProcessingStatus.INDEXED
                        document.indexed_at = datetime.utcnow()
                        
                        # Update collection stats
                        collection = document.collection
                        if collection and document.status == ProcessingStatus.INDEXED:
                            collection.document_count += 1
                            collection.size_bytes += document.file_size
                            collection.vector_count += document.vector_count
                            collection.updated_at = datetime.utcnow()
                        
                    except Exception as e:
                        logger.error(f"Failed to index document {task.document_id} in RAG: {e}")
                        # Keep as processed even if indexing fails
                        # Don't raise the exception to avoid retries on indexing failures
                
                await session.commit()
                return True
                
            except Exception as e:
                # Mark document as error
                if 'document' in locals() and document:
                    document.status = ProcessingStatus.ERROR
                    document.processing_error = str(e)
                    await session.commit()
                
                logger.error(f"Error processing document {task.document_id}: {e}")
                return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            **self.stats,
            "running": self.running,
            "worker_count": len(self.workers),
            "queue_size": self.processing_queue.qsize()
        }
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed queue status"""
        return {
            "queue_size": self.processing_queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "queue_full": self.processing_queue.full(),
            "active_workers": self.stats["active_workers"],
            "max_workers": self.max_workers
        }


# Global document processor instance
document_processor = DocumentProcessor()