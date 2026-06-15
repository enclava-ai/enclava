"""
Connector sync service.

Handles:
  - Credential encryption / decryption (Fernet, keyed from CONNECTOR_CREDENTIALS_KEY)
  - Running a full or incremental sync for a ConnectorSource
  - Persisting ConnectorSyncJob records
  - Deduplicating documents against existing RagDocument rows
  - Handing content to the RAG embedding pipeline
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector_source import (
    ConnectorSource,
    ConnectorSyncJob,
    ConnectorSyncStatus,
    ConnectorStatus,
)
from app.models.rag_document import RagDocument
from app.models.rag_collection import RagCollection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    """
    Return a Fernet instance keyed from CONNECTOR_CREDENTIALS_KEY.

    If the environment variable is not set, a deterministic key is derived
    from the JWT_SECRET so that existing deployments don't break on first
    start.  A warning is logged in that case — operators should set an
    explicit key in production.
    """
    raw_key = os.environ.get("CONNECTOR_CREDENTIALS_KEY")
    if raw_key:
        # Accept both raw 32-byte keys and already-base64url-encoded Fernet keys
        try:
            key = raw_key.encode() if isinstance(raw_key, str) else raw_key
            # Fernet expects URL-safe base64 encoded 32-byte key
            Fernet(key)  # validate
            return Fernet(key)
        except Exception:
            # Treat it as a passphrase and derive the key
            pass
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(raw_key.encode()).digest()
        )
        return Fernet(derived)

    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret:
        raise RuntimeError(
            "Neither CONNECTOR_CREDENTIALS_KEY nor JWT_SECRET is set. "
            "Cannot encrypt connector credentials."
        )
    logger.warning(
        "CONNECTOR_CREDENTIALS_KEY not set — deriving encryption key from "
        "JWT_SECRET.  Set CONNECTOR_CREDENTIALS_KEY in production."
    )
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(jwt_secret.encode()).digest()
    )
    return Fernet(derived)


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt a credentials dict to a base64 string for DB storage."""
    import json
    fernet = _get_fernet()
    plaintext = json.dumps(credentials).encode()
    return fernet.encrypt(plaintext).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt credentials from the stored base64 string."""
    import json
    fernet = _get_fernet()
    try:
        plaintext = fernet.decrypt(encrypted.encode())
        return json.loads(plaintext)
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt connector credentials — key mismatch?") from exc


# ---------------------------------------------------------------------------
# Sync execution
# ---------------------------------------------------------------------------

class ConnectorSyncService:
    """
    Orchestrates a single sync run for one ConnectorSource.

    Usage (called from the Celery task):

        service = ConnectorSyncService(db_session)
        await service.run_sync(connector_source_id)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_sync(self, connector_id: int) -> ConnectorSyncJob:
        """
        Execute a full-or-incremental sync for *connector_id*.

        Returns the completed ConnectorSyncJob row.
        """
        # Load connector row
        connector: Optional[ConnectorSource] = await self.db.get(
            ConnectorSource, connector_id
        )
        if connector is None:
            raise ValueError(f"ConnectorSource {connector_id} not found")
        if not connector.is_active:
            raise ValueError(f"ConnectorSource {connector_id} is not active")

        # Create a sync job record
        job = ConnectorSyncJob(
            connector_id=connector_id,
            status=ConnectorSyncStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        await self.db.flush()  # get job.id

        try:
            docs_indexed, docs_failed = await self._do_sync(connector, job)
            job.status = ConnectorSyncStatus.SUCCESS
            job.docs_indexed = docs_indexed
            job.docs_failed = docs_failed
            connector.status = ConnectorStatus.ACTIVE
            connector.last_sync_status = ConnectorSyncStatus.SUCCESS
            connector.last_sync_error = None
            connector.last_sync_docs_indexed = docs_indexed
            connector.last_sync_docs_failed = docs_failed
        except Exception as exc:
            logger.exception(
                "Sync failed for connector %d (%s): %s",
                connector_id,
                connector.connector_type,
                exc,
            )
            job.status = ConnectorSyncStatus.FAILED
            job.error_message = str(exc)
            connector.status = ConnectorStatus.ERROR
            connector.last_sync_status = ConnectorSyncStatus.FAILED
            connector.last_sync_error = str(exc)
        finally:
            job.finished_at = datetime.now(timezone.utc)
            connector.last_synced_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(job)

        return job

    async def _do_sync(
        self, connector: ConnectorSource, job: ConnectorSyncJob
    ) -> tuple[int, int]:
        """
        Core sync logic.  Returns (docs_indexed, docs_failed).
        """
        from app.connectors.registry import build_connector
        from app.models.connector_source import ConnectorType

        # Decrypt credentials
        credentials: dict[str, Any] = {}
        if connector.encrypted_credentials:
            credentials = decrypt_credentials(connector.encrypted_credentials)

        # Instantiate the connector implementation
        impl = build_connector(
            ConnectorType(connector.connector_type),
            config=connector.config or {},
            credentials=credentials,
        )

        # Decide full vs incremental
        is_incremental = (
            connector.last_synced_at is not None
            and connector.checkpoint is not None
        )

        if is_incremental and connector.checkpoint:
            impl.restore_checkpoint(connector.checkpoint)
            doc_iterator = impl.fetch_updated(
                since=connector.last_synced_at,  # type: ignore[arg-type]
                checkpoint=connector.checkpoint,
            )
        else:
            doc_iterator = impl.fetch_all()

        # Process batches
        docs_indexed = 0
        docs_failed = 0

        for batch in doc_iterator:
            for doc in batch:
                try:
                    indexed = await self._upsert_document(connector, doc)
                    if indexed:
                        docs_indexed += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to index document %s from connector %d: %s",
                        doc.external_id,
                        connector.id,
                        exc,
                    )
                    docs_failed += 1

        # Persist updated checkpoint
        new_checkpoint = impl.build_checkpoint()
        if new_checkpoint is not None:
            connector.checkpoint = new_checkpoint

        return docs_indexed, docs_failed

    async def _upsert_document(
        self, connector: ConnectorSource, doc: "ConnectorDocument"  # noqa: F821
    ) -> bool:
        """
        Insert or update a RagDocument for *doc*.

        Returns True if the document was actually (re-)indexed, False if it
        was skipped due to dedup.
        """
        from app.models.rag_collection import RagCollection

        # Dedup gate: look for an existing document with the same external_id
        # in this connector's collection
        stmt = select(RagDocument).where(
            RagDocument.connector_source_id == connector.id,
            RagDocument.external_id == doc.external_id,
            RagDocument.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        existing: Optional[RagDocument] = result.scalar_one_or_none()

        if existing is not None:
            # Skip if the external system hasn't changed the document
            if (
                existing.external_updated_at is not None
                and doc.updated_at <= existing.external_updated_at
            ):
                return False
            # Mark old vectors for replacement by deleting and re-creating below
            existing.is_deleted = True
            existing.deleted_at = datetime.now(timezone.utc)
            await self.db.flush()

        # Fetch the target Qdrant collection name
        collection: Optional[RagCollection] = await self.db.get(
            RagCollection, connector.collection_id
        )
        if collection is None:
            raise ValueError(
                f"Target collection {connector.collection_id} not found for connector {connector.id}"
            )

        # Encode content as UTF-8 bytes and hand it to the RAG pipeline
        content_bytes = doc.content.encode("utf-8")
        filename = f"{doc.external_id}.{doc.file_type}"

        # Process document into chunks / embeddings, then store in the target
        # Qdrant collection.
        from app.modules.rag.main import process_document as rag_process_document
        from app.modules.rag.main import index_processed_document as rag_index_document

        doc_metadata = {
            "title": doc.title,
            "source_url": doc.url,
            **{k: str(v) for k, v in doc.metadata.items()},
        }
        processed = await rag_process_document(
            file_data=content_bytes,
            filename=filename,
            metadata=doc_metadata,
        )

        chunk_count = 0
        if processed is not None:
            await rag_index_document(
                processed_doc=processed,
                collection_name=collection.qdrant_collection_name,
            )
            chunk_count = getattr(processed, "chunk_count", 0) or 0

        # Persist the RagDocument row with connector provenance
        rag_doc = RagDocument(
            collection_id=connector.collection_id,
            filename=filename,
            original_filename=doc.title or filename,
            file_path="",  # connector docs have no local file path
            file_type=doc.file_type,
            file_size=len(content_bytes),
            mime_type="text/markdown",
            source_url=doc.url,
            status="indexed",
            converted_content=doc.content,
            word_count=len(doc.content.split()),
            character_count=len(doc.content),
            vector_count=chunk_count,
            document_metadata=doc_metadata,
            connector_source_id=connector.id,
            external_id=doc.external_id,
            external_updated_at=doc.updated_at,
            indexed_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
        )
        self.db.add(rag_doc)
        await self.db.flush()
        return True


# ---------------------------------------------------------------------------
# Utility: index a connector document from the Qdrant collection directly
# (used by the RAG module integration in _upsert_document above)
# ---------------------------------------------------------------------------

async def index_connector_document(
    content: str,
    filename: str,
    metadata: dict[str, Any],
    qdrant_collection_name: str,
) -> dict[str, Any]:
    """
    Thin wrapper that delegates to the RAG module's process_document function
    and stores the result in the specified Qdrant collection.

    Returns a dict with at least {"chunk_count": int}.
    """
    from app.modules.rag.main import rag_module

    if not rag_module.enabled:
        raise RuntimeError("RAG module is not initialised")

    content_bytes = content.encode("utf-8")
    processed = await rag_module.process_document(
        file_data=content_bytes,
        filename=filename,
        metadata=metadata,
    )
    if processed:
        await rag_module.index_processed_document(
            processed_doc=processed,
            collection_name=qdrant_collection_name,
        )
        return {"chunk_count": getattr(processed, "chunk_count", 1)}
    return {"chunk_count": 0}
