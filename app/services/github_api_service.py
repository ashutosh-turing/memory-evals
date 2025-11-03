"""GitHub API service for fetching PR data without cloning repositories."""

import base64
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Error when calling GitHub API."""


class GitHubAPIService:
    """Service for interacting with GitHub API."""

    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "memory-break-orchestrator",
        }

        # Add authentication if token is provided
        if hasattr(settings, "github_token") and settings.github_token:
            self.headers["Authorization"] = f"token {settings.github_token}"
        elif hasattr(settings, "github_api_key") and settings.github_api_key:
            self.headers["Authorization"] = f"Bearer {settings.github_api_key}"

        self.logger = logging.getLogger("services.github_api")
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
        """Make HTTP request to GitHub API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method, url, headers=self.headers, **kwargs
                )

                # Handle rate limiting
                if response.status_code == 403:
                    rate_limit_remaining = response.headers.get(
                        "X-RateLimit-Remaining", "0"
                    )
                    if rate_limit_remaining == "0":
                        reset_time = response.headers.get("X-RateLimit-Reset", "0")
                        raise GitHubAPIError(
                            f"GitHub API rate limit exceeded. Resets at: {reset_time}"
                        )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"GitHub API error: {e.response.status_code} - {e.response.text}"
            )
            raise GitHubAPIError(f"GitHub API error: {e.response.status_code}") from e
        except httpx.TimeoutException as e:
            self.logger.error(f"GitHub API timeout: {e}")
            raise GitHubAPIError("GitHub API request timed out") from e
        except Exception as e:
            self.logger.error(f"Unexpected error calling GitHub API: {e}")
            raise GitHubAPIError(f"Failed to call GitHub API: {e}") from e

    def _make_request_sync(
        self, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
        """Synchronous version for compatibility."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._make_request(method, endpoint, **kwargs))

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Get PR information from GitHub API."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"
        return self._make_request_sync("GET", endpoint)

    def get_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Get list of changed files in PR from GitHub API."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/files"
        return self._make_request_sync("GET", endpoint)

    def get_file_contents(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> dict[str, Any]:
        """Get file contents from GitHub API."""
        endpoint = f"repos/{owner}/{repo}/contents/{path}"
        params = {}
        if ref:
            params["ref"] = ref
        return self._make_request_sync("GET", endpoint, params=params)

    def get_pr_commits(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Get commits in PR from GitHub API."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/commits"
        return self._make_request_sync("GET", endpoint)

    def parse_pr_url(self, pr_url: str) -> tuple[str, str, int] | None:
        """Parse GitHub PR URL into owner, repo, and PR number."""
        import re

        # Match: https://github.com/owner/repo/pull/123
        pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.search(pattern, pr_url)

        if not match:
            return None

        owner = match.group(1)
        repo = match.group(2)
        pr_number = int(match.group(3))

        return owner, repo, pr_number

    def fetch_changed_files_contents(
        self, owner: str, repo: str, pr_number: int, max_files: int = 50
    ) -> dict[str, str]:
        """
        Fetch contents of changed files in PR.

        Returns:
            Dict mapping file paths to their contents
        """
        files = self.get_pr_files(owner, repo, pr_number)
        pr_info = self.get_pr_info(owner, repo, pr_number)

        # Get the head SHA for fetching file contents
        head_sha = pr_info.get("head", {}).get("sha")

        file_contents = {}
        for file_info in files[:max_files]:
            file_path = file_info["filename"]

            # Skip deleted files
            if file_info.get("status") == "removed":
                continue

            try:
                # Get file contents from GitHub API
                content_data = self.get_file_contents(owner, repo, file_path, head_sha)

                # Decode base64 content
                if content_data.get("encoding") == "base64":
                    content = base64.b64decode(content_data["content"]).decode("utf-8")
                    file_contents[file_path] = content
                else:
                    # File might be too large, use patch from PR files endpoint
                    patch = file_info.get("patch", "")
                    if patch:
                        file_contents[file_path] = patch

            except Exception as e:
                self.logger.warning(f"Failed to fetch content for {file_path}: {e}")
                # Fallback to patch if available
                patch = file_info.get("patch", "")
                if patch:
                    file_contents[file_path] = patch

        return file_contents


def get_github_api_service() -> GitHubAPIService:
    """Get global GitHub API service instance."""
    global _github_api_service

    if "_github_api_service" not in globals():
        _github_api_service = GitHubAPIService()

    return _github_api_service
