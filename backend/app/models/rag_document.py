"""
RAG Document Model
Represents documents within RAG collections
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)

    # Collection relationship
    collection_id = Column(
        Integer,
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection = relationship("RagCollection", back_populates="documents")

    # File information
    filename = Column(String(255), nullable=False)  # sanitized filename for storage
    original_filename = Column(String(255), nullable=False)  # user's original filename
    file_path = Column(String(500), nullable=False)  # path to stored file
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, etc.
    file_size = Column(BigInteger, nullable=False)  # file size in bytes
    mime_type = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True, index=True)  # original source URL

    # Processing status
    status = Column(
        String(50), default="processing", nullable=False
    )  # 'processing', 'processed', 'error', 'indexed'
    processing_error = Column(Text, nullable=True)

    # Content information
    converted_content = Column(Text, nullable=True)  # markdown converted content
    word_count = Column(Integer, default=0, nullable=False)
    character_count = Column(Integer, default=0, nullable=False)

    # Vector information
    vector_count = Column(
        Integer, default=0, nullable=False
    )  # number of chunks/vectors created
    chunk_size = Column(
        Integer, default=1000, nullable=False
    )  # chunk size used for vectorization

    # Metadata extracted from document
    document_metadata = Column(
        JSON, nullable=True
    )  # language, entities, keywords, etc.

    # Processing timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Connector provenance — set when a document was ingested via a ConnectorSource
    connector_source_id = Column(
        Integer,
        ForeignKey("connector_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # The external system's stable identifier (e.g. Notion page UUID, GitHub issue number)
    external_id = Column(String(512), nullable=True, index=True)
    # The last-modified timestamp from the external system; used for dedup
    external_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    connector_source = relationship(
        "ConnectorSource", foreign_keys=[connector_source_id]
    )

    def __init__(self, **kwargs):
        if "size" in kwargs and "file_size" not in kwargs:
            kwargs["file_size"] = kwargs.pop("size")
        if "content" in kwargs and "converted_content" not in kwargs:
            kwargs["converted_content"] = kwargs.pop("content")
        if "metadata" in kwargs and "document_metadata" not in kwargs:
            kwargs["document_metadata"] = kwargs.pop("metadata")
        if "embedding_status" in kwargs:
            embedding_status = kwargs.pop("embedding_status")
            kwargs.setdefault(
                "status",
                {
                    "completed": "indexed",
                    "failed": "error",
                }.get(embedding_status, embedding_status),
            )
            kwargs["_legacy_embedding_status"] = embedding_status
        if "chunk_count" in kwargs and "vector_count" not in kwargs:
            kwargs["vector_count"] = kwargs.pop("chunk_count")
        if "error_message" in kwargs and "processing_error" not in kwargs:
            kwargs["processing_error"] = kwargs.pop("error_message")
        kwargs.setdefault("original_filename", kwargs.get("filename", ""))
        kwargs.setdefault("file_path", kwargs.get("filename", ""))
        kwargs.setdefault(
            "file_type",
            (
                kwargs.get("filename", "").rsplit(".", 1)[-1]
                if "." in kwargs.get("filename", "")
                else "txt"
            ),
        )
        kwargs.setdefault("file_size", len(kwargs.get("converted_content") or ""))
        legacy_status = kwargs.pop("_legacy_embedding_status", None)
        super().__init__(**kwargs)
        if legacy_status is not None:
            self._legacy_embedding_status = legacy_status

    @property
    def size(self):
        return self.file_size

    @size.setter
    def size(self, value):
        self.file_size = value

    @property
    def content(self):
        return self.converted_content

    @content.setter
    def content(self, value):
        self.converted_content = value

    @property
    def embedding_status(self):
        if hasattr(self, "_legacy_embedding_status"):
            return self._legacy_embedding_status
        return {
            "indexed": "completed",
            "processed": "completed",
            "error": "failed",
        }.get(self.status, self.status)

    @embedding_status.setter
    def embedding_status(self, value):
        self._legacy_embedding_status = value
        self.status = {
            "completed": "indexed",
            "failed": "error",
        }.get(value, value)

    @property
    def chunk_count(self):
        return self.vector_count

    @chunk_count.setter
    def chunk_count(self, value):
        self.vector_count = value

    @property
    def error_message(self):
        return self.processing_error

    @error_message.setter
    def error_message(self, value):
        self.processing_error = value

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
            "source_url": self.source_url,
            "status": self.status,
            "processing_error": self.processing_error,
            "converted_content": self.converted_content,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "vector_count": self.vector_count,
            "chunk_size": self.chunk_size,
            "metadata": self.document_metadata or {},
            "connector_source_id": self.connector_source_id,
            "external_id": self.external_id,
            "external_updated_at": (
                self.external_updated_at.isoformat()
                if self.external_updated_at
                else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self):
        return f"<RagDocument(id={self.id}, filename='{self.original_filename}', status='{self.status}')>"
