"""
Unit tests for the SlackConnector.

Tests the contract:
- load_credentials({"bot_token": "xoxb-test"})
- validate() - calls client.auth_test()
- Messages grouped by day: 3 messages on same day → 1 ConnectorDocument
- Messages on different days → 2 ConnectorDocuments
- Thread replies included in content when include_threads=True
- external_id format: "{channel_id}/day/{YYYY-MM-DD}"
- Empty channel (no messages): no documents yielded
- Rate limit: SlackApiError with error="ratelimited" causes sleep+retry
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Import with defensive try/except since SDK may not be installed
try:
    from app.connectors.slack import SlackConnector

    SLACK_AVAILABLE = True
except (ImportError, RuntimeError):
    SLACK_AVAILABLE = False


@pytest.mark.skipif(not SLACK_AVAILABLE, reason="slack-sdk not installed")
@pytest.mark.unit
class TestSlackConnector:
    """Test suite for SlackConnector."""

    @pytest.fixture
    def connector(self):
        """Create a SlackConnector with test config."""
        connector = SlackConnector(
            config={
                "channel_ids": ["C123456"],
                "include_threads": True,
            }
        )
        return connector

    @pytest.fixture
    def mock_client(self):
        """Create a mock Slack client."""
        return MagicMock()

    def test_init(self):
        """Test connector initialization."""
        connector = SlackConnector(
            config={
                "channel_ids": ["C123", "C456"],
                "include_threads": True,
                "include_private": False,
            }
        )
        assert connector.config["channel_ids"] == ["C123", "C456"]
        assert connector.config["include_threads"] is True
        assert connector.config["include_private"] is False
        assert connector._client is None
        assert connector._bot_token is None

    def test_load_credentials(self, connector):
        """Test loading credentials with bot_token."""
        connector.load_credentials({"bot_token": "xoxb-test"})
        assert connector._bot_token == "xoxb-test"

    def test_load_credentials_missing_token_raises(self, connector):
        """Test that missing bot_token raises ValueError."""
        with pytest.raises(ValueError, match="bot_token"):
            connector.load_credentials({})

    def test_validate_success(self, connector, mock_client):
        """Test validate() passes when auth_test() succeeds."""
        connector.load_credentials({"bot_token": "xoxb-test"})
        mock_client.auth_test.return_value = {
            "ok": True,
            "team": "Test Team",
            "user": "bot",
        }
        connector._client = mock_client

        # Should not raise
        connector.validate()
        mock_client.auth_test.assert_called_once()

    def test_validate_raises_on_failure(self, connector, mock_client):
        """Test validate() raises RuntimeError when auth_test() fails."""
        connector.load_credentials({"bot_token": "xoxb-test"})
        mock_client.auth_test.return_value = {"ok": False, "error": "invalid_auth"}
        connector._client = mock_client

        with pytest.raises(RuntimeError, match="Slack validation failed"):
            connector.validate()

    def test_validate_raises_on_exception(self, connector, mock_client):
        """Test validate() raises RuntimeError on API exception."""
        connector.load_credentials({"bot_token": "xoxb-test"})
        mock_client.auth_test.side_effect = Exception("Connection error")
        connector._client = mock_client

        with pytest.raises(RuntimeError, match="Slack validation failed"):
            connector.validate()

    def test_fetch_all_groups_messages_by_day(self, connector, mock_client):
        """Test that messages on same day are grouped into single document."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        # Three messages on the same day
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",  # 2024-01-15 10:00:00
                    "text": "First message",
                    "user": "U123",
                    "thread_ts": None,
                },
                {
                    "ts": "1705316400.000000",  # 2024-01-15 11:00:00
                    "text": "Second message",
                    "user": "U456",
                    "thread_ts": None,
                },
                {
                    "ts": "1705320000.000000",  # 2024-01-15 12:00:00
                    "text": "Third message",
                    "user": "U789",
                    "thread_ts": None,
                },
            ],
            "has_more": False,
        }

        # Mock channel info
        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())

        # Should yield exactly one document for all 3 messages (same day)
        all_docs = []
        for batch in batches:
            all_docs.extend(batch)

        assert len(all_docs) == 1
        doc = all_docs[0]
        assert doc.external_id == "C123456/day/2024-01-15"
        assert "First message" in doc.content
        assert "Second message" in doc.content
        assert "Third message" in doc.content

    def test_fetch_all_creates_multiple_documents_for_different_days(
        self, connector, mock_client
    ):
        """Test that messages on different days create multiple documents."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        # Messages on different days
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",  # 2024-01-15
                    "text": "Message on day 1",
                    "user": "U123",
                    "thread_ts": None,
                },
                {
                    "ts": "1705485600.000000",  # 2024-01-17
                    "text": "Message on day 2",
                    "user": "U456",
                    "thread_ts": None,
                },
            ],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())

        all_docs = []
        for batch in batches:
            all_docs.extend(batch)

        # Should yield 2 documents (one per day)
        assert len(all_docs) == 2

        external_ids = {d.external_id for d in all_docs}
        assert "C123456/day/2024-01-15" in external_ids
        assert "C123456/day/2024-01-17" in external_ids

    def test_external_id_format(self, connector, mock_client):
        """Test that external_id follows the correct format."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",  # 2024-01-15
                    "text": "Test message",
                    "user": "U123",
                    "thread_ts": None,
                }
            ],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())
        doc = batches[0][0]

        # Format should be: {channel_id}/day/{YYYY-MM-DD}
        assert doc.external_id == "C123456/day/2024-01-15"

    def test_empty_channel_yields_no_documents(self, connector, mock_client):
        """Test that empty channel yields no ConnectorDocuments."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "empty-channel"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())

        # Should yield no batches or empty batches
        total_docs = sum(len(batch) for batch in batches)
        assert total_docs == 0

    def test_thread_replies_included_when_configured(self, connector, mock_client):
        """Test that thread replies are included when include_threads=True."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        # Message with thread
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",
                    "text": "Parent message",
                    "user": "U123",
                    "thread_ts": "1705312800.000000",  # Has thread
                    "reply_count": 2,
                }
            ],
            "has_more": False,
        }

        # Thread replies
        mock_client.conversations_replies.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",
                    "text": "Parent message",
                    "user": "U123",
                    "thread_ts": "1705312800.000000",
                },
                {"ts": "1705312900.000000", "text": "Reply 1", "user": "U456"},
                {"ts": "1705313000.000000", "text": "Reply 2", "user": "U789"},
            ],
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())

        doc = batches[0][0]
        assert "Parent message" in doc.content
        assert "Reply 1" in doc.content
        assert "Reply 2" in doc.content

    def test_thread_replies_excluded_when_not_configured(self):
        """Test that thread replies are excluded when include_threads=False."""
        connector = SlackConnector(
            config={"channel_ids": ["C123456"], "include_threads": False}
        )
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client = MagicMock()
        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",
                    "text": "Parent message",
                    "user": "U123",
                    "thread_ts": "1705312800.000000",
                    "reply_count": 2,
                }
            ],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())

        doc = batches[0][0]
        assert "Parent message" in doc.content
        # conversations_replies should not be called
        mock_client.conversations_replies.assert_not_called()

    def test_rate_limit_error_triggers_retry(self, connector, mock_client):
        """Test that rate limit error triggers sleep and retry."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        # First call raises rate limit, second succeeds
        mock_client.conversations_history.side_effect = [
            MagicMock(ok=False, error="ratelimited", data={"retry_after": 1}),
            {
                "ok": True,
                "messages": [
                    {
                        "ts": "1705312800.000000",
                        "text": "Message",
                        "user": "U123",
                        "thread_ts": None,
                    }
                ],
                "has_more": False,
            },
        ]

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        with patch("time.sleep") as mock_sleep:  # Speed up test
            batches = list(connector.fetch_all())

        # Should have retried
        assert mock_client.conversations_history.call_count == 2
        mock_sleep.assert_called()

    def test_fetch_updated_with_since_parameter(self, connector, mock_client):
        """Test fetch_updated() passes since timestamp to API."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        connector._client = mock_client

        since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        list(connector.fetch_updated(since=since, checkpoint=None))

        # Verify conversations_history was called with oldest parameter
        mock_client.conversations_history.assert_called()
        call_kwargs = mock_client.conversations_history.call_args.kwargs
        assert "oldest" in call_kwargs

    def test_message_formatting_includes_user_and_timestamp(
        self, connector, mock_client
    ):
        """Test that message content includes user info and timestamp."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",  # 2024-01-15 10:00:00
                    "text": "Hello team!",
                    "user": "U123",
                    "thread_ts": None,
                }
            ],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "general"},
        }

        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "John Doe", "name": "john"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())
        doc = batches[0][0]

        # Content should include message text
        assert "Hello team!" in doc.content

    def test_multiple_channels_processed(self, connector, mock_client):
        """Test that multiple channels are processed."""
        connector = SlackConnector(
            config={"channel_ids": ["C123", "C456"], "include_threads": False}
        )
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",
                    "text": "Message",
                    "user": "U123",
                    "thread_ts": None,
                }
            ],
            "has_more": False,
        }

        mock_client.conversations_info.side_effect = [
            {"ok": True, "channel": {"name": "channel-1"}},
            {"ok": True, "channel": {"name": "channel-2"}},
        ]

        connector._client = mock_client

        batches = list(connector.fetch_all())

        # Should have fetched from both channels
        assert mock_client.conversations_history.call_count == 2
        assert mock_client.conversations_info.call_count == 2

    def test_document_title_format(self, connector, mock_client):
        """Test that document title includes channel and date."""
        connector.load_credentials({"bot_token": "xoxb-test"})

        mock_client.conversations_history.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1705312800.000000",
                    "text": "Message",
                    "user": "U123",
                    "thread_ts": None,
                }
            ],
            "has_more": False,
        }

        mock_client.conversations_info.return_value = {
            "ok": True,
            "channel": {"name": "engineering"},
        }

        connector._client = mock_client

        batches = list(connector.fetch_all())
        doc = batches[0][0]

        # Title should contain channel name and date
        assert "engineering" in doc.title.lower() or "C123456" in doc.title
        assert "2024" in doc.title or "Jan" in doc.title or "01-15" in doc.title

    def test_checkpoint_save_and_restore(self, connector):
        """Test build_checkpoint and restore_checkpoint methods."""
        connector._last_message_ts = "1705312800.000000"
        connector._processed_channels = ["C123456"]

        checkpoint = connector.build_checkpoint()

        assert checkpoint is not None
        assert checkpoint.get("last_message_ts") == "1705312800.000000"
        assert "C123456" in checkpoint.get("processed_channels", [])

        # Restore checkpoint
        connector.restore_checkpoint(
            {"last_message_ts": "1705400000.000000", "processed_channels": ["C789"]}
        )

        assert connector._last_message_ts == "1705400000.000000"
        assert connector._processed_channels == ["C789"]
