"""
ConnectorSource model
Represents an external data source connector (Notion, Slack, GitHub, Linear, …)
that periodically syncs documents into a RAG collection.
"""

from enum import Enum

from sqlalchemy import (
    JSON,
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


class ConnectorType(str, Enum):
    NOTION = "notion"
    SLACK = "slack"
    GITHUB = "github"
    LINEAR = "linear"
    GOOGLE_DRIVE = "google_drive"
    GOOGLE_DOCS = "google_docs"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    # Extend as new connectors are added


class ConnectorStatus(str, Enum):
    ACTIVE = "active"  # syncing normally
    PAUSED = "paused"  # manually paused
    ERROR = "error"  # last sync failed
    PENDING = "pending"  # created, never synced yet


class ConnectorSyncStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ConnectorSource(Base):
    """
    One row per connected external source.

    Credentials are stored as Fernet-encrypted JSON so that raw tokens never
    appear in the database in plaintext.
    """

    __tablename__ = "connector_sources"

    id = Column(Integer, primary_key=True, index=True)

    # Human-readable label set by the admin (e.g. "Engineering Notion workspace")
    name = Column(String(255), nullable=False)

    # ConnectorType enum stored as string
    connector_type = Column(String(50), nullable=False, index=True)

    # The RAG collection that synced documents land in
    collection_id = Column(
        Integer,
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Connector-specific settings (e.g. root_page_id for Notion, repo list for GitHub)
    # Stored as plain JSON — must NOT contain secrets
    config = Column(JSON, nullable=False, default=dict)

    # Fernet-encrypted JSON blob containing API tokens / OAuth tokens
    # Encrypted with the application's CONNECTOR_CREDENTIALS_KEY env var
    encrypted_credentials = Column(Text, nullable=True)

    # Sync scheduling
    # ISO 8601 duration string, e.g. "PT30M" (every 30 min), "PT1H", "P1D"
    sync_frequency = Column(String(20), nullable=False, default="PT1H")

    # Status
    status = Column(String(20), nullable=False, default=ConnectorStatus.PENDING)

    # Last sync tracking
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(20), nullable=True)  # ConnectorSyncStatus value
    last_sync_error = Column(Text, nullable=True)
    last_sync_docs_indexed = Column(Integer, nullable=True)
    last_sync_docs_failed = Column(Integer, nullable=True)

    # Incremental sync: opaque JSON blob stored by the connector (e.g. cursor, last_edit_time)
    checkpoint = Column(JSON, nullable=True)

    # Ownership — who created this connector
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_active = Column(Boolean, nullable=False, default=True)

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
    collection = relationship("RagCollection", back_populates="connector_sources")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    sync_jobs = relationship(
        "ConnectorSyncJob", back_populates="connector", cascade="all, delete-orphan"
    )

    def to_dict(self, include_credentials: bool = False) -> dict:
        """Serialize to dict. Credentials are never included by default."""
        d = {
            "id": self.id,
            "name": self.name,
            "connector_type": self.connector_type,
            "collection_id": self.collection_id,
            "config": self.config,
            "sync_frequency": self.sync_frequency,
            "status": self.status,
            "last_synced_at": (
                self.last_synced_at.isoformat() if self.last_synced_at else None
            ),
            "last_sync_status": self.last_sync_status,
            "last_sync_error": self.last_sync_error,
            "last_sync_docs_indexed": self.last_sync_docs_indexed,
            "last_sync_docs_failed": self.last_sync_docs_failed,
            "created_by_user_id": self.created_by_user_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_credentials:
            d["encrypted_credentials"] = self.encrypted_credentials
        return d

    def __repr__(self) -> str:
        return (
            f"<ConnectorSource(id={self.id}, type='{self.connector_type}', "
            f"name='{self.name}', status='{self.status}')>"
        )


class ConnectorSyncJob(Base):
    """
    One row per sync run.  Provides a history of past syncs for the UI.
    """

    __tablename__ = "connector_sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    connector_id = Column(
        Integer,
        ForeignKey("connector_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(String(20), nullable=False, default=ConnectorSyncStatus.IDLE)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    docs_indexed = Column(Integer, nullable=False, default=0)
    docs_failed = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    connector = relationship("ConnectorSource", back_populates="sync_jobs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connector_id": self.connector_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "docs_indexed": self.docs_indexed,
            "docs_failed": self.docs_failed,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<ConnectorSyncJob(id={self.id}, connector_id={self.connector_id}, "
            f"status='{self.status}')>"
        )
