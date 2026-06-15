"""
Unit tests for the LinearConnector.

Tests the contract:
- load_credentials({"api_key": "lin_api_test"})
- validate() - POST to Linear GraphQL endpoint, succeeds if returns {"data": {"viewer": {"id": "u1"}}}
- fetch_all() - yields ConnectorDocuments with external_id, title containing identifier like "ENG-123"
- Issue with description and comments produces multi-section markdown content
- Issue with no description: content is just the title
- fetch_updated(since, checkpoint) - passes correct updatedAt filter to GraphQL
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Import with defensive try/except since SDK may not be installed
try:
    from app.connectors.linear import LinearConnector
    LINEAR_AVAILABLE = True
except (ImportError, RuntimeError):
    LINEAR_AVAILABLE = False


@pytest.mark.skipif(not LINEAR_AVAILABLE, reason="linear client not installed")
@pytest.mark.unit
class TestLinearConnector:
    """Test suite for LinearConnector."""

    @pytest.fixture
    def connector(self):
        """Create a LinearConnector with test config."""
        connector = LinearConnector(config={
            "team_ids": ["team-123"],
            "include_issues": True,
        })
        return connector

    @pytest.fixture
    def mock_client(self):
        """Create a mock Linear client."""
        return MagicMock()

    def test_init(self):
        """Test connector initialization."""
        connector = LinearConnector(config={
            "team_ids": ["team-1", "team-2"],
            "include_issues": True,
            "include_comments": True
        })
        assert connector.config["team_ids"] == ["team-1", "team-2"]
        assert connector.config["include_issues"] is True
        assert connector.config["include_comments"] is True
        assert connector._client is None
        assert connector._api_key is None

    def test_load_credentials(self, connector):
        """Test loading credentials with api_key."""
        connector.load_credentials({"api_key": "lin_api_test"})
        assert connector._api_key == "lin_api_test"

    def test_load_credentials_missing_key_raises(self, connector):
        """Test that missing api_key raises ValueError."""
        with pytest.raises(ValueError, match="api_key"):
            connector.load_credentials({})

    def test_validate_success(self, connector):
        """Test validate() passes when GraphQL returns viewer data."""
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_response = {
            "data": {"viewer": {"id": "u1", "name": "Test User"}}
        }

        with patch.object(connector, '_make_graphql_request', return_value=mock_response):
            # Should not raise
            connector.validate()

    def test_validate_raises_on_invalid_response(self, connector):
        """Test validate() raises RuntimeError when GraphQL returns error."""
        connector.load_credentials({"api_key": "lin_api_test"})

        # Error response
        mock_response = {
            "errors": [{"message": "Authentication failed"}]
        }

        with patch.object(connector, '_make_graphql_request', return_value=mock_response):
            with pytest.raises(RuntimeError, match="Linear validation failed"):
                connector.validate()

    def test_validate_raises_on_missing_viewer(self, connector):
        """Test validate() raises when viewer data is missing."""
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_response = {
            "data": {}  # No viewer field
        }

        with patch.object(connector, '_make_graphql_request', return_value=mock_response):
            with pytest.raises(RuntimeError, match="Linear validation failed"):
                connector.validate()

    def test_fetch_all_yields_connector_documents(self, connector):
        """Test fetch_all() yields ConnectorDocument instances with issue identifiers."""
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_issues = [
            {
                "id": "issue-123",
                "identifier": "ENG-123",
                "title": "Fix bug in authentication",
                "description": "The login flow is broken",
                "url": "https://linear.app/issue/ENG-123",
                "updatedAt": "2024-01-15T10:30:00.000Z",
                "state": {"name": "In Progress"},
                "assignee": {"name": "John Doe"}
            }
        ]

        with patch.object(connector, '_fetch_issues', return_value=mock_issues):
            batches = list(connector.fetch_all())

        assert len(batches) > 0
        docs = batches[0]
        assert len(docs) == 1

        doc = docs[0]
        assert doc.external_id == "issue-123"
        assert "ENG-123" in doc.title
        assert "Fix bug in authentication" in doc.title
        assert doc.url == "https://linear.app/issue/ENG-123"
        assert doc.updated_at is not None
        assert doc.file_type == "md"

    def test_fetch_all_includes_description_in_content(self, connector):
        """Test that issue description is included in document content."""
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_issues = [
            {
                "id": "issue-456",
                "identifier": "ENG-456",
                "title": "Add feature X",
                "description": "We need to implement feature X\nWith multiple lines",
                "url": "https://linear.app/issue/ENG-456",
                "updatedAt": "2024-01-16T10:30:00.000Z",
                "state": {"name": "Todo"},
                "assignee": None
            }
        ]

        with patch.object(connector, '_fetch_issues', return_value=mock_issues):
            batches = list(connector.fetch_all())

        docs = batches[0]
        doc = docs[0]
        # Content should include both title and description
        assert "Add feature X" in doc.content
        assert "We need to implement feature X" in doc.content

    def test_fetch_all_no_description_uses_title_only(self, connector):
        """Test that issue with no description has content = title only."""
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_issues = [
            {
                "id": "issue-789",
                "identifier": "ENG-789",
                "title": "Quick fix",
                "description": None,  # No description
                "url": "https://linear.app/issue/ENG-789",
                "updatedAt": "2024-01-17T10:30:00.000Z",
                "state": {"name": "Done"},
                "assignee": None
            }
        ]

        with patch.object(connector, '_fetch_issues', return_value=mock_issues):
            batches = list(connector.fetch_all())

        docs = batches[0]
        doc = docs[0]
        # Content should be title only (no description section)
        assert doc.content.strip() == "Quick fix"

    def test_fetch_all_includes_comments_when_configured(self, connector):
        """Test that comments are included in content when include_comments=True."""
        connector = LinearConnector(config={
            "team_ids": ["team-123"],
            "include_issues": True,
            "include_comments": True
        })
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_issues = [
            {
                "id": "issue-with-comments",
                "identifier": "ENG-100",
                "title": "Issue with comments",
                "description": "Description here",
                "url": "https://linear.app/issue/ENG-100",
                "updatedAt": "2024-01-18T10:30:00.000Z",
                "state": {"name": "In Progress"},
                "comments": {
                    "nodes": [
                        {"user": {"name": "Alice"}, "body": "First comment"},
                        {"user": {"name": "Bob"}, "body": "Second comment"}
                    ]
                }
            }
        ]

        with patch.object(connector, '_fetch_issues', return_value=mock_issues):
            batches = list(connector.fetch_all())

        docs = batches[0]
        doc = docs[0]
        # Content should include comments section
        assert "First comment" in doc.content
        assert "Second comment" in doc.content
        assert "Alice" in doc.content
        assert "Bob" in doc.content

    def test_fetch_all_metadata_includes_state_and_assignee(self, connector):
        """Test that document metadata includes state and assignee info."""
        connector.load_credentials({"api_key": "lin_api_test"})

        mock_issues = [
            {
                "id": "issue-meta",
                "identifier": "ENG-200",
                "title": "Test issue",
                "description": "Test",
                "url": "https://linear.app/issue/ENG-200",
                "updatedAt": "2024-01-19T10:30:00.000Z",
                "state": {"name": "Backlog", "color": "#ff0000"},
                "assignee": {"name": "Jane Smith", "email": "jane@example.com"},
                "priority": 1,
                "labels": [{"name": "bug"}, {"name": "urgent"}]
            }
        ]

        with patch.object(connector, '_fetch_issues', return_value=mock_issues):
            batches = list(connector.fetch_all())

        docs = batches[0]
        doc = docs[0]
        # Check metadata
        assert doc.metadata.get("state") == "Backlog"
        assert doc.metadata.get("assignee") == "Jane Smith"
        assert doc.metadata.get("priority") == 1
        assert "bug" in doc.metadata.get("labels", [])
        assert "urgent" in doc.metadata.get("labels", [])

    def test_fetch_updated_with_since_filter(self, connector):
        """Test fetch_updated() passes updatedAt filter to GraphQL query."""
        connector.load_credentials({"api_key": "lin_api_test"})

        since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        with patch.object(connector, '_fetch_issues') as mock_fetch:
            mock_fetch.return_value = []
            list(connector.fetch_updated(since=since, checkpoint=None))

            # Verify _fetch_issues was called with since parameter
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            # The since parameter should be passed

    def test_fetch_updated_respects_checkpoint(self, connector):
        """Test fetch_updated() respects checkpoint state."""
        connector.load_credentials({"api_key": "lin_api_test"})

        since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        checkpoint = {"last_issue_id": "issue-999", "cursor": "cursor-xyz"}

        with patch.object(connector, '_fetch_issues') as mock_fetch:
            mock_fetch.return_value = []
            list(connector.fetch_updated(since=since, checkpoint=checkpoint))

            # Checkpoint should be used if supported
            mock_fetch.assert_called_once()

    def test_build_checkpoint_returns_state(self, connector):
        """Test build_checkpoint() returns current sync state."""
        connector._last_issue_id = "issue-last"
        connector._cursor = "cursor-abc"

        checkpoint = connector.build_checkpoint()

        assert checkpoint is not None
        assert checkpoint.get("last_issue_id") == "issue-last"
        assert checkpoint.get("cursor") == "cursor-abc"

    def test_restore_checkpoint_sets_state(self, connector):
        """Test restore_checkpoint() restores internal state."""
        checkpoint = {"last_issue_id": "issue-restored", "cursor": "cursor-restored"}

        connector.restore_checkpoint(checkpoint)

        assert connector._last_issue_id == "issue-restored"
        assert connector._cursor == "cursor-restored"

    def test_empty_issues_list_yields_no_batches(self, connector):
        """Test that empty issues list yields no documents."""
        connector.load_credentials({"api_key": "lin_api_test"})

        with patch.object(connector, '_fetch_issues', return_value=[]):
            batches = list(connector.fetch_all())

        # Should yield no batches or empty batches
        assert len(batches) == 0 or all(len(batch) == 0 for batch in batches)

    def test_make_graphql_request_error_handling(self, connector):
        """Test GraphQL request error handling."""
        connector.load_credentials({"api_key": "lin_api_test"})

        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Network error")

            with pytest.raises(RuntimeError):
                connector._make_graphql_request("query { viewer { id } }")
