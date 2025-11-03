"""GitHub Pull Request service for cloning and analyzing PRs."""

import logging
import shutil
from pathlib import Path

from git import GitCommandError, Repo

from app.config import settings

logger = logging.getLogger(__name__)


class PRAnalysisResult:
    """Result of PR analysis containing repo info and changed files."""

    def __init__(
        self,
        repo_path: Path,
        owner: str,
        repo_name: str,
        pr_number: int,
        changed_files: list[str],
        base_branch: str,
        head_branch: str,
        commit_sha: str,
    ):
        self.repo_path = repo_path
        self.owner = owner
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.changed_files = changed_files
        self.base_branch = base_branch
        self.head_branch = head_branch
        self.commit_sha = commit_sha

    @property
    def repo_full_name(self) -> str:
        """Get full repository name."""
        return f"{self.owner}/{self.repo_name}"

    def __str__(self) -> str:
        return f"PR {self.pr_number} in {self.repo_full_name}: {len(self.changed_files)} files changed"


class PRServiceError(Exception):
    """Base exception for PR service errors."""


class PRCloneError(PRServiceError):
    """Error during repository cloning."""


class PRAnalysisError(PRServiceError):
    """Error during PR analysis."""


class PRService:
    """Service for handling GitHub Pull Request operations."""

    def __init__(self, run_root: str | None = None):
        # Ensure run_root is always a Path object
        if run_root:
            self.run_root = Path(str(run_root)).expanduser()
        else:
            self.run_root = Path(str(settings.run_root)).expanduser()
        self.max_files = settings.max_files_per_task
        self.logger = logging.getLogger("services.pr")

    def process_pr(self, pr_url: str, task_id: str) -> PRAnalysisResult:
        """
        Process a GitHub PR: clone repo and analyze changes.

        Args:
            pr_url: GitHub PR URL (https://github.com/owner/repo/pull/number)
            task_id: Unique task identifier

        Returns:
            PRAnalysisResult containing master repo path and changed files

        Raises:
            PRServiceError: If PR processing fails
        """
        self.logger.info(f"Processing PR: {pr_url}")

        # Parse PR URL
        pr_info = self._parse_pr_url(pr_url)
        if not pr_info:
            raise PRServiceError(f"Invalid GitHub PR URL: {pr_url}")

        owner, repo_name, pr_number = pr_info

        # Create task workspace with master repo
        task_dir = self.run_root / task_id
        pr_dir = task_dir / "pr"
        master_repo_path = pr_dir / "master" / repo_name

        try:
            # Clone repository to master location
            self._clone_repository(owner, repo_name, master_repo_path)

            # Analyze PR changes
            changed_files, base_branch, head_branch, commit_sha = (
                self._analyze_pr_changes(master_repo_path, pr_number)
            )

            # Filter and validate files
            filtered_files = self._filter_changed_files(changed_files, master_repo_path)

            self.logger.info(
                f"Successfully processed PR {pr_number}: "
                f"{len(filtered_files)}/{len(changed_files)} files selected"
            )

            return PRAnalysisResult(
                repo_path=master_repo_path,  # This is the master copy
                owner=owner,
                repo_name=repo_name,
                pr_number=pr_number,
                changed_files=filtered_files,
                base_branch=base_branch,
                head_branch=head_branch,
                commit_sha=commit_sha,
            )

        except Exception as e:
            self.logger.error(f"Failed to process PR {pr_url}: {e}")
            # Cleanup on failure
            if task_dir.exists():
                try:
                    shutil.rmtree(task_dir)
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to cleanup {task_dir}: {cleanup_e}")
            raise PRServiceError(f"PR processing failed: {e}") from e

    def create_agent_repo_copy(
        self, task_id: str, agent_name: str, agent_run_id: str, master_repo_path: Path
    ) -> Path:
        """
        Create an isolated repository copy for a specific agent.

        Args:
            task_id: Task identifier
            agent_name: Name of the agent (iflow, claude, gemini)
            agent_run_id: Unique agent run identifier
            master_repo_path: Path to the master repository copy

        Returns:
            Path to the agent's isolated repository copy

        Raises:
            PRServiceError: If copying fails
        """

        # Create agent-specific repository path
        task_dir = self.run_root / task_id
        agent_repo_path = task_dir / "agents" / agent_name / "repo"

        try:
            # Ensure parent directory exists
            agent_repo_path.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing agent repo if it exists
            if agent_repo_path.exists():
                shutil.rmtree(agent_repo_path)

            # Copy master repository to agent's workspace
            self.logger.info(
                f"Creating isolated repo copy for {agent_name}: {agent_repo_path}"
            )
            shutil.copytree(
                src=master_repo_path,
                dst=agent_repo_path,
                symlinks=False,
                ignore=shutil.ignore_patterns(
                    ".git"
                ),  # Skip .git directory for efficiency
                dirs_exist_ok=True,
            )

            self.logger.info(
                f"Successfully created isolated repo for {agent_name}: {agent_repo_path}"
            )
            return agent_repo_path

        except Exception as e:
            self.logger.error(f"Failed to create agent repo copy for {agent_name}: {e}")
            raise PRServiceError(
                f"Failed to create isolated repo for {agent_name}: {e}"
            )

    def cleanup_task_workspace(self, task_id: str) -> None:
        """Clean up task workspace directory."""
        task_dir = self.run_root / task_id

        if task_dir.exists():
            try:
                shutil.rmtree(task_dir)
                self.logger.info(f"Cleaned up task workspace: {task_dir}")
            except Exception as e:
                self.logger.error(f"Failed to cleanup task workspace {task_dir}: {e}")
        else:
            self.logger.debug(f"Task workspace not found: {task_dir}")

    def get_file_content(
        self, repo_path: Path, file_path: str, encoding: str = "utf-8"
    ) -> str:
        """Get content of a specific file from the repository."""
        full_path = repo_path / file_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        try:
            with open(full_path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            try:
                with open(full_path, encoding="latin-1") as f:
                    return f.read()
            except Exception as e:
                raise ValueError(f"Failed to read file {file_path}: {e}")

    def _parse_pr_url(self, pr_url: str) -> tuple[str, str, int] | None:
        """Parse GitHub PR URL to extract owner, repo, and PR number."""
        import re

        # Match GitHub PR URL pattern
        pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.match(pattern, pr_url.strip())

        if not match:
            return None

        owner = match.group(1)
        repo_name = match.group(2)
        pr_number = int(match.group(3))

        return owner, repo_name, pr_number

    def _clone_repository(self, owner: str, repo_name: str, repo_path: Path) -> None:
        """Clone GitHub repository to local path."""

        # Ensure repo_path is absolute
        if not repo_path.is_absolute():
            repo_path = repo_path.resolve()

        # Create all parent directories
        repo_path.parent.mkdir(parents=True, exist_ok=True)

        # Verify parent directory was created
        if not repo_path.parent.exists():
            raise PRCloneError(f"Failed to create parent directory: {repo_path.parent}")

        # Remove existing directory if it exists
        if repo_path.exists():
            shutil.rmtree(repo_path)

        # GitHub repository URL
        repo_url = f"https://github.com/{owner}/{repo_name}.git"

        try:
            self.logger.info(f"Cloning repository: {repo_url}")

            # Clone with minimal history for efficiency
            repo = Repo.clone_from(
                repo_url,
                str(repo_path),
                depth=1,  # Shallow clone
                single_branch=True,  # Only default branch initially
                progress=None,  # Disable progress reporting
            )

            # Fetch PR refs so we can access the PR
            origin = repo.remotes.origin

            # Fetch all refs to get PR information
            try:
                origin.fetch("+refs/pull/*/head:refs/remotes/origin/pr/*")
                self.logger.debug("Fetched PR references")
            except GitCommandError as e:
                self.logger.warning(f"Failed to fetch PR refs: {e}")
                # Continue without PR refs - we'll try to get PR info differently

            self.logger.info(f"Successfully cloned {repo_url} to {repo_path}")

        except GitCommandError as e:
            self.logger.error(f"Git clone failed: {e}")
            raise PRCloneError(f"Failed to clone repository {repo_url}: {e}")
        except Exception as e:
            self.logger.error(f"Repository clone failed: {e}")
            raise PRCloneError(f"Failed to clone repository: {e}")

    def _analyze_pr_changes(
        self, repo_path: Path, pr_number: int
    ) -> tuple[list[str], str, str, str]:
        """
        Analyze PR to find changed files.

        Returns:
            Tuple of (changed_files, base_branch, head_branch, commit_sha)
        """
        try:
            repo = Repo(str(repo_path))

            # Detect the actual default branch (main, master, or others)
            base_branch = self._get_default_branch(repo)

            # Try to get PR information via GitHub API or git commands
            changed_files = []
            head_branch = f"pr-{pr_number}"
            commit_sha = str(repo.head.commit)

            # Method 1: Try to use PR refs if available
            try:
                pr_ref = f"refs/remotes/origin/pr/{pr_number}"
                if pr_ref in [ref.name for ref in repo.refs]:
                    # Get diff between PR and detected base branch
                    pr_commit = repo.refs[pr_ref].commit
                    base_ref = f"refs/remotes/origin/{base_branch}"

                    if base_ref in [ref.name for ref in repo.refs]:
                        base_commit = repo.refs[base_ref].commit

                        diff = base_commit.diff(pr_commit)
                        changed_files = [item.a_path or item.b_path for item in diff]

                        commit_sha = str(pr_commit)
                        head_branch = f"pr-{pr_number}"

                        self.logger.debug(
                            f"Found {len(changed_files)} changed files via PR refs (base: {base_branch})"
                        )
                    else:
                        self.logger.warning(
                            f"Base branch {base_branch} not found in refs, falling back"
                        )
                        raise Exception("Base branch not found")

            except Exception as e:
                self.logger.debug(f"PR refs method failed: {e}")

                # Method 2: Fallback to recent commits analysis
                try:
                    # Get recent commits and their changes
                    commits = list(repo.iter_commits(max_count=10))
                    all_changed_files = set()

                    for commit in commits:
                        if commit.parents:  # Skip merge commits without parents
                            diff = commit.parents[0].diff(commit)
                            for item in diff:
                                file_path = item.a_path or item.b_path
                                if file_path:
                                    all_changed_files.add(file_path)

                    changed_files = list(all_changed_files)
                    self.logger.debug(
                        f"Found {len(changed_files)} changed files via commit analysis"
                    )

                except Exception as e2:
                    self.logger.debug(f"Commit analysis failed: {e2}")

                    # Method 3: Final fallback - use all source files
                    changed_files = self._get_source_files(repo_path)
                    self.logger.warning(
                        f"Using all source files as fallback: {len(changed_files)} files"
                    )

            # Ensure we have some files
            if not changed_files:
                changed_files = self._get_source_files(repo_path)
                self.logger.warning("No changed files found, using all source files")

            return changed_files, base_branch, head_branch, commit_sha

        except Exception as e:
            self.logger.error(f"PR analysis failed: {e}")
            raise PRAnalysisError(f"Failed to analyze PR {pr_number}: {e}")

    def _get_source_files(self, repo_path: Path) -> list[str]:
        """Get all source code files in the repository as fallback."""
        source_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".cs",
            ".php",
            ".rb",
            ".go",
            ".rs",
            ".kt",
            ".swift",
            ".scala",
            ".sql",
            ".html",
            ".css",
            ".scss",
            ".less",
            ".vue",
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".toml",
            ".ini",
            ".cfg",
        }

        source_files = []

        for file_path in repo_path.rglob("*"):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in source_extensions
                and not self._is_ignored_path(file_path, repo_path)
            ):
                relative_path = file_path.relative_to(repo_path)
                source_files.append(str(relative_path))

        return source_files

    def _filter_changed_files(
        self, changed_files: list[str], repo_path: Path
    ) -> list[str]:
        """Filter and validate changed files."""

        filtered_files = []

        for file_path in changed_files:
            full_path = repo_path / file_path

            # Skip if file doesn't exist (might be deleted)
            if not full_path.exists() or not full_path.is_file():
                continue

            # Skip ignored paths
            if self._is_ignored_path(full_path, repo_path):
                continue

            # Skip binary files
            if self._is_binary_file(full_path):
                continue

            # Skip very large files (>1MB)
            if full_path.stat().st_size > 1024 * 1024:
                self.logger.debug(f"Skipping large file: {file_path}")
                continue

            filtered_files.append(file_path)

            # Limit number of files
            if len(filtered_files) >= self.max_files:
                self.logger.warning(
                    f"Reached max files limit ({self.max_files}), truncating"
                )
                break

        return filtered_files

    def _is_ignored_path(self, file_path: Path, repo_path: Path) -> bool:
        """Check if file path should be ignored."""
        relative_path = file_path.relative_to(repo_path)
        path_str = str(relative_path).lower()

        # Ignored directories
        ignored_dirs = {
            "node_modules",
            ".git",
            ".svn",
            ".hg",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            "venv",
            "env",
            "build",
            "dist",
            "target",
            "bin",
            "obj",
            ".idea",
            ".vscode",
            "coverage",
            ".coverage",
            ".nyc_output",
        }

        # Check if any parent directory is ignored
        for part in relative_path.parts:
            if part.lower() in ignored_dirs:
                return True

        # Ignored file patterns
        ignored_patterns = [
            ".min.js",
            ".min.css",
            ".bundle.js",
            ".bundle.css",
            "package-lock.json",
            "yarn.lock",
            "composer.lock",
            ".log",
            ".tmp",
            ".temp",
            ".cache",
        ]

        for pattern in ignored_patterns:
            if pattern in path_str:
                return True

        # Ignored extensions
        ignored_extensions = {
            ".pyc",
            ".pyo",
            ".class",
            ".o",
            ".obj",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            ".jar",
            ".war",
            ".tar",
            ".gz",
            ".zip",
            ".rar",
            ".7z",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".svg",
            ".mp4",
            ".avi",
            ".mov",
            ".mp3",
            ".wav",
            ".flac",
        }

        if file_path.suffix.lower() in ignored_extensions:
            return True

        return False

    def _get_default_branch(self, repo: Repo) -> str:
        """
        Detect the actual default branch of the repository.

        Args:
            repo: GitPython Repo object

        Returns:
            Name of the default branch (main, master, develop, etc.)
        """
        try:
            # Method 1: Check if HEAD points to a specific branch
            try:
                default_branch = repo.active_branch.name
                self.logger.debug(
                    f"Default branch detected via active_branch: {default_branch}"
                )
                return default_branch
            except Exception:
                pass

            # Method 2: Check remote refs for common default branches
            remote_refs = [
                ref.name
                for ref in repo.refs
                if ref.name.startswith("refs/remotes/origin/")
            ]

            # Priority order for common default branches
            for candidate in ["main", "master", "develop", "dev"]:
                candidate_ref = f"refs/remotes/origin/{candidate}"
                if candidate_ref in remote_refs:
                    self.logger.debug(
                        f"Default branch detected via remote refs: {candidate}"
                    )
                    return candidate

            # Method 3: Try to get the default from git symbolic-ref
            try:
                # This should give us something like 'refs/heads/main'
                symbolic_ref = repo.git.symbolic_ref("HEAD")
                if symbolic_ref.startswith("refs/heads/"):
                    branch_name = symbolic_ref.replace("refs/heads/", "")
                    self.logger.debug(
                        f"Default branch detected via symbolic-ref: {branch_name}"
                    )
                    return branch_name
            except Exception:
                pass

            # Method 4: Use the first remote branch as fallback
            if remote_refs:
                # Get the branch name from the first remote ref
                first_ref = remote_refs[0]
                if first_ref.startswith("refs/remotes/origin/"):
                    fallback_branch = first_ref.replace("refs/remotes/origin/", "")
                    # Skip PR refs
                    if not fallback_branch.startswith("pr/"):
                        self.logger.debug(
                            f"Default branch fallback to first remote: {fallback_branch}"
                        )
                        return fallback_branch

            # Final fallback - assume 'main' (modern default)
            self.logger.warning("Could not detect default branch, assuming 'main'")
            return "main"

        except Exception as e:
            self.logger.warning(f"Error detecting default branch: {e}, assuming 'main'")
            return "main"

    def _is_binary_file(self, file_path: Path) -> bool:
        """Check if file is binary."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)

            # Check for null bytes (common in binary files)
            if b"\x00" in chunk:
                return True

            # Check text/binary ratio
            text_chars = sum(
                1 for byte in chunk if 32 <= byte <= 126 or byte in (9, 10, 13)
            )
            if len(chunk) > 0 and text_chars / len(chunk) < 0.95:
                return True

        except Exception:
            # If we can't read the file, consider it binary
            return True

        return False
