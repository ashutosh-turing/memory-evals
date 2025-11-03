"""Base agent interface and common functionality."""

import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from app.domain.entities import AgentName

logger = logging.getLogger(__name__)


class AgentSession(Protocol):
    """Session information for agent execution."""

    task_id: UUID
    agent_run_id: UUID
    repo_dir: Path
    output_dir: Path
    prompts: dict[str, str]
    timeout: int


class CompressionDetector(ABC):
    """Abstract base class for compression detection strategies."""

    @abstractmethod
    def detect_compression(self, session_data: str) -> bool:
        """Detect if compression has occurred based on session data."""

    @abstractmethod
    def should_enter_memory_only(
        self, session_data: str, previous_state: dict[str, Any]
    ) -> bool:
        """Determine if agent should enter memory-only mode."""


class AgentAdapter(ABC):
    """Abstract base class for AI agent adapters."""

    def __init__(self, name: AgentName, binary_path: str | None = None):
        self.name = name
        self.binary_path = binary_path or name.value
        self.compression_detector: CompressionDetector | None = None
        self.logger = logging.getLogger(f"agents.{name.value}")

    @abstractmethod
    def validate_installation(self) -> bool:
        """Validate that the agent CLI is properly installed."""

    @abstractmethod
    def run_session(
        self,
        session: AgentSession,
    ) -> dict[str, Any]:
        """
        Run a complete agent session.

        Returns:
            Dict containing:
            - artifacts: Dict[str, str] (name -> file_path)
            - stats: Dict[str, str] (execution statistics)
            - compression_detected: bool
            - milestones: List[str]
        """

    @abstractmethod
    def get_version_info(self) -> dict[str, str]:
        """Get agent version and system information."""

    def check_binary_exists(self) -> bool:
        """Check if the agent binary exists in PATH."""
        return shutil.which(self.binary_path) is not None

    def setup_output_directory(self, output_dir: Path) -> None:
        """Setup output directory for agent artifacts."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created output directory: {output_dir}")

    def cleanup_session(self, session: AgentSession) -> None:
        """Cleanup after session completion."""
        # Default implementation - can be overridden
        self.logger.info(f"Session cleanup completed for {self.name.value}")

    def handle_error(self, error: Exception, session: AgentSession) -> dict[str, Any]:
        """Handle errors during session execution."""
        self.logger.error(f"Error in {self.name.value} session: {error}")

        error_artifact_path = session.output_dir / "error.txt"
        with open(error_artifact_path, "w") as f:
            f.write(f"Error: {error!s}\n")
            f.write(f"Agent: {self.name.value}\n")
            f.write(f"Task ID: {session.task_id}\n")

        return {
            "artifacts": {"error": str(error_artifact_path)},
            "stats": {"error": str(error)},
            "compression_detected": False,
            "milestones": ["error"],
        }

    async def execute_evaluation(self, eval_params: dict[str, Any]) -> dict[str, Any]:
        """
        Wrapper method for container-based execution.
        Converts simple eval_params to AgentSession and calls run_session().

        Args:
            eval_params: Dictionary containing:
                - pr_url: str
                - workspace_dir: str (path to cloned repo)
                - prompts: Dict[str, str] (precompression, deepdive, memory_only, evaluator_set)
                - max_files: int (optional)
                - rubric: List[str] (optional)
                - timeout_seconds: int (optional)

        Returns:
            Dict containing execution results
        """
        from uuid import uuid4

        # Map prompt keys from service format to agent format
        prompts = eval_params.get("prompts", {})
        mapped_prompts = {
            "pre": prompts.get("precompression", ""),
            "deep": prompts.get("deepdive", ""),
            "memory_only": prompts.get("memory_only", ""),
            "eval": prompts.get("evaluator_set", ""),
        }

        # Create a simple AgentSession-like object
        class SimpleSession:
            def __init__(self, params, prompts_mapped):
                self.task_id = uuid4()
                self.agent_run_id = uuid4()
                self.repo_dir = Path(params["workspace_dir"])
                self.output_dir = self.repo_dir.parent / "output"
                self.prompts = prompts_mapped
                self.timeout = params.get("timeout_seconds", 1800)

        session = SimpleSession(eval_params, mapped_prompts)

        # Call the existing run_session method
        result = self.run_session(session)

        return result


class StandardCompressionDetector(CompressionDetector):
    """Standard compression detection implementation."""

    def __init__(self, threshold_low: int = 30, jump_threshold: int = 30):
        self.threshold_low = threshold_low
        self.jump_threshold = jump_threshold

    def detect_compression(self, session_data: str) -> bool:
        """Detect compression based on context percentage thresholds."""
        # This is a base implementation - specific agents will override
        return False

    def should_enter_memory_only(
        self, session_data: str, previous_state: dict[str, Any]
    ) -> bool:
        """Determine if should enter memory-only mode."""
        return self.detect_compression(session_data)


class AgentCapabilities:
    """Agent capabilities and feature flags."""

    def __init__(
        self,
        supports_export: bool = False,
        supports_stats: bool = False,
        supports_compression_detection: bool = False,
        supports_interactive_mode: bool = False,
        max_session_duration: int = 1800,
    ):
        self.supports_export = supports_export
        self.supports_stats = supports_stats
        self.supports_compression_detection = supports_compression_detection
        self.supports_interactive_mode = supports_interactive_mode
        self.max_session_duration = max_session_duration


class AgentMetadata:
    """Agent metadata for registry and discovery."""

    def __init__(
        self,
        name: AgentName,
        display_name: str,
        description: str,
        version: str,
        capabilities: AgentCapabilities,
        binary_name: str,
        installation_instructions: str = "",
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.version = version
        self.capabilities = capabilities
        self.binary_name = binary_name
        self.installation_instructions = installation_instructions


class BaseAgentException(Exception):
    """Base exception for agent-related errors."""

    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        self.message = message
        super().__init__(f"[{agent_name}] {message}")


class AgentNotFoundError(BaseAgentException):
    """Raised when agent binary is not found."""


class AgentExecutionError(BaseAgentException):
    """Raised when agent execution fails."""


class AgentTimeoutError(BaseAgentException):
    """Raised when agent execution times out."""


class AgentValidationError(BaseAgentException):
    """Raised when agent validation fails."""
