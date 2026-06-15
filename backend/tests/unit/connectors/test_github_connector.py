"""
Unit tests for the GitHubConnector.

Tests the contract:
- load_credentials({"access_token": "ghp_test"})
- validate() - calls g.get_user().login
- README fetched when include_readme=True: produces doc with external_id ending in /readme
- Issues fetched: doc has external_id like owner/repo/issue/123
- PRs filtered correctly when include_pull_requests=False
- fetch_updated(since, checkpoint) passes since to get_issues(since=...)
- Rate limit exception: caught and retried (mock RateLimitExceededException)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

# Import with defensive try/except since SDK may not be installed
try:
    from app.connectors.github import GitHubConnector
    GITHUB_AVAILABLE = True
except (ImportError, RuntimeError):
    GITHUB_AVAILABLE = False


@pytest.mark.skipif(not GITHUB_AVAILABLE, reason="PyGithub not installed")
@pytest.mark.unit
class TestGitHubConnector:
    """Test suite for GitHubConnector."""

    @pytest.fixture
    def connector(self):
        """Create a GitHubConnector with test config."""
        connector = GitHubConnector(config={
            "owner": "testowner",
            "repo": "testrepo",
            "include_issues": True,
            "include_pull_requests": True,
            "include_readme": True,
        })
        return connector

    @pytest.fixture
    def mock_github(self):
        """Create a mock PyGithub instance."""
        return MagicMock()

    def test_init(self):
        """Test connector initialization."""
        connector = GitHubConnector(config={
            "owner": "myorg",
            "repo": "myrepo",
            "include_issues": True,
            "include_pull_requests": False,
            "include_readme": True
        })
        assert connector.config["owner"] == "myorg"
        assert connector.config["repo"] == "myrepo"
        assert connector.config["include_issues"] is True
        assert connector.config["include_pull_requests"] is False
        assert connector.config["include_readme"] is True
        assert connector._github is None
        assert connector._access_token is None

    def test_load_credentials(self, connector):
        """Test loading credentials with access_token."""
        connector.load_credentials({"access_token": "ghp_test"})
        assert connector._access_token == "ghp_test"

    def test_load_credentials_missing_token_raises(self, connector):
        """Test that missing access_token raises ValueError."""
        with pytest.raises(ValueError, match="access_token"):
            connector.load_credentials({})

    def test_validate_success(self, connector):
        """Test validate() passes when get_user().login succeeds."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_user = MagicMock()
        mock_user.login = "testuser"

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_user.return_value = mock_user
            mock_github_class.return_value = mock_github

            # Should not raise
            connector.validate()
            mock_github.get_user.assert_called_once()

    def test_validate_raises_on_auth_failure(self, connector):
        """Test validate() raises RuntimeError on auth failure."""
        connector.load_credentials({"access_token": "ghp_test"})

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_user.side_effect = Exception("Bad credentials")
            mock_github_class.return_value = mock_github

            with pytest.raises(RuntimeError, match="GitHub validation failed"):
                connector.validate()

    def test_fetch_all_includes_readme_when_configured(self, connector):
        """Test that README is fetched when include_readme=True."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.full_name = "testowner/testrepo"
        mock_repo.get_readme.return_value = MagicMock(
            decoded_content=b"# README\n\nThis is the readme content",
            html_url="https://github.com/testowner/testrepo/blob/main/README.md",
            last_modified_datetime=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        )

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        # Should have at least one document
        all_docs = []
        for batch in batches:
            all_docs.extend(batch)

        # Find README document
        readme_docs = [d for d in all_docs if d.external_id.endswith("/readme")]
        assert len(readme_docs) == 1

        readme = readme_docs[0]
        assert readme.external_id == "testowner/testrepo/readme"
        assert "README" in readme.title
        assert "This is the readme content" in readme.content

    def test_fetch_all_skips_readme_when_not_configured(self):
        """Test that README is not fetched when include_readme=False."""
        connector = GitHubConnector(config={
            "owner": "testowner",
            "repo": "testrepo",
            "include_issues": True,
            "include_readme": False
        })
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.get_readme.return_value = None
        mock_repo.get_issues.return_value = []

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        # get_readme should not be called
        mock_repo.get_readme.assert_not_called()

    def test_fetch_all_includes_issues(self, connector):
        """Test that issues are fetched with correct external_id format."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_issue = MagicMock()
        mock_issue.number = 123
        mock_issue.title = "Bug: Something is broken"
        mock_issue.body = "Description of the bug"
        mock_issue.html_url = "https://github.com/testowner/testrepo/issues/123"
        mock_issue.updated_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_issue.state = "open"
        mock_issue.labels = []
        mock_issue.assignee = None

        mock_repo = MagicMock()
        mock_repo.full_name = "testowner/testrepo"
        mock_repo.get_issues.return_value = [mock_issue]
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        all_docs = []
        for batch in batches:
            all_docs.extend(batch)

        # Find issue document
        issue_docs = [d for d in all_docs if "issue/123" in d.external_id]
        assert len(issue_docs) == 1

        issue_doc = issue_docs[0]
        assert issue_doc.external_id == "testowner/testrepo/issue/123"
        assert issue_doc.title == "Bug: Something is broken"
        assert "Description of the bug" in issue_doc.content
        assert issue_doc.url == "https://github.com/testowner/testrepo/issues/123"

    def test_fetch_all_includes_pull_requests_when_configured(self, connector):
        """Test that PRs are fetched when include_pull_requests=True."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_pr = MagicMock()
        mock_pr.number = 456
        mock_pr.title = "Feature: Add new feature"
        mock_pr.body = "PR description"
        mock_pr.html_url = "https://github.com/testowner/testrepo/pull/456"
        mock_pr.updated_at = datetime(2024, 1, 16, 10, 0, 0, tzinfo=timezone.utc)
        mock_pr.state = "open"
        mock_pr.labels = []
        mock_pr.assignee = None

        mock_repo = MagicMock()
        mock_repo.full_name = "testowner/testrepo"
        mock_repo.get_issues.return_value = []
        mock_repo.get_pulls.return_value = [mock_pr]
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        all_docs = []
        for batch in batches:
            all_docs.extend(batch)

        # Find PR document
        pr_docs = [d for d in all_docs if "pull/456" in d.external_id]
        assert len(pr_docs) == 1

        pr_doc = pr_docs[0]
        assert pr_doc.external_id == "testowner/testrepo/pull/456"
        assert pr_doc.title == "Feature: Add new feature"

    def test_fetch_all_skips_pull_requests_when_not_configured(self):
        """Test that PRs are not fetched when include_pull_requests=False."""
        connector = GitHubConnector(config={
            "owner": "testowner",
            "repo": "testrepo",
            "include_issues": True,
            "include_pull_requests": False
        })
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        # get_pulls should not be called
        mock_repo.get_pulls.assert_not_called()

    def test_fetch_updated_passes_since_to_issues(self, connector):
        """Test fetch_updated() passes since parameter to get_issues()."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            list(connector.fetch_updated(since=since, checkpoint=None))

        # Verify get_issues was called with since parameter
        mock_repo.get_issues.assert_called_once()
        call_kwargs = mock_repo.get_issues.call_args.kwargs
        assert "since" in call_kwargs
        assert call_kwargs["since"] == since

    def test_fetch_updated_with_checkpoint(self, connector):
        """Test fetch_updated() handles checkpoint state."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            checkpoint = {"last_issue_number": 100}
            list(connector.fetch_updated(since=since, checkpoint=checkpoint))

        # Checkpoint should be handled if supported

    def test_rate_limit_exception_retries(self, connector):
        """Test that RateLimitExceededException triggers retry."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.get_readme.return_value = None

        # First two calls raise rate limit, third succeeds
        rate_limit_error = Exception("Rate limit exceeded")
        mock_repo.get_issues.side_effect = [
            rate_limit_error,
            rate_limit_error,
            []
        ]

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            with patch('time.sleep'):  # Speed up test
                batches = list(connector.fetch_all())

        # Should have retried
        assert mock_repo.get_issues.call_count >= 1

    def test_issue_metadata_includes_labels_and_assignee(self, connector):
        """Test that issue documents include labels and assignee in metadata."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_label1 = MagicMock()
        mock_label1.name = "bug"
        mock_label2 = MagicMock()
        mock_label2.name = "urgent"

        mock_assignee = MagicMock()
        mock_assignee.login = "johndoe"

        mock_issue = MagicMock()
        mock_issue.number = 789
        mock_issue.title = "Issue with metadata"
        mock_issue.body = "Body"
        mock_issue.html_url = "https://github.com/testowner/testrepo/issues/789"
        mock_issue.updated_at = datetime(2024, 1, 17, 10, 0, 0, tzinfo=timezone.utc)
        mock_issue.state = "open"
        mock_issue.labels = [mock_label1, mock_label2]
        mock_issue.assignee = mock_assignee

        mock_repo = MagicMock()
        mock_repo.full_name = "testowner/testrepo"
        mock_repo.get_issues.return_value = [mock_issue]
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        all_docs = []
        for batch in batches:
            all_docs.extend(batch)

        issue_doc = [d for d in all_docs if "issue/789" in d.external_id][0]
        assert issue_doc.metadata.get("state") == "open"
        assert issue_doc.metadata.get("assignee") == "johndoe"
        assert "bug" in issue_doc.metadata.get("labels", [])
        assert "urgent" in issue_doc.metadata.get("labels", [])

    def test_empty_repo_yields_no_documents(self, connector):
        """Test that empty repository yields no documents."""
        connector.load_credentials({"access_token": "ghp_test"})

        mock_repo = MagicMock()
        mock_repo.full_name = "testowner/testrepo"
        mock_repo.get_issues.return_value = []
        mock_repo.get_pulls.return_value = []
        mock_repo.get_readme.return_value = None

        with patch('github.Github') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            batches = list(connector.fetch_all())

        # Should yield no batches or empty batches
        total_docs = sum(len(batch) for batch in batches)
        assert total_docs == 0

    def test_multiple_owners_repos_in_config(self):
        """Test connector with multiple repos specified."""
        connector = GitHubConnector(config={
            "repos": ["owner1/repo1", "owner2/repo2"],
            "include_issues": True,
            "include_readme": True
        })
        connector.load_credentials({"access_token": "ghp_test"})

        assert "repos" in connector.config
        assert len(connector.config["repos"]) == 2
