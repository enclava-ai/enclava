"""
Base connector interface.

Every external-source connector must:
  1. Subclass BaseConnector.
  2. Implement load_credentials() to accept and store the credential dict.
  3. Implement validate() to verify the credentials/config are usable.
  4. Implement fetch_all() for a full re-index.
  5. Optionally override fetch_updated() for incremental sync (defaults to fetch_all).
  6. Optionally override build_checkpoint() / restore_checkpoint() if the connector
     needs to persist state across sync runs (e.g. pagination cursors).

Documents yielded by fetch_all / fetch_updated are plain ConnectorDocument
dataclasses.  The sync service converts them to RagDocument rows and hands the
text content to the existing RAG embedding pipeline.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Optional


@dataclass
class ConnectorDocument:
    """
    A document produced by a connector.

    Fields
    ------
    external_id:
        The source system's stable, unique identifier for this document
        (e.g. Notion page UUID, GitHub issue URL, Linear issue ID).
        Used for deduplication — if a document with this external_id already
        exists in the collection *and* external_updated_at has not advanced,
        the document is skipped.

    title:
        Human-readable title shown in search results.

    content:
        Plain-text (or Markdown) body of the document.  This is what gets
        chunked and embedded.

    url:
        Canonical link back to the original source (surfaced in search results).

    updated_at:
        Last-modified timestamp from the source system.  Used as the fast dedup
        gate — if unchanged, content hashing is skipped entirely.

    metadata:
        Arbitrary key→value pairs stored alongside the document (author, labels,
        project, etc.).  Surfaced in the Qdrant payload for potential filtering.

    file_type:
        Hint for the RAG processing pipeline (e.g. "md", "html", "txt").
        Defaults to "md".
    """

    external_id: str
    title: str
    content: str
    url: str
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    file_type: str = "md"


class BaseConnector(abc.ABC):
    """
    Abstract base class for all Enclava data-source connectors.

    Subclasses are instantiated by the sync service with:
        connector = MyConnector(config=<row.config>)
        connector.load_credentials(<decrypted credentials dict>)
        connector.validate()
        for batch in connector.fetch_all():
            ...
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Parameters
        ----------
        config:
            Connector-specific settings from ConnectorSource.config (plain JSON,
            no secrets).  Examples: root_page_id (Notion), repo_list (GitHub).
        """
        self.config = config

    @abc.abstractmethod
    def load_credentials(self, credentials: dict[str, Any]) -> None:
        """
        Receive decrypted credentials and store them on the instance.

        Called once by the sync service before validate() or fetch_*().
        The credentials dict shape is connector-specific (e.g.
        {"api_token": "secret_…"} for Notion).
        """

    @abc.abstractmethod
    def validate(self) -> None:
        """
        Verify that the stored credentials and config are valid.

        Should make a cheap API call (e.g. "get current user") and raise a
        descriptive exception if anything is wrong.  Raised exceptions are
        surfaced to the admin in the connector UI.
        """

    @abc.abstractmethod
    def fetch_all(self) -> Iterator[list[ConnectorDocument]]:
        """
        Yield batches of *all* documents available from the source.

        Used for the initial index and for periodic full re-syncs.
        Each yielded list is a batch (typically 50–100 documents) — the
        sync service processes batches incrementally so that a large source
        does not exhaust memory.
        """

    def fetch_updated(
        self,
        since: datetime,
        checkpoint: Optional[dict[str, Any]] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """
        Yield batches of documents updated *since* the given timestamp.

        The default implementation falls back to fetch_all(), which is correct
        but inefficient for large sources.  Connectors that support incremental
        queries (e.g. Linear's updatedAt_gt, Slack's oldest param) should
        override this.

        Parameters
        ----------
        since:
            Only return documents whose updated_at > since.
        checkpoint:
            Opaque state dict previously returned by build_checkpoint().
            May be None on the first run.
        """
        return self.fetch_all()

    def build_checkpoint(self) -> Optional[dict[str, Any]]:
        """
        Return an opaque JSON-serialisable dict representing the current sync
        position (e.g. a pagination cursor or the timestamp of the last document
        seen).

        The sync service persists this to ConnectorSource.checkpoint after each
        successful sync and passes it back via fetch_updated() on the next run.

        Return None if the connector does not need checkpoint state.
        """
        return None

    def restore_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """
        Restore internal state from a previously saved checkpoint dict.

        Called by the sync service before fetch_updated() when a non-None
        checkpoint exists.  The default is a no-op.
        """
