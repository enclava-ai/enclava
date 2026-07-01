"""
RAG Collection Model
Represents document collections for the RAG system
"""

from enum import Enum

from sqlalchemy import (
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


class CollectionVisibility(str, Enum):
    """Who can search/read documents in this collection."""

    PRIVATE = "private"  # owner + admins only
    TEAM = "team"  # all authenticated users (default, matches legacy behaviour)
    ROLE_REQUIRED = "role_required"  # users whose role.level >= allowed_role_level
    PUBLIC = "public"  # anyone, including unauthenticated API callers


class RagCollection(Base):
    __tablename__ = "rag_collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    qdrant_collection_name = Column(
        String(255), nullable=False, unique=True, index=True
    )

    # Ownership & access control
    owner_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # CollectionVisibility value stored as string; default 'team' preserves existing behaviour
    visibility = Column(String(20), nullable=False, default=CollectionVisibility.TEAM)
    # Minimum role level required when visibility == 'role_required'
    # Valid values mirror RoleLevel: 'read_only', 'user', 'admin', 'super_admin'
    allowed_role_level = Column(String(20), nullable=True)

    # Metadata
    document_count = Column(Integer, default=0, nullable=False)
    size_bytes = Column(BigInteger, default=0, nullable=False)
    vector_count = Column(Integer, default=0, nullable=False)

    # Status tracking
    status = Column(
        String(50), default="active", nullable=False
    )  # 'active', 'indexing', 'error'
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owner = relationship("User", foreign_keys=[owner_user_id])
    documents = relationship(
        "RagDocument", back_populates="collection", cascade="all, delete-orphan"
    )
    connector_sources = relationship(
        "ConnectorSource", back_populates="collection", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        if "user_id" in kwargs and "owner_user_id" not in kwargs:
            kwargs["owner_user_id"] = kwargs.pop("user_id")
        legacy_fields = {
            "embedding_model": kwargs.pop("embedding_model", None),
            "chunk_size": kwargs.pop("chunk_size", None),
            "chunk_overlap": kwargs.pop("chunk_overlap", None),
        }
        super().__init__(**kwargs)
        for key, value in legacy_fields.items():
            if value is not None:
                setattr(self, f"_{key}", value)

    @property
    def user_id(self):
        return self.owner_user_id

    @user_id.setter
    def user_id(self, value):
        self.owner_user_id = value

    @property
    def embedding_model(self):
        return getattr(self, "_embedding_model", None)

    @embedding_model.setter
    def embedding_model(self, value):
        self._embedding_model = value

    @property
    def chunk_size(self):
        return getattr(self, "_chunk_size", None)

    @chunk_size.setter
    def chunk_size(self, value):
        self._chunk_size = value

    @property
    def chunk_overlap(self):
        return getattr(self, "_chunk_overlap", None)

    @chunk_overlap.setter
    def chunk_overlap(self, value):
        self._chunk_overlap = value

    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description or "",
            "owner_user_id": self.owner_user_id,
            "visibility": self.visibility,
            "allowed_role_level": self.allowed_role_level,
            "document_count": self.document_count,
            "size_bytes": self.size_bytes,
            "vector_count": self.vector_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<RagCollection(id={self.id}, name='{self.name}', documents={self.document_count})>"
