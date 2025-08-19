"""
RAG Document Model
Represents documents within RAG collections
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, BigInteger, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    
    # Collection relationship
    collection_id = Column(Integer, ForeignKey("rag_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    collection = relationship("RagCollection", back_populates="documents")
    
    # File information
    filename = Column(String(255), nullable=False)  # sanitized filename for storage
    original_filename = Column(String(255), nullable=False)  # user's original filename
    file_path = Column(String(500), nullable=False)  # path to stored file
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, etc.
    file_size = Column(BigInteger, nullable=False)  # file size in bytes
    mime_type = Column(String(100), nullable=True)
    
    # Processing status
    status = Column(String(50), default='processing', nullable=False)  # 'processing', 'processed', 'error', 'indexed'
    processing_error = Column(Text, nullable=True)
    
    # Content information
    converted_content = Column(Text, nullable=True)  # markdown converted content
    word_count = Column(Integer, default=0, nullable=False)
    character_count = Column(Integer, default=0, nullable=False)
    
    # Vector information
    vector_count = Column(Integer, default=0, nullable=False)  # number of chunks/vectors created
    chunk_size = Column(Integer, default=1000, nullable=False)  # chunk size used for vectorization
    
    # Metadata extracted from document
    document_metadata = Column(JSON, nullable=True)  # language, entities, keywords, etc.
    
    # Processing timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "id": str(self.id),
            "collection_id": str(self.collection_id),
            "collection_name": self.collection.name if self.collection else None,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status,
            "processing_error": self.processing_error,
            "converted_content": self.converted_content,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "vector_count": self.vector_count,
            "chunk_size": self.chunk_size,
            "metadata": self.document_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted
        }

    def __repr__(self):
        return f"<RagDocument(id={self.id}, filename='{self.original_filename}', status='{self.status}')>"