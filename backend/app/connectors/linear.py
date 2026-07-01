"""
Linear connector for the Enclava knowledge base.

Fetches issues from Linear workspaces using the GraphQL API.
Supports both full and incremental sync with cursor-based pagination.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Iterator, Optional

import httpx
import requests

from app.connectors.base import BaseConnector, ConnectorDocument

logger = logging.getLogger(__name__)

_LINEAR_API_URL = "https://api.linear.app/graphql"
_RATE_LIMIT_SLEEP = 0.1  # 10 req/sec => 0.1s between requests
_BATCH_SIZE = 50
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


def _parse_iso_timestamp(ts: str) -> datetime:
    """Parse ISO 8601 timestamp from Linear API."""
    # Linear returns timestamps like "2023-10-01T12:00:00.000Z"
    # Remove Z and parse
    ts_clean = ts.replace("Z", "")
    return datetime.fromisoformat(ts_clean)


def _build_issue_content(issue: dict[str, Any]) -> str:
    """Build markdown content from a Linear issue."""
    identifier = issue.get("identifier", "")
    title = issue.get("title", "")
    description = issue.get("description") or ""
    state = issue.get("state", {})
    state_name = state.get("name", "Unknown")
    team = issue.get("team", {})
    team_name = team.get("name", "Unknown")
    raw_labels = issue.get("labels", {})
    labels = raw_labels.get("nodes", []) if isinstance(raw_labels, dict) else raw_labels
    label_names = [label.get("name", "") for label in labels]
    raw_comments = issue.get("comments", {})
    comments = (
        raw_comments.get("nodes", [])
        if isinstance(raw_comments, dict)
        else raw_comments or []
    )

    if not description and not comments:
        return title

    # Build content
    lines: list[str] = []

    # Header
    lines.append(f"# {identifier}: {title}")
    lines.append("")

    # Metadata
    lines.append(f"**State:** {state_name}")
    lines.append(f"**Team:** {team_name}")
    if label_names:
        lines.append(f"**Labels:** {', '.join(label_names)}")
    lines.append("")

    # Description
    lines.append("## Description")
    lines.append(description if description else "_No description provided_")
    lines.append("")

    # Comments
    if comments:
        lines.append("## Comments")
        for i, comment in enumerate(comments, 1):
            comment_body = comment.get("body", "")
            user = comment.get("user") or {}
            user_name = user.get("name")
            heading = f"### Comment {i}"
            if user_name:
                heading += f" by {user_name}"
            lines.append(heading)
            lines.append(comment_body)
            lines.append("")

    return "\n".join(lines)


def _make_graphql_request(
    client: httpx.Client,
    query: str,
    variables: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """Make a GraphQL request to Linear with retry logic."""
    last_exception: Optional[Exception] = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.post(
                _LINEAR_API_URL,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
                json={"query": query, "variables": variables},
                timeout=30.0,
            )

            if response.status_code == 429:
                # Rate limited
                sleep_time = _RETRY_DELAY * (2**attempt)
                logger.warning(
                    "Rate limited (attempt %d/%d), sleeping %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    sleep_time,
                )
                time.sleep(sleep_time)
                continue

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = str(data["errors"])
                raise RuntimeError(f"Linear GraphQL error: {error_msg}")

            return data.get("data", {})

        except httpx.HTTPStatusError as exc:
            last_exception = exc
            if exc.response.status_code == 429:
                sleep_time = _RETRY_DELAY * (2**attempt)
                logger.warning(
                    "HTTP 429 rate limited (attempt %d/%d), sleeping %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    sleep_time,
                )
                time.sleep(sleep_time)
                continue
            raise

        except Exception as exc:
            last_exception = exc
            if attempt < _MAX_RETRIES - 1:
                sleep_time = _RETRY_DELAY * (2**attempt)
                logger.warning(
                    "Request failed (attempt %d/%d): %s, retrying...",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                )
                time.sleep(sleep_time)
                continue
            raise

    # Exhausted retries
    raise RuntimeError(
        f"Failed GraphQL request after {_MAX_RETRIES} attempts"
    ) from last_exception


class LinearConnector(BaseConnector):
    """
    Connector for Linear workspaces.

    Fetches issues using the GraphQL API with cursor-based pagination.
    Supports incremental sync via updatedAt filtering.
    """

    # GraphQL queries
    _VALIDATE_QUERY = """
        query {
            viewer {
                id
                name
            }
        }
    """

    _ISSUES_QUERY = """
        query Issues($first: Int, $after: String, $filter: IssueFilter) {
            issues(first: $first, after: $after, filter: $filter) {
                nodes {
                    id
                    identifier
                    title
                    description
                    url
                    updatedAt
                    createdAt
                    state {
                        name
                    }
                    team {
                        name
                    }
                    labels {
                        nodes {
                            name
                        }
                    }
                    comments {
                        nodes {
                            body
                            updatedAt
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    """

    _UPDATED_ISSUES_QUERY = """
        query UpdatedIssues($since: DateTimeComparator!) {
            issues(filter: { updatedAt: $since }, first: 100) {
                nodes {
                    id
                    identifier
                    title
                    description
                    url
                    updatedAt
                    createdAt
                    state {
                        name
                    }
                    team {
                        name
                    }
                    labels {
                        nodes {
                            name
                        }
                    }
                    comments {
                        nodes {
                            body
                            updatedAt
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._client: Optional[httpx.Client] = None
        self._api_key: Optional[str] = None
        self._checkpoint: dict[str, Any] = {}
        self._last_issue_id: Optional[str] = None
        self._cursor: Optional[str] = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client()
        return self._client

    def load_credentials(self, credentials: dict[str, Any]) -> None:
        """Receive and store Linear API credentials."""
        api_key = credentials.get("api_key")
        if not api_key:
            raise ValueError("Linear credentials must include 'api_key'")
        self._api_key = api_key

    def validate(self) -> None:
        """Verify credentials by calling the viewer query."""
        if not self._api_key:
            raise RuntimeError("Credentials not loaded. Call load_credentials() first.")

        try:
            payload = self._make_graphql_request(self._VALIDATE_QUERY, {})
            if "errors" in payload:
                raise RuntimeError(payload["errors"])
            data = payload.get("data", payload)
            viewer = data.get("viewer", {})
            if not viewer:
                raise RuntimeError("viewer missing from Linear response")
            viewer_name = viewer.get("name", "unknown")
            logger.info("Linear connector validated for user: %s", viewer_name)
        except Exception as exc:
            raise RuntimeError(f"Linear validation failed: {exc}") from exc
        finally:
            # Close client after validation to avoid leaving connections open
            if self._client:
                self._client.close()
                self._client = None

    def _make_graphql_request(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Legacy instance wrapper for Linear GraphQL requests."""
        if not self._api_key:
            raise RuntimeError("Credentials not loaded. Call load_credentials() first.")

        try:
            response = requests.post(
                _LINEAR_API_URL,
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
                json={"query": query, "variables": variables or {}},
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            if "errors" in payload:
                raise RuntimeError(payload["errors"])
            return payload
        except Exception as exc:
            raise RuntimeError(f"Linear GraphQL request failed: {exc}") from exc

    def _build_issue_filter(self) -> Optional[dict[str, Any]]:
        """Build the filter for issues based on config."""
        include_completed = self.config.get("include_completed", True)
        include_cancelled = self.config.get("include_cancelled", False)
        team_ids = self.config.get("team_ids", [])

        filter_dict: dict[str, Any] = {}

        # Team filter
        if team_ids:
            if len(team_ids) == 1:
                filter_dict["team"] = {"id": {"eq": team_ids[0]}}
            else:
                filter_dict["team"] = {"id": {"in": team_ids}}

        # State filter (completed/cancelled)
        state_filter: dict[str, Any] = {}
        if not include_completed:
            state_filter["type"] = {"neq": "completed"}
        if not include_cancelled:
            if "type" not in state_filter:
                state_filter["type"] = {}
            state_filter["type"]["neq"] = "canceled"

        if state_filter:
            filter_dict["state"] = state_filter

        return filter_dict if filter_dict else None

    def _issue_to_document(self, issue: dict[str, Any]) -> ConnectorDocument:
        """Convert a Linear issue to a ConnectorDocument."""
        issue_id = issue.get("id", "")
        identifier = issue.get("identifier", "")
        title = issue.get("title", "")
        url = issue.get("url", "")
        updated_at_str = issue.get("updatedAt", "")
        state = issue.get("state", {})
        state_name = state.get("name", "")
        team = issue.get("team", {})
        team_name = team.get("name", "")
        raw_labels = issue.get("labels", {})
        labels = (
            raw_labels.get("nodes", []) if isinstance(raw_labels, dict) else raw_labels
        )
        label_names = [label.get("name", "") for label in labels]
        assignee = issue.get("assignee") or {}

        # Parse updated_at
        updated_at = datetime.utcnow()
        if updated_at_str:
            try:
                updated_at = _parse_iso_timestamp(updated_at_str)
            except (ValueError, TypeError):
                logger.warning("Failed to parse updatedAt: %s", updated_at_str)

        # Build content
        content = _build_issue_content(issue)

        # If no content, use title
        if not content.strip():
            content = title

        metadata = {
            "identifier": identifier,
            "state": state_name,
            "team": team_name,
            "labels": label_names,
            "assignee": assignee.get("name") if isinstance(assignee, dict) else None,
            "priority": issue.get("priority"),
        }

        return ConnectorDocument(
            external_id=issue_id,
            title=f"{identifier}: {title}",
            content=content,
            url=url,
            updated_at=updated_at,
            metadata=metadata,
            file_type="md",
        )

    def _fetch_issues(
        self, since: Optional[datetime] = None
    ) -> Iterator[dict[str, Any]]:
        """Fetch raw Linear issues with pagination."""
        if not self._api_key:
            raise RuntimeError("Credentials not loaded. Call load_credentials() first.")

        cursor: Optional[str] = None
        issue_filter = self._build_issue_filter()
        if since is not None:
            issue_filter = issue_filter or {}
            issue_filter["updatedAt"] = {"gte": since.isoformat()}

        while True:
            variables: dict[str, Any] = {
                "first": 100,
                "after": cursor,
            }
            if issue_filter:
                variables["filter"] = issue_filter

            try:
                payload = self._make_graphql_request(self._ISSUES_QUERY, variables)
                data = payload.get("data", payload)
            except Exception as exc:
                logger.error("Failed to fetch issues: %s", exc)
                break

            issues_data = data.get("issues", {})
            issues = issues_data.get("nodes", [])
            page_info = issues_data.get("pageInfo", {})

            for issue in issues:
                self._last_issue_id = issue.get("id")
                yield issue

            # Rate limiting
            time.sleep(_RATE_LIMIT_SLEEP)

            has_more = page_info.get("hasNextPage", False)
            if not has_more:
                break

            cursor = page_info.get("endCursor")
            self._cursor = cursor
            if not cursor:
                break

    def _fetch_all_issues(self) -> Iterator[ConnectorDocument]:
        """Fetch all issues with pagination."""
        for issue in self._fetch_issues():
            yield self._issue_to_document(issue)

    def _fetch_updated_issues(self, since: datetime) -> Iterator[ConnectorDocument]:
        """Fetch issues updated since the given timestamp."""
        if not self._api_key:
            raise RuntimeError("Credentials not loaded. Call load_credentials() first.")

        for issue in self._fetch_issues(since=since):
            doc = self._issue_to_document(issue)
            if doc.updated_at >= since:
                yield doc

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
        """Yield all issues accessible by the API key."""
        return self._yield_batches(self._fetch_all_issues())

    def fetch_updated(
        self,
        since: datetime,
        checkpoint: Optional[dict[str, Any]] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """
        Yield issues updated since the given timestamp.

        Uses checkpoint for resumable pagination.
        """
        if checkpoint:
            self._checkpoint = checkpoint

        return self._yield_batches(self._fetch_updated_issues(since))

    def build_checkpoint(self) -> Optional[dict[str, Any]]:
        """Return checkpoint data for resumable sync."""
        return {
            "last_cursor": self._checkpoint.get("last_cursor"),
            "last_issue_id": self._last_issue_id,
            "cursor": self._cursor,
            "last_sync_time": datetime.utcnow().isoformat(),
        }

    def restore_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Restore state from a saved checkpoint."""
        self._checkpoint = checkpoint.copy()
        self._last_issue_id = checkpoint.get("last_issue_id")
        self._cursor = checkpoint.get("cursor")

    def __del__(self):
        """Cleanup resources."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
