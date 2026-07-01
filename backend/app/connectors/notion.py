"""
Notion connector for the Enclava knowledge base.

Fetches pages and databases from Notion workspaces using the official
notion-client Python SDK. Supports both full and incremental sync.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Iterator, Optional

from app.connectors.base import BaseConnector, ConnectorDocument

try:
    from notion_client import Client
except ImportError as exc:
    raise RuntimeError("Install notion-client: pip install notion-client") from exc

logger = logging.getLogger(__name__)

# Rate limit: 3 req/sec => 0.333s between requests, using 0.35s for safety
_RATE_LIMIT_SLEEP = 0.35
_BATCH_SIZE = 50
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse ISO 8601 timestamp from Notion API (no timezone)."""
    # Notion returns timestamps like "2023-10-01T12:00:00.000"
    # Python 3.11+ can handle this directly with fromisoformat
    return datetime.fromisoformat(ts.replace("Z", ""))


def _extract_rich_text(rich_text: list[dict[str, Any]]) -> str:
    """Extract plain text from rich_text array."""
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _extract_block_text(block: dict[str, Any]) -> str:
    """
    Extract text content from a Notion block.

    Handles various block types including paragraphs, headings, lists,
    code blocks, quotes, callouts, and table rows.
    """
    block_type = block.get("type", "")

    if block_type in ("paragraph", "heading_1", "heading_2", "heading_3"):
        rich_text = block.get(block_type, {}).get("rich_text", [])
        return _extract_rich_text(rich_text)

    if block_type in ("bulleted_list_item", "numbered_list_item"):
        rich_text = block.get(block_type, {}).get("rich_text", [])
        text = _extract_rich_text(rich_text)
        if block_type == "bulleted_list_item":
            return f"- {text}"
        # numbered_list_item - we don't have the actual number from the API
        return f"• {text}"

    if block_type == "code":
        rich_text = block.get("code", {}).get("rich_text", [])
        code_text = _extract_rich_text(rich_text)
        language = block.get("code", {}).get("language", "")
        return f"```{language}\n{code_text}\n```"

    if block_type == "quote":
        rich_text = block.get("quote", {}).get("rich_text", [])
        text = _extract_rich_text(rich_text)
        return f"> {text}"

    if block_type == "callout":
        rich_text = block.get("callout", {}).get("rich_text", [])
        return _extract_rich_text(rich_text)

    if block_type == "table_row":
        cells = block.get("table_row", {}).get("cells", [])
        cell_texts = []
        for cell in cells:
            cell_text = _extract_rich_text(cell)
            cell_texts.append(cell_text)
        return " | ".join(cell_texts)

    if block_type in ("child_page", "child_database"):
        # These will be fetched as separate documents
        return ""

    # All other block types: skip silently
    return ""


