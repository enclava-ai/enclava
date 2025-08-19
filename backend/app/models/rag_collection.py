"""
RAG Collection Model
Represents document collections for the RAG system
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class RagCollection(Base):
    __tablename__ = "rag_collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    qdrant_collection_name = Column(String(255), nullable=False, unique=True, index=True)
    
    # Metadata
    document_count = Column(Integer, default=0, nullable=False)
    size_bytes = Column(BigInteger, default=0, nullable=False)
    vector_count = Column(Integer, default=0, nullable=False)
    
    # Status tracking
    status = Column(String(50), default='active', nullable=False)  # 'active', 'indexing', 'error'
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    documents = relationship("RagDocument", back_populates="collection", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description or "",
            "document_count": self.document_count,
            "size_bytes": self.size_bytes,
            "vector_count": self.vector_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active
        }

    def __repr__(self):
        return f"<RagCollection(id={self.id}, name='{self.name}', documents={self.document_count})>"