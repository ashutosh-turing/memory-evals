"""Domain entities representing core business concepts."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class TaskStatus(str, Enum):
    """Task execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    JUDGING = "judging"
    DONE = "done"
    ERROR = "error"


class AgentRunStatus(str, Enum):
    """Agent run execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    MEMORY_ONLY = "memory_only"
    EVALUATING = "evaluating"
    DONE = "done"
    ERROR = "error"


class AgentName(str, Enum):
    """Supported AI agents."""

    IFLOW = "iflow"
    CLAUDE = "claude"
    GEMINI = "gemini"


class RubricDimension(str, Enum):
    """Evaluation rubric dimensions."""

    AR = "AR"  # Accurate Retrieval - Recall
    TTL = "TTL"  # Test-Time Learning - Adapt
    LRU = "LRU"  # Long-Range Understanding - Connect
    SF = "SF"  # Selective Forgetting - Update/Forget


class Task(BaseModel):
    """Memory-break evaluation task."""

    id: UUID = Field(default_factory=uuid4)
    pr_url: HttpUrl
    repo: str
    pr_number: int
    agents: list[AgentName]
    rubric: list[RubricDimension] = Field(default_factory=lambda: list(RubricDimension))
    status: TaskStatus = TaskStatus.QUEUED
    max_files: int = Field(default=50, ge=1, le=1000)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Metadata
    changed_files: list[str] = Field(default_factory=list)
    prompt_hash: str | None = None
    error_message: str | None = None

    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_judging(self) -> None:
        """Mark task as in judging phase."""
        self.status = TaskStatus.JUDGING
        self.updated_at = datetime.utcnow()

    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.DONE
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_error(self, error_message: str) -> None:
        """Mark task as errored."""
        self.status = TaskStatus.ERROR
        self.error_message = error_message
        self.updated_at = datetime.utcnow()


class AgentRun(BaseModel):
    """Individual agent execution within a task."""

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    agent: AgentName
    status: AgentRunStatus = AgentRunStatus.QUEUED

    # Execution milestones
    milestones: dict[str, datetime] = Field(default_factory=dict)

    # Artifacts and outputs
    artifacts: dict[str, str] = Field(default_factory=dict)  # name -> file path
    stats: dict[str, str] = Field(default_factory=dict)  # execution statistics

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error handling
    error_message: str | None = None
    retry_count: int = 0

    def add_milestone(self, name: str) -> None:
        """Add execution milestone."""
        self.milestones[name] = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_artifact(self, name: str, file_path: str) -> None:
        """Add artifact file path."""
        self.artifacts[name] = file_path
        self.updated_at = datetime.utcnow()

    def add_stat(self, key: str, value: str) -> None:
        """Add execution statistic."""
        self.stats[key] = value
        self.updated_at = datetime.utcnow()

    def mark_started(self) -> None:
        """Mark agent run as started."""
        self.status = AgentRunStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.add_milestone("started")

    def mark_memory_only(self) -> None:
        """Mark agent run as entered memory-only mode."""
        self.status = AgentRunStatus.MEMORY_ONLY
        self.add_milestone("memory_only")

    def mark_evaluating(self) -> None:
        """Mark agent run as in evaluation phase."""
        self.status = AgentRunStatus.EVALUATING
        self.add_milestone("evaluating")

    def mark_completed(self) -> None:
        """Mark agent run as completed."""
        self.status = AgentRunStatus.DONE
        self.completed_at = datetime.utcnow()
        self.add_milestone("completed")

    def mark_error(self, error_message: str) -> None:
        """Mark agent run as errored."""
        self.status = AgentRunStatus.ERROR
        self.error_message = error_message
        self.updated_at = datetime.utcnow()


class Score(BaseModel):
    """Evaluation score for an agent run."""

    id: UUID = Field(default_factory=uuid4)
    agent_run_id: UUID
    task_id: UUID
    agent: AgentName

    # Scoring
    scores: dict[RubricDimension, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = False

    # Judge information
    judge_type: str  # "heuristic" or "llm"
    judge_model: str | None = None
    rationale: str = ""

    # A/B comparison data
    pre_compression_answers: dict[str, str] = Field(default_factory=dict)
    post_compression_answers: dict[str, str] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def calculate_overall_score(self) -> None:
        """Calculate overall score and pass/fail status."""
        if not self.scores:
            self.overall_score = 0.0
            self.passed = False
            return

        self.overall_score = sum(self.scores.values()) / len(self.scores)
        # Pass if >= 3/4 dimensions score >= 0.5 (or similar threshold)
        passing_scores = sum(1 for score in self.scores.values() if score >= 0.5)
        self.passed = passing_scores >= max(3, len(self.scores) * 0.75)


class Artifact(BaseModel):
    """File artifact generated during agent execution."""

    id: UUID = Field(default_factory=uuid4)
    agent_run_id: UUID
    task_id: UUID
    agent: AgentName

    # File information
    name: str
    file_path: str
    file_type: str  # "transcript", "export", "scores", etc.
    size_bytes: int | None = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: str | None = None