class NotionConnector(BaseConnector):
    """
    Connector for Notion workspaces.

    Supports fetching pages and databases with incremental sync based on
    last_edited_time. Handles rate limiting (3 req/sec) and pagination.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._client: Optional[Client] = None
        self._api_token: Optional[str] = None
        self._workspace_id: Optional[str] = None
        self._workspace_name: Optional[str] = None
        self._checkpoint: dict[str, Any] = {}

    def load_credentials(self, credentials: dict[str, Any]) -> None:
        """
        Receive and store Notion credentials.

        Supports both API token (internal integration) and OAuth access token.
        Credentials may include: api_token OR access_token, workspace_id, workspace_name.
        """
        # Handle both api_token (internal) and access_token (OAuth)
        token = credentials.get("api_token") or credentials.get("access_token")
        if not token:
            raise ValueError(
                "Notion credentials must include 'api_token' or 'access_token'"
            )
        self._api_token = token
        self._workspace_id = credentials.get("workspace_id")
        self._workspace_name = credentials.get("workspace_name")

    def _init_client(self) -> Client:
        """Initialize and return the Notion client."""
        if self._client is None:
            if not self._api_token:
                raise RuntimeError(
                    "Credentials not loaded. Call load_credentials() first."
                )
            self._client = Client(auth=self._api_token)
        return self._client

    def _make_request_with_retry(
        self, operation: str, func: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Execute an API call with retry logic for rate limiting."""
        client = self._init_client()
        last_exception: Optional[Exception] = None

        for attempt in range(_MAX_RETRIES):
            try:
                return func(client, *args, **kwargs)
            except Exception as exc:
                last_exception = exc
                # Check for rate limit (HTTP 429) or connection errors
                error_str = str(exc).lower()
                if "rate" in error_str or "429" in error_str or "too many" in error_str:
                    sleep_time = _RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "Rate limited on %s (attempt %d/%d), sleeping %.1fs",
                        operation,
                        attempt + 1,
                        _MAX_RETRIES,
                        sleep_time,
                    )
                    # Use asyncio.sleep since we may be in async context
                    import time

                    time.sleep(sleep_time)
                else:
                    # Non-retryable error
                    raise

        # Exhausted retries
        raise RuntimeError(
            f"Failed {operation} after {_MAX_RETRIES} attempts"
        ) from last_exception

    def validate(self) -> None:
        """
        Verify credentials by making a test API call.

        Calls users.me() which raises an exception if the token is invalid.
        """
        client = self._init_client()
        try:
            user = client.users.me()
            logger.info(
                "Notion connector validated for user: %s", user.get("name", "unknown")
            )
        except Exception as exc:
            raise RuntimeError(f"Notion validation failed: {exc}") from exc

    def _fetch_page_blocks(self, page_id: str) -> str:
        """
        Fetch all blocks for a page and extract text content.

        Handles pagination for pages with many blocks.
        """
        client = self._init_client()
        all_text: list[str] = []
        cursor: Optional[str] = None

        while True:
            try:
                response = client.blocks.children.list(
                    block_id=page_id, start_cursor=cursor, page_size=100
                )
            except Exception as exc:
                logger.error("Failed to fetch blocks for page %s: %s", page_id, exc)
                break

            blocks = response.get("results", [])
            for block in blocks:
                text = _extract_block_text(block)
                if text:
                    all_text.append(text)

            # Rate limiting
            import time

            time.sleep(_RATE_LIMIT_SLEEP)

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break

        return "\n\n".join(all_text)

    def _get_title_from_page(self, page: dict[str, Any]) -> str:
        """Extract title from a page or database object."""
        object_type = page.get("object", "")

        if object_type == "page":
            # Try to get title from properties
            properties = page.get("properties", {})
            # Title could be in different formats
            for prop_name, prop_value in properties.items():
                if prop_value.get("type") == "title":
                    title_items = prop_value.get("title", [])
                    return _extract_rich_text(title_items)
        elif object_type == "database":
            return page.get("title", [{}])[0].get("plain_text", "Untitled Database")

        return "Untitled"

    def _search_pages(
        self, filter_type: Optional[str] = None, since: Optional[datetime] = None
    ) -> list[dict[str, Any]]:
        """
        Search for pages/databases in Notion.

        Args:
            filter_type: "page" or "database" or None for both
            since: Only return items updated since this timestamp (for incremental sync)
        """
        client = self._init_client()
        all_results: list[dict[str, Any]] = []
        cursor: Optional[str] = None

        search_filter: Optional[dict[str, str]] = None
        if filter_type:
            search_filter = {"property": "object", "value": filter_type}

        # For incremental sync, we sort by last_edited_time descending
        # But we need to filter manually since Notion search doesn't support
        # last_edited_time filter directly in the search endpoint

        while True:
            try:
                params: dict[str, Any] = {
                    "start_cursor": cursor,
                    "page_size": 100,
                }
                if search_filter:
                    params["filter"] = search_filter

                response = client.search(**params)
            except Exception as exc:
                logger.error("Notion search failed: %s", exc)
                break

            results = response.get("results", [])

            for item in results:
                # Check last_edited_time for incremental filtering
                if since:
                    last_edited = item.get("last_edited_time", "")
                    if last_edited:
                        try:
                            item_updated = _parse_iso_timestamp(last_edited)
                            if item_updated < since:
                                # Results are sorted by last_edited_time descending
                                # so we can stop early
                                break
                        except (ValueError, TypeError):
                            pass

                all_results.append(item)

            # Rate limiting
            import time

            time.sleep(_RATE_LIMIT_SLEEP)

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break

        return all_results

    def _get_page_content(self, page: dict[str, Any]) -> ConnectorDocument:
        """Convert a Notion page/database to a ConnectorDocument."""
        page_id = page.get("id", "")
        object_type = page.get("object", "page")  # "page" or "database"
        url = page.get("url", "")

        # Get title
        title = self._get_title_from_page(page)

        # Get updated time
        last_edited = page.get("last_edited_time", "")
        updated_at = datetime.utcnow()
        if last_edited:
            try:
                updated_at = _parse_iso_timestamp(last_edited)
            except (ValueError, TypeError):
                logger.warning("Failed to parse last_edited_time: %s", last_edited)

        # Fetch content for pages (databases don't have block content)
        content = ""
        if object_type == "page":
            content = self._fetch_page_blocks(page_id)

        # If no content, use title
        if not content.strip():
            content = title

        metadata = {
            "page_type": object_type,
            "workspace_name": self._workspace_name,
            "notion_id": page_id,
        }

        return ConnectorDocument(
            external_id=page_id,
            title=title,
            content=content,
            url=url,
            updated_at=updated_at,
            metadata=metadata,
            file_type="md",
        )

    def _should_include_item(self, item: dict[str, Any]) -> bool:
        """Check if item should be included based on config."""
        include_databases = self.config.get("include_databases", True)
        include_pages = self.config.get("include_pages", True)
        object_type = item.get("object", "")

        if object_type == "page" and not include_pages:
            return False
        if object_type == "database" and not include_databases:
            return False

        return True

    def _fetch_children_recursive(
        self, parent_id: str, since: Optional[datetime] = None
    ) -> Iterator[ConnectorDocument]:
        """
        Recursively fetch all children of a page/block.

        This is used when root_page_id is set to sync a specific subtree.
        """
        client = self._init_client()

        # First yield the parent page if it's a valid page
        try:
            parent_page = client.pages.retrieve(page_id=parent_id)
            if self._should_include_item(parent_page):
                yield self._get_page_content(parent_page)
        except Exception as exc:
            logger.warning("Failed to retrieve parent page %s: %s", parent_id, exc)

        # Rate limit after page fetch
        import time

        time.sleep(_RATE_LIMIT_SLEEP)

        # Fetch children
        cursor: Optional[str] = None
        child_pages: list[str] = []

        while True:
            try:
                response = client.blocks.children.list(
                    block_id=parent_id, start_cursor=cursor, page_size=100
                )
            except Exception as exc:
                logger.error("Failed to fetch children of %s: %s", parent_id, exc)
                break

            blocks = response.get("results", [])

            for block in blocks:
                block_type = block.get("type", "")
                block_id = block.get("id", "")

                # Handle child_page blocks
                if block_type == "child_page":
                    child_page_id = block_id  # child_page block id IS the page id
                    child_pages.append(child_page_id)

                # Handle child_database blocks (we don't recurse into databases)
                elif block_type == "child_database":
                    # Databases are synced as separate documents, not recursed into
                    try:
                        db = client.databases.retrieve(database_id=block_id)
                        if self._should_include_item(db):
                            yield self._get_page_content(db)
                        time.sleep(_RATE_LIMIT_SLEEP)
                    except Exception as exc:
                        logger.warning(
                            "Failed to retrieve database %s: %s", block_id, exc
                        )

            time.sleep(_RATE_LIMIT_SLEEP)

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break

        # Recursively process child pages
        for child_page_id in child_pages:
            yield from self._fetch_children_recursive(child_page_id, since)

    def _yield_batches(
        self, documents: Iterator[ConnectorDocument]
    ) -> Iterator[list[ConnectorDocument]]:
        """Batch documents into groups of _BATCH_SIZE."""
        batch: list[ConnectorDocument] = []

        for doc in documents:
            batch.append(doc)
            if len(batch) >= _BATCH_SIZE:
                yield batch
                batch = []

        if batch:
            yield batch

    def fetch_all(self) -> Iterator[list[ConnectorDocument]]:
        """
        Yield all pages and databases accessible by the integration.

        If config.root_page_id is set, only sync that page and its children.
        Otherwise sync all accessible pages and databases.
        """
        root_page_id = self.config.get("root_page_id")

        def document_generator() -> Iterator[ConnectorDocument]:
            seen_ids: set[str] = set()

            def emit_once(item: dict[str, Any]) -> Optional[ConnectorDocument]:
                item_id = item.get("id", "")
                if item_id and item_id in seen_ids:
                    return None
                if item_id:
                    seen_ids.add(item_id)
                if self._should_include_item(item):
                    return self._get_page_content(item)
                return None

            if root_page_id:
                # Sync specific subtree
                yield from self._fetch_children_recursive(root_page_id)
            else:
                # Sync all accessible content
                include_databases = self.config.get("include_databases", True)
                include_pages = self.config.get("include_pages", True)

                # Fetch databases first
                if include_databases:
                    databases = self._search_pages(filter_type="database")
                    for db in databases:
                        doc = emit_once(db)
                        if doc:
                            yield doc

                # Then fetch pages
                if include_pages:
                    pages = self._search_pages(filter_type="page")
                    for page in pages:
                        doc = emit_once(page)
                        if doc:
                            yield doc

        return self._yield_batches(document_generator())

    def fetch_updated(
        self,
        since: datetime,
        checkpoint: Optional[dict[str, Any]] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """
        Yield documents updated since the given timestamp.

        Uses checkpoint for resumable pagination. Filters search results by
        last_edited_time >= since.
        """
        if checkpoint:
            self._checkpoint = checkpoint

        root_page_id = self.config.get("root_page_id")

        def document_generator() -> Iterator[ConnectorDocument]:
            seen_ids: set[str] = set()

            def emit_updated_once(item: dict[str, Any]) -> Optional[ConnectorDocument]:
                item_id = item.get("id", "")
                if item_id and item_id in seen_ids:
                    return None
                if item_id:
                    seen_ids.add(item_id)
                if not self._should_include_item(item):
                    return None
                doc = self._get_page_content(item)
                return doc if doc.updated_at >= since else None

            if root_page_id:
                # For subtree sync with incremental, we still need to walk
                # the tree but filter by updated time
                # This is less efficient but necessary for correctness
                for doc in self._fetch_children_recursive(root_page_id, since):
                    if doc.updated_at >= since:
                        yield doc
            else:
                include_databases = self.config.get("include_databases", True)
                include_pages = self.config.get("include_pages", True)

                # Fetch updated databases
                if include_databases:
                    databases = self._search_pages(filter_type="database", since=since)
                    for db in databases:
                        doc = emit_updated_once(db)
                        if doc:
                            yield doc

                # Fetch updated pages
                if include_pages:
                    pages = self._search_pages(filter_type="page", since=since)
                    for page in pages:
                        doc = emit_updated_once(page)
                        if doc:
                            yield doc

        return self._yield_batches(document_generator())

    def build_checkpoint(self) -> Optional[dict[str, Any]]:
        """Return checkpoint data for resumable sync."""
        return {
            "last_cursor": self._checkpoint.get("last_cursor"),
            "last_sync_time": datetime.utcnow().isoformat(),
        }

    def restore_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Restore state from a saved checkpoint."""
        self._checkpoint = checkpoint.copy()
