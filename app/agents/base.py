"""Base agent interface and common functionality."""

import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Any
from uuid import UUID

from app.domain.entities import AgentName, AgentRun

logger = logging.getLogger(__name__)


class AgentSession(Protocol):
    """Session information for agent execution."""
    
    task_id: UUID
    agent_run_id: UUID
    repo_dir: Path
    output_dir: Path
    prompts: Dict[str, str]
    timeout: int


class CompressionDetector(ABC):
    """Abstract base class for compression detection strategies."""
    
    @abstractmethod
    def detect_compression(self, session_data: str) -> bool:
        """Detect if compression has occurred based on session data."""
        pass
    
    @abstractmethod
    def should_enter_memory_only(self, session_data: str, previous_state: Dict[str, Any]) -> bool:
        """Determine if agent should enter memory-only mode."""
        pass


class AgentAdapter(ABC):
    """Abstract base class for AI agent adapters."""
    
    def __init__(self, name: AgentName, binary_path: Optional[str] = None):
        self.name = name
        self.binary_path = binary_path or name.value
        self.compression_detector: Optional[CompressionDetector] = None
        self.logger = logging.getLogger(f"agents.{name.value}")
    
    @abstractmethod
    def validate_installation(self) -> bool:
        """Validate that the agent CLI is properly installed."""
        pass
    
    @abstractmethod
    def run_session(
        self,
        session: AgentSession,
    ) -> Dict[str, Any]:
        """
        Run a complete agent session.
        
        Returns:
            Dict containing:
            - artifacts: Dict[str, str] (name -> file_path)
            - stats: Dict[str, str] (execution statistics)
            - compression_detected: bool
            - milestones: List[str]
        """
        pass
    
    @abstractmethod
    def get_version_info(self) -> Dict[str, str]:
        """Get agent version and system information."""
        pass
    
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
    
    def handle_error(self, error: Exception, session: AgentSession) -> Dict[str, Any]:
        """Handle errors during session execution."""
        self.logger.error(f"Error in {self.name.value} session: {error}")
        
        error_artifact_path = session.output_dir / "error.txt"
        with open(error_artifact_path, "w") as f:
            f.write(f"Error: {str(error)}\n")
            f.write(f"Agent: {self.name.value}\n")
            f.write(f"Task ID: {session.task_id}\n")
        
        return {
            "artifacts": {"error": str(error_artifact_path)},
            "stats": {"error": str(error)},
            "compression_detected": False,
            "milestones": ["error"],
        }


class StandardCompressionDetector(CompressionDetector):
    """Standard compression detection implementation."""
    
    def __init__(self, threshold_low: int = 30, jump_threshold: int = 30):
        self.threshold_low = threshold_low
        self.jump_threshold = jump_threshold
    
    def detect_compression(self, session_data: str) -> bool:
        """Detect compression based on context percentage thresholds."""
        # This is a base implementation - specific agents will override
        return False
    
    def should_enter_memory_only(self, session_data: str, previous_state: Dict[str, Any]) -> bool:
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
    pass


class AgentExecutionError(BaseAgentException):
    """Raised when agent execution fails."""
    pass


class AgentTimeoutError(BaseAgentException):
    """Raised when agent execution times out."""
    pass


class AgentValidationError(BaseAgentException):
    """Raised when agent validation fails."""
    pass
