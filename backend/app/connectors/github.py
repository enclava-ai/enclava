"""
GitHub connector.

Syncs issues, pull requests, and README documents from GitHub repositories
into Enclava RAG collections using the PyGithub library.

Install dependency:
    pip install PyGithub
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Iterator, Optional

try:
    from github import Github, GithubException, RateLimitExceededException
    from github.ContentFile import ContentFile
    from github.Issue import Issue
    from github.PullRequest import PullRequest
    from github.Repository import Repository
except ImportError:
    raise RuntimeError("Install PyGithub: pip install PyGithub")

from app.connectors.base import BaseConnector, ConnectorDocument

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50

# Default config values — used when a key is absent from the supplied config dict
_DEFAULTS: dict[str, Any] = {
    "repositories": [],
    "include_issues": True,
    "include_pull_requests": True,
    "include_readme": True,
    "include_discussions": False,
    "state": "all",
}


def _cfg(config: dict[str, Any], key: str) -> Any:
    """Return config[key] with fallback to _DEFAULTS."""
    return config.get(key, _DEFAULTS[key])


class GitHubConnector(BaseConnector):
    """
    Connector for GitHub repositories.

    Credential schema (one of):
        {"access_token": "ghp_..."}
        {"api_token":    "ghp_..."}

    Config schema (all optional, shown with defaults):
        {
            "repositories":           [],     # ["owner/repo", …]; empty = all accessible repos
            "include_issues":         True,
            "include_pull_requests":  True,
            "include_readme":         True,
            "include_discussions":    False,  # not implemented
            "state":                  "all",  # "open" | "closed" | "all"
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._token: Optional[str] = None
        self._client: Optional[Github] = None

    # ------------------------------------------------------------------
    # Credential loading
    # ------------------------------------------------------------------

    def load_credentials(self, credentials: dict[str, Any]) -> None:
        """Accept ``access_token`` or ``api_token`` key."""
        token = credentials.get("access_token") or credentials.get("api_token")
        if not token:
            raise ValueError(
                "GitHub credentials must contain 'access_token' or 'api_token'."
            )
        self._token = token
        self._client = Github(token)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Verify credentials by fetching the authenticated user's login."""
        if self._client is None:
            raise RuntimeError("call load_credentials() before validate().")
        try:
            login = self._client.get_user().login
            logger.info("GitHub connector validated. Authenticated as: %s", login)
        except GithubException as exc:
            raise ValueError(
                f"GitHub credential validation failed: {exc.status} {exc.data}"
            ) from exc

    # ------------------------------------------------------------------
    # Rate-limit helper
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Sleep until the GitHub core rate-limit window resets."""
        if self._client is None:
            return
        try:
            reset_at: datetime = self._client.get_rate_limit().core.reset
            now = datetime.utcnow()
            wait_seconds = max(0.0, (reset_at - now).total_seconds()) + 5.0
            logger.warning(
                "GitHub rate limit exceeded. Sleeping %.0f seconds until %s.",
                wait_seconds,
                reset_at.isoformat(),
            )
            time.sleep(wait_seconds)
        except GithubException:
            logger.warning("Could not determine rate-limit reset time; sleeping 60s.")
            time.sleep(60)

    # ------------------------------------------------------------------
    # Repository resolution
    # ------------------------------------------------------------------

    def _get_repos(self) -> list[Repository]:
        """Return the list of Repository objects to sync."""
        assert self._client is not None
        repo_slugs: list[str] = _cfg(self.config, "repositories")
        if repo_slugs:
            repos: list[Repository] = []
            for slug in repo_slugs:
                try:
                    repos.append(self._client.get_repo(slug))
                except GithubException as exc:
                    logger.warning(
                        "Could not fetch repo '%s': %s — skipping.", slug, exc
                    )
            return repos
        # No explicit list → all repos the token can access
        return list(self._client.get_user().get_repos())

    # ------------------------------------------------------------------
    # Document builders
    # ------------------------------------------------------------------

    def _build_readme_doc(self, repo: Repository) -> Optional[ConnectorDocument]:
        """Fetch and return a ConnectorDocument for the repo's README, or None."""
        try:
            readme: ContentFile = repo.get_readme()
            content: str = readme.decoded_content.decode("utf-8", errors="replace")
        except GithubException:
            logger.debug("No README found for %s.", repo.full_name)
            return None
        except Exception as exc:
            logger.warning("Error fetching README for %s: %s", repo.full_name, exc)
            return None

        if not content.strip():
            content = f"# {repo.full_name} README\n\n*(empty)*"

        return ConnectorDocument(
            external_id=f"{repo.full_name}/readme",
            title=f"{repo.full_name} README",
            content=content,
            url=f"https://github.com/{repo.full_name}",
            updated_at=repo.updated_at,
            metadata={
                "repo": repo.full_name,
                "doc_type": "readme",
                "language": repo.language,
            },
            file_type="md",
        )

    def _fetch_issue_comments_md(self, issue: Issue) -> str:
        """Return a markdown-formatted string of all comments on an issue."""
        lines: list[str] = []
        try:
            for comment in issue.get_comments():
                author = comment.user.login if comment.user else "unknown"
                date_str = (
                    comment.created_at.strftime("%Y-%m-%d")
                    if comment.created_at
                    else "unknown date"
                )
                body = (comment.body or "").strip()
                lines.append(f"### Comment by {author} ({date_str})")
                lines.append(body)
                lines.append("")
        except GithubException as exc:
            logger.warning("Could not fetch comments for issue: %s", exc)
        return "\n".join(lines)

    def _build_issue_doc(self, repo: Repository, issue: Issue) -> ConnectorDocument:
        """Build a ConnectorDocument for a GitHub issue."""
        labels = [label.name for label in issue.labels]
        author = issue.user.login if issue.user else "unknown"
        created_str = (
            issue.created_at.strftime("%Y-%m-%d") if issue.created_at else "unknown"
        )
        updated_str = (
            issue.updated_at.strftime("%Y-%m-%d") if issue.updated_at else "unknown"
        )
        body = (issue.body or "").strip()

        sections: list[str] = [
            f"# Issue #{issue.number}: {issue.title}",
            "",
            f"**State:** {issue.state}",
            f"**Author:** {author}",
            f"**Labels:** {', '.join(labels) if labels else 'none'}",
            f"**Created:** {created_str}",
            f"**Updated:** {updated_str}",
            "",
            "## Description",
            body if body else "*(no description)*",
            "",
            "## Comments",
        ]

        comments_md = self._fetch_issue_comments_md(issue)
        if comments_md.strip():
            sections.append(comments_md)
        else:
            sections.append("*(no comments)*")

        content = "\n".join(sections)

        return ConnectorDocument(
            external_id=f"{repo.full_name}/issue/{issue.number}",
            title=f"#{issue.number}: {issue.title}",
            content=content,
            url=issue.html_url,
            updated_at=issue.updated_at,
            metadata={
                "repo": repo.full_name,
                "doc_type": "issue",
                "number": issue.number,
                "state": issue.state,
                "labels": labels,
            },
            file_type="md",
        )

    def _fetch_pr_review_comments_md(self, pr: PullRequest) -> str:
        """Return a markdown summary of review comments on a pull request."""
        lines: list[str] = []
        try:
            for comment in pr.get_review_comments():
                author = comment.user.login if comment.user else "unknown"
                date_str = (
                    comment.created_at.strftime("%Y-%m-%d")
                    if comment.created_at
                    else "unknown date"
                )
                body = (comment.body or "").strip()
                path = comment.path or ""
                lines.append(f"### Review comment by {author} ({date_str}) on `{path}`")
                lines.append(body)
                lines.append("")
        except GithubException as exc:
            logger.warning("Could not fetch review comments for PR: %s", exc)
        return "\n".join(lines)

    def _fetch_pr_issue_comments_md(self, pr: PullRequest) -> str:
        """Return a markdown string of issue-style comments on a pull request."""
        lines: list[str] = []
        try:
            for comment in pr.get_issue_comments():
                author = comment.user.login if comment.user else "unknown"
                date_str = (
                    comment.created_at.strftime("%Y-%m-%d")
                    if comment.created_at
                    else "unknown date"
                )
                body = (comment.body or "").strip()
                lines.append(f"### Comment by {author} ({date_str})")
                lines.append(body)
                lines.append("")
        except GithubException as exc:
            logger.warning("Could not fetch issue comments for PR: %s", exc)
        return "\n".join(lines)

    def _build_pr_doc(self, repo: Repository, pr: PullRequest) -> ConnectorDocument:
        """Build a ConnectorDocument for a GitHub pull request."""
        labels = [label.name for label in pr.labels]
        author = pr.user.login if pr.user else "unknown"
        created_str = (
            pr.created_at.strftime("%Y-%m-%d") if pr.created_at else "unknown"
        )
        updated_str = (
            pr.updated_at.strftime("%Y-%m-%d") if pr.updated_at else "unknown"
        )
        body = (pr.body or "").strip()
        base_branch = pr.base.ref if pr.base else "unknown"
        head_branch = pr.head.ref if pr.head else "unknown"

        sections: list[str] = [
            f"# PR #{pr.number}: {pr.title}",
            "",
            f"**State:** {pr.state}",
            f"**Author:** {author}",
            f"**Labels:** {', '.join(labels) if labels else 'none'}",
            f"**Created:** {created_str}",
            f"**Updated:** {updated_str}",
            f"**Base branch:** {base_branch}",
            f"**Head branch:** {head_branch}",
            f"**Merged:** {'Yes' if pr.merged else 'No'}",
            "",
            "## Description",
            body if body else "*(no description)*",
            "",
            "## Comments",
        ]

        issue_comments_md = self._fetch_pr_issue_comments_md(pr)
        if issue_comments_md.strip():
            sections.append(issue_comments_md)
        else:
            sections.append("*(no comments)*\n")

        sections.append("## Review Comments")
        review_comments_md = self._fetch_pr_review_comments_md(pr)
        if review_comments_md.strip():
            sections.append(review_comments_md)
        else:
            sections.append("*(no review comments)*")

        content = "\n".join(sections)

        return ConnectorDocument(
            external_id=f"{repo.full_name}/pull/{pr.number}",
            title=f"#{pr.number}: {pr.title}",
            content=content,
            url=pr.html_url,
            updated_at=pr.updated_at,
            metadata={
                "repo": repo.full_name,
                "doc_type": "pull_request",
                "number": pr.number,
                "state": pr.state,
                "labels": labels,
                "merged": pr.merged,
            },
            file_type="md",
        )

    # ------------------------------------------------------------------
    # Core sync logic
    # ------------------------------------------------------------------

    def _iter_repo_documents(
        self,
        repo: Repository,
        since: Optional[datetime] = None,
    ) -> Iterator[ConnectorDocument]:
        """
        Yield individual ConnectorDocument objects for one repository.

        If *since* is provided, only items updated after that timestamp are
        fetched (for incremental sync).
        """
        state: str = _cfg(self.config, "state")

        # --- README ---
        if _cfg(self.config, "include_readme"):
            doc = self._build_readme_doc(repo)
            if doc is not None:
                yield doc

        # --- Issues (excluding PRs) ---
        if _cfg(self.config, "include_issues"):
            try:
                issue_kwargs: dict[str, Any] = {"state": state}
                if since is not None:
                    issue_kwargs["since"] = since
                for issue in repo.get_issues(**issue_kwargs):
                    # get_issues returns both issues AND pull requests
                    if issue.pull_request is not None:
                        continue  # skip PRs here; handled separately below
                    try:
                        yield self._build_issue_doc(repo, issue)
                    except RateLimitExceededException:
                        self._wait_for_rate_limit()
                        yield self._build_issue_doc(repo, issue)
                    except GithubException as exc:
                        logger.warning(
                            "Error building issue doc %s#%s: %s — skipping.",
                            repo.full_name,
                            issue.number,
                            exc,
                        )
            except RateLimitExceededException:
                self._wait_for_rate_limit()
            except GithubException as exc:
                logger.warning(
                    "Error fetching issues for %s: %s — skipping.", repo.full_name, exc
                )

        # --- Pull Requests ---
        if _cfg(self.config, "include_pull_requests"):
            # get_pulls does not accept a `since` param; filter manually when needed
            pr_state = state if state in ("open", "closed") else "all"
            try:
                for pr in repo.get_pulls(state=pr_state, sort="updated", direction="desc"):
                    if since is not None and pr.updated_at is not None:
                        if pr.updated_at <= since:
                            # PRs are sorted by updated desc; once we're past `since` we're done
                            break
                    try:
                        yield self._build_pr_doc(repo, pr)
                    except RateLimitExceededException:
                        self._wait_for_rate_limit()
                        yield self._build_pr_doc(repo, pr)
                    except GithubException as exc:
                        logger.warning(
                            "Error building PR doc %s#%s: %s — skipping.",
                            repo.full_name,
                            pr.number,
                            exc,
                        )
            except RateLimitExceededException:
                self._wait_for_rate_limit()
            except GithubException as exc:
                logger.warning(
                    "Error fetching PRs for %s: %s — skipping.", repo.full_name, exc
                )

    def _sync(
        self,
        since: Optional[datetime] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """
        Internal generator: iterate repos and yield batches of ConnectorDocuments.

        *since* is forwarded to ``_iter_repo_documents`` for incremental sync.
        """
        try:
            repos = self._get_repos()
        except RateLimitExceededException:
            self._wait_for_rate_limit()
            repos = self._get_repos()
        except GithubException as exc:
            raise RuntimeError(f"Failed to list GitHub repositories: {exc}") from exc

        logger.info("GitHub connector: syncing %d repository/repositories.", len(repos))

        batch: list[ConnectorDocument] = []
        for repo in repos:
            logger.info("Syncing repo: %s", repo.full_name)
            try:
                for doc in self._iter_repo_documents(repo, since=since):
                    batch.append(doc)
                    if len(batch) >= _BATCH_SIZE:
                        yield batch
                        batch = []
            except Exception as exc:
                logger.warning(
                    "Unexpected error while syncing repo %s: %s — skipping.",
                    repo.full_name,
                    exc,
                )

        if batch:
            yield batch

    # ------------------------------------------------------------------
    # Public BaseConnector interface
    # ------------------------------------------------------------------

    def fetch_all(self) -> Iterator[list[ConnectorDocument]]:
        """Yield all documents from the configured repositories in batches of 50."""
        yield from self._sync(since=None)

    def fetch_updated(
        self,
        since: datetime,
        checkpoint: Optional[dict[str, Any]] = None,
    ) -> Iterator[list[ConnectorDocument]]:
        """Yield documents updated after *since* (incremental sync)."""
        # Prefer the checkpoint timestamp if it is more recent than `since`
        effective_since = since
        if checkpoint and "last_sync_time" in checkpoint:
            try:
                cp_time = datetime.fromisoformat(checkpoint["last_sync_time"])
                if cp_time > since:
                    effective_since = cp_time
            except (ValueError, TypeError):
                pass

        yield from self._sync(since=effective_since)

    def build_checkpoint(self) -> Optional[dict[str, Any]]:
        """Record the current UTC time so the next incremental sync can use it."""
        return {"last_sync_time": datetime.utcnow().isoformat()}
