"""
Slack connector.

Syncs channel messages from Slack workspaces into Enclava RAG collections
using the official slack-sdk library.

Install dependency:
    pip install slack-sdk
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    raise RuntimeError("Install slack-sdk: pip install slack-sdk")

from app.connectors.base import BaseConnector, ConnectorDocument

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50

# Default config values
_DEFAULTS: dict[str, Any] = {
    "channel_ids": [],
    "include_threads": True,
    "message_limit": 10000,
    "channel_types": "public_channel,private_channel",
}


def _cfg(config: dict[str, Any], key: str) -> Any:
    """Return config[key] with fallback to _DEFAULTS."""
    return config.get(key, _DEFAULTS[key])


def _ts_to_datetime(ts: str) -> datetime:
    """Convert a Slack timestamp string (e.g. '1705312200.123456') to a datetime."""
    return datetime.utcfromtimestamp(float(ts))


def _ts_to_time_str(ts: str) -> str:
    """Format a Slack timestamp as a human-readable HH:MM AM/PM string."""
    dt = _ts_to_datetime(ts)
    return dt.strftime("%I:%M %p").lstrip("0")


def _ts_to_date_str(ts: str) -> str:
    """Return the calendar-date portion (YYYY-MM-DD) of a Slack timestamp."""
    return _ts_to_datetime(ts).strftime("%Y-%m-%d")


class SlackConnector(BaseConnector):
    """
    Connector for Slack workspaces.

    Credential schema (one of):
        {"bot_token":     "xoxb-..."}
        {"access_token":  "xoxb-..."}

    Config schema (all optional, shown with defaults):
        {
            "channel_ids":    [],                              # specific channel IDs; empty = all
            "include_threads": True,
            "message_limit":  10000,                           # max messages per channel
            "channel_types":  "public_channel,private_channel",
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._token: Optional[str] = None
        self._bot_token: Optional[str] = None
        self._client: Optional[WebClient] = None
        self._workspace_id: Optional[str] = None
        self._user_cache: dict[str, str] = {}
        self._last_message_ts: Optional[str] = None
        self._processed_channels: list[str] = []

    # ------------------------------------------------------------------
    # Credential loading
    # ------------------------------------------------------------------

    def load_credentials(self, credentials: dict[str, Any]) -> None:
        """Accept ``bot_token`` or ``access_token`` key."""
        token = credentials.get("bot_token") or credentials.get("access_token")
        if not token:
            raise ValueError(
                "Slack credentials must contain 'bot_token' or 'access_token'."
            )
        self._token = token
        self._bot_token = token
        self._client = WebClient(token=token)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Verify credentials via auth.test and cache the workspace/team ID."""
        if self._client is None:
            raise RuntimeError("call load_credentials() before validate().")
        try:
            response = self._client.auth_test()
            if not response.get("ok", True):
                raise RuntimeError(response.get("error", "unknown_error"))
            self._workspace_id = response.get("team_id")
            logger.info(
                "Slack connector validated. Team: %s (%s), Bot user: %s",
                response.get("team"),
                self._workspace_id,
                response.get("user"),
            )
        except SlackApiError as exc:
            error = exc.response.get("error", str(exc))
            raise RuntimeError(f"Slack validation failed: {error}") from exc
        except Exception as exc:
            raise RuntimeError(f"Slack validation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Rate-limit helper
    # ------------------------------------------------------------------

    def _call_with_retry(self, api_func: Any, **kwargs: Any) -> Any:
        """
        Call a Slack SDK API method, retrying once on ``ratelimited`` errors.

        The ``Retry-After`` header value (seconds) is respected when sleeping.
        """
        try:
            response = api_func(**kwargs)
            if self._is_rate_limited_response(response):
                retry_after = self._retry_after_seconds(response)
                logger.warning(
                    "Slack rate limit hit. Sleeping %d seconds (Retry-After).",
                    retry_after,
                )
                time.sleep(retry_after)
                return api_func(**kwargs)
            return response
        except SlackApiError as exc:
            if exc.response.get("error") == "ratelimited":
                retry_after = int(exc.response.headers.get("Retry-After", 30))
                logger.warning(
                    "Slack rate limit hit. Sleeping %d seconds (Retry-After).",
                    retry_after,
                )
                time.sleep(retry_after)
                return api_func(**kwargs)
            raise

    def _is_rate_limited_response(self, response: Any) -> bool:
        if isinstance(response, dict):
            return (
                response.get("ok") is False and response.get("error") == "ratelimited"
            )
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            return data.get("error") == "ratelimited"
        return (
            getattr(response, "ok", True) is False
            and getattr(response, "error", None) == "ratelimited"
        )

    def _retry_after_seconds(self, response: Any) -> int:
        if isinstance(response, dict):
            return int(response.get("retry_after") or response.get("Retry-After") or 1)
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            return int(data.get("retry_after") or data.get("Retry-After") or 1)
        return int(getattr(response, "retry_after", 1) or 1)

    # ------------------------------------------------------------------
    # User display-name helper
    # ------------------------------------------------------------------

    def _get_display_name(self, user_id: str) -> str:
        """
        Return the human-readable display name for a Slack user ID.

        Results are cached in ``_user_cache`` to avoid redundant API calls.
        Falls back to ``display_name``, then the raw ``user_id``.
        """
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        assert self._client is not None
        try:
            resp = self._call_with_retry(self._client.users_info, user=user_id)
            profile: dict[str, Any] = resp.get("user", {}).get("profile", {})
            name: str = (
                profile.get("real_name") or profile.get("display_name") or user_id
            )
        except SlackApiError as exc:
            logger.debug("Could not fetch user info for %s: %s", user_id, exc)
            name = user_id

        self._user_cache[user_id] = name
        return name

    # ------------------------------------------------------------------
    # Channel listing
    # ------------------------------------------------------------------

    def _list_channels(self) -> list[dict[str, Any]]:
        """
        Return all channels the bot is a member of, optionally filtered by
        ``config["channel_ids"]``.
        """
        assert self._client is not None
        channel_types: str = _cfg(self.config, "channel_types")
        channels: list[dict[str, Any]] = []
        cursor: Optional[str] = None

        allowed_ids: list[str] = _cfg(self.config, "channel_ids")
        if allowed_ids:
            for channel_id in allowed_ids:
                try:
                    resp = self._call_with_retry(
                        self._client.conversations_info, channel=channel_id
                    )
                    if isinstance(resp, dict):
                        channel = dict(resp.get("channel") or {})
                    else:
                        channel = {}
                    channel.setdefault("id", channel_id)
                    channel.setdefault("name", channel_id)
                    channels.append(channel)
                except Exception as exc:
                    logger.warning(
                        "Error fetching Slack channel %s: %s", channel_id, exc
                    )
            return channels

        while True:
            kwargs: dict[str, Any] = {
                "types": channel_types,
                "limit": 200,
                "exclude_archived": True,
            }
            if cursor:
                kwargs["cursor"] = cursor

            try:
                resp = self._call_with_retry(self._client.conversations_list, **kwargs)
            except SlackApiError as exc:
                logger.warning("Error listing Slack channels: %s", exc)
                break

            if not isinstance(resp, dict):
                break

            channels.extend(resp.get("channels", []))
            next_cursor: str = (
                resp.get("response_metadata", {}).get("next_cursor", "") or ""
            )
            if not next_cursor:
                break
            cursor = next_cursor
        return channels

    # ------------------------------------------------------------------
    # Message fetching
    # ------------------------------------------------------------------

    def _fetch_channel_messages(
        self,
        channel_id: str,
        oldest: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch messages from *channel_id*, up to ``config["message_limit"]``.

        *oldest* is a Slack timestamp string used for incremental sync.
        """
        assert self._client is not None
        message_limit: int = _cfg(self.config, "message_limit")
        messages: list[dict[str, Any]] = []
        cursor: Optional[str] = None
        page_size = min(200, message_limit)

        while len(messages) < message_limit:
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "limit": page_size,
            }
            if oldest:
                kwargs["oldest"] = oldest
            if cursor:
                kwargs["cursor"] = cursor

            try:
                resp = self._call_with_retry(
                    self._client.conversations_history, **kwargs
                )
            except SlackApiError as exc:
                logger.warning(
                    "Error fetching history for channel %s: %s", channel_id, exc
                )
                break

            page_messages: list[dict[str, Any]] = resp.get("messages", [])
            messages.extend(page_messages)

            if not resp.get("has_more"):
                break
            next_cursor: str = (
                resp.get("response_metadata", {}).get("next_cursor", "") or ""
            )
            if not next_cursor:
                break
            cursor = next_cursor

        return messages[:message_limit]

    def _fetch_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> list[dict[str, Any]]:
        """
        Return all replies in a thread (excluding the parent message, which is
        already present in the channel history).
        """
        assert self._client is not None
        replies: list[dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": 200,
            }
            if cursor:
                kwargs["cursor"] = cursor

            try:
                resp = self._call_with_retry(
                    self._client.conversations_replies, **kwargs
                )
            except SlackApiError as exc:
                logger.warning(
                    "Error fetching thread replies for ts=%s in %s: %s",
                    thread_ts,
                    channel_id,
                    exc,
                )
                break

            page: list[dict[str, Any]] = resp.get("messages", [])
            # Skip the first message (it is the parent) only on the first page
            if not cursor and page:
                page = page[1:]
            replies.extend(page)

            if not resp.get("has_more"):
                break
            next_cursor: str = (
                resp.get("response_metadata", {}).get("next_cursor", "") or ""
            )
            if not next_cursor:
                break
            cursor = next_cursor

        return replies

    # ------------------------------------------------------------------
    # Document building
    # ------------------------------------------------------------------

    def _format_message_line(
        self,
        msg: dict[str, Any],
        is_thread_reply: bool = False,
    ) -> str:
        """Format a single message as a Markdown line."""
        user_id: str = msg.get("user", "")
        display_name: str = self._get_display_name(user_id) if user_id else "unknown"
        ts: str = msg.get("ts", "")
        time_str: str = _ts_to_time_str(ts) if ts else "?"
        text: str = (msg.get("text") or "").strip()
        if not text:
            text = "*(empty message)*"

        if is_thread_reply:
            return f"  > **{display_name}** (Thread reply, {time_str}): {text}"
        return f"**{display_name}** ({time_str}): {text}"

    def _build_day_document(
        self,
        channel_id: str,
        channel_name: str,
        date_str: str,
        day_messages: list[dict[str, Any]],
        threads: dict[str, list[dict[str, Any]]],
    ) -> ConnectorDocument:
        """
        Build one ConnectorDocument representing all messages in *channel* for *date_str*.
        """
        lines: list[str] = [
            f"# #{channel_name} — {date_str}",
            "",
        ]

        last_ts: str = ""
        for msg in day_messages:
            ts: str = msg.get("ts", "")
            if ts:
                last_ts = ts
            lines.append(self._format_message_line(msg, is_thread_reply=False))

            # Inline thread replies
            if _cfg(self.config, "include_threads"):
                for reply in threads.get(ts, []):
                    lines.append(self._format_message_line(reply, is_thread_reply=True))

            lines.append("")  # blank line between messages

        content = "\n".join(lines).rstrip() or f"# #{channel_name} — {date_str}"

        updated_at: datetime = (
            _ts_to_datetime(last_ts) if last_ts else datetime.utcnow()
        )

        workspace_id: str = self._workspace_id or "T0000000"
        url = f"https://app.slack.com/client/{workspace_id}/{channel_id}"

        return ConnectorDocument(
            external_id=f"{channel_id}/day/{date_str}",
            title=f"#{channel_name} — {date_str}",
            content=content,
            url=url,
            updated_at=updated_at,
            metadata={
                "channel_id": channel_id,
                "channel_name": channel_name,
                "date": date_str,
                "message_count": len(day_messages),
            },
            file_type="md",
        )

    # ------------------------------------------------------------------
    # Core sync logic
    # ------------------------------------------------------------------

    def _sync_channel(
        self,
        channel: dict[str, Any],
        oldest: Optional[str] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """
        Yield batches of day-grouped ConnectorDocuments for a single channel.
        """
        channel_id: str = channel["id"]
        channel_name: str = channel.get("name") or channel_id

        logger.info("Syncing Slack channel: #%s (%s)", channel_name, channel_id)

        time.sleep(0.2)  # polite throttle between channels

        messages = self._fetch_channel_messages(channel_id, oldest=oldest)
        if not messages:
            logger.debug("No messages found for #%s.", channel_name)
            return

        # Fetch thread replies for messages that have them
        threads: dict[str, list[dict[str, Any]]] = {}
        if _cfg(self.config, "include_threads"):
            for msg in messages:
                reply_count: int = int(msg.get("reply_count", 0))
                if reply_count > 0:
                    ts: str = msg.get("ts", "")
                    if ts:
                        try:
                            threads[ts] = self._fetch_thread_replies(channel_id, ts)
                        except Exception as exc:
                            logger.warning(
                                "Error fetching thread %s in #%s: %s — skipping.",
                                ts,
                                channel_name,
                                exc,
                            )
                        time.sleep(0.1)  # brief pause between thread fetches

        # Group messages by calendar day (UTC)
        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for msg in messages:
            ts = msg.get("ts", "")
            if ts:
                if self._last_message_ts is None or ts > self._last_message_ts:
                    self._last_message_ts = ts
                by_day[_ts_to_date_str(ts)].append(msg)

        batch: list[ConnectorDocument] = []
        for date_str in sorted(by_day.keys()):
            try:
                doc = self._build_day_document(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    date_str=date_str,
                    day_messages=by_day[date_str],
                    threads=threads,
                )
                batch.append(doc)
                if len(batch) >= _BATCH_SIZE:
                    yield batch
                    batch = []
            except Exception as exc:
                logger.warning(
                    "Error building day document for #%s on %s: %s — skipping.",
                    channel_name,
                    date_str,
                    exc,
                )

        if batch:
            yield batch

    def _sync(self, oldest: Optional[str] = None) -> Iterator[list[ConnectorDocument]]:
        """Internal sync: iterate channels and yield batches of ConnectorDocuments."""
        try:
            channels = self._list_channels()
        except Exception as exc:
            raise RuntimeError(f"Failed to list Slack channels: {exc}") from exc

        logger.info("Slack connector: syncing %d channel(s).", len(channels))

        for channel in channels:
            try:
                channel_id = channel.get("id")
                if channel_id and channel_id not in self._processed_channels:
                    self._processed_channels.append(channel_id)
                yield from self._sync_channel(channel, oldest=oldest)
            except Exception as exc:
                channel_name = channel.get("name") or channel.get("id", "?")
                logger.warning(
                    "Unexpected error syncing channel #%s: %s — skipping.",
                    channel_name,
                    exc,
                )

    # ------------------------------------------------------------------
    # Public BaseConnector interface
    # ------------------------------------------------------------------

    def fetch_all(self) -> Iterator[list[ConnectorDocument]]:
        """Yield all messages from the configured Slack channels, grouped by day."""
        yield from self._sync(oldest=None)

    def fetch_updated(
        self,
        since: datetime,
        checkpoint: Optional[dict[str, Any]] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """Yield messages posted after *since* (incremental sync)."""
        # Prefer the checkpoint timestamp if it is more recent
        effective_since: datetime = since
        if checkpoint and "last_sync_time" in checkpoint:
            try:
                cp_time = datetime.fromisoformat(checkpoint["last_sync_time"])
                if cp_time > since:
                    effective_since = cp_time
            except (ValueError, TypeError):
                pass

        # Slack conversations_history accepts `oldest` as a Unix timestamp string
        oldest_ts: str = str(effective_since.replace(tzinfo=timezone.utc).timestamp())
        yield from self._sync(oldest=oldest_ts)

    def build_checkpoint(self) -> Optional[dict[str, Any]]:
        """Record the current UTC time so the next incremental sync can use it."""
        return {
            "last_sync_time": datetime.utcnow().isoformat(),
            "last_message_ts": self._last_message_ts,
            "processed_channels": list(self._processed_channels),
        }

    def restore_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Restore sync progress from a saved checkpoint."""
        self._last_message_ts = checkpoint.get("last_message_ts")
        self._processed_channels = list(checkpoint.get("processed_channels") or [])
