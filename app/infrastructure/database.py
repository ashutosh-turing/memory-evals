"""Database configuration and models using SQLModel."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UUID as SQLUUID
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine

from app.config import settings
from app.domain.entities import AgentName, AgentRunStatus, TaskStatus


class TaskDB(SQLModel, table=True):
    """Database model for Task."""

    __tablename__ = "tasks"

    # Primary fields
    id: UUID = Field(
        default_factory=uuid4, sa_column=Column(SQLUUID(as_uuid=True), primary_key=True)
    )
    pr_url: str = Field(sa_column=Column(String(512), nullable=False))
    repo: str = Field(sa_column=Column(String(256), nullable=False))
    pr_number: int = Field(sa_column=Column(Integer, nullable=False))
    status: TaskStatus = Field(sa_column=Column(String(50), nullable=False))
    max_files: int = Field(default=50, sa_column=Column(Integer, nullable=False))

    # JSON fields
    agents: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rubric: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    changed_files: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    total_files: int | None = Field(
        default=None, sa_column=Column(Integer)
    )  # Total files in PR before filtering

    # Metadata
    prompt_hash: str | None = Field(default=None, sa_column=Column(String(64)))
    error_message: str | None = Field(default=None, sa_column=Column(Text))

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False)
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime))


class AgentRunDB(SQLModel, table=True):
    """Database model for AgentRun."""

    __tablename__ = "agent_runs"

    # Primary fields
    id: UUID = Field(
        default_factory=uuid4, sa_column=Column(SQLUUID(as_uuid=True), primary_key=True)
    )
    task_id: UUID = Field(sa_column=Column(SQLUUID(as_uuid=True), nullable=False))
    agent: AgentName = Field(sa_column=Column(String(50), nullable=False))
    status: AgentRunStatus = Field(sa_column=Column(String(50), nullable=False))

    # JSON fields
    milestones: dict[str, str] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # datetime as ISO string
    artifacts: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    stats: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))

    # Error handling
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    retry_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False)
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime))


class ScoreDB(SQLModel, table=True):
    """Database model for Score."""

    __tablename__ = "scores"

    # Primary fields
    id: UUID = Field(
        default_factory=uuid4, sa_column=Column(SQLUUID(as_uuid=True), primary_key=True)
    )
    agent_run_id: UUID = Field(sa_column=Column(SQLUUID(as_uuid=True), nullable=False))
    task_id: UUID = Field(sa_column=Column(SQLUUID(as_uuid=True), nullable=False))
    agent: AgentName = Field(sa_column=Column(String(50), nullable=False))

    # Scoring
    scores: dict[str, float] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # dimension -> score
    overall_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    passed: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))

    # Judge information
    judge_type: str = Field(sa_column=Column(String(50), nullable=False))
    judge_model: str | None = Field(default=None, sa_column=Column(String(100)))
    rationale: str = Field(default="", sa_column=Column(Text))

    # A/B comparison data
    pre_compression_answers: dict[str, str] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    post_compression_answers: dict[str, str] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False)
    )


class ArtifactDB(SQLModel, table=True):
    """Database model for Artifact."""

    __tablename__ = "artifacts"

    # Primary fields
    id: UUID = Field(
        default_factory=uuid4, sa_column=Column(SQLUUID(as_uuid=True), primary_key=True)
    )
    agent_run_id: UUID = Field(sa_column=Column(SQLUUID(as_uuid=True), nullable=False))
    task_id: UUID = Field(sa_column=Column(SQLUUID(as_uuid=True), nullable=False))
    agent: AgentName = Field(sa_column=Column(String(50), nullable=False))

    # File information
    name: str = Field(sa_column=Column(String(255), nullable=False))
    file_path: str = Field(sa_column=Column(String(1024), nullable=False))
    file_type: str = Field(sa_column=Column(String(50), nullable=False))
    size_bytes: int | None = Field(default=None, sa_column=Column(Integer))
    checksum: str | None = Field(default=None, sa_column=Column(String(64)))

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime, nullable=False)
    )


# Database engine and session management
engine = create_engine(
    settings.database_url_str,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections after 1 hour
)


def create_tables() -> None:
    """Create all database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Get database session - for dependency injection."""
    with Session(engine) as session:
        yield session


class DatabaseManager:
    """Database operations manager."""

    def __init__(self, session: Session):
        self.session = session

    def create_task(self, task_data: dict) -> TaskDB:
        """Create a new task."""
        task = TaskDB(**task_data)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, task_id: UUID) -> TaskDB | None:
        """Get task by ID."""
        return self.session.get(TaskDB, task_id)

    def update_task(self, task_id: UUID, updates: dict) -> TaskDB | None:
        """Update task."""
        task = self.session.get(TaskDB, task_id)
        if not task:
            return None

        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(task)
        return task

    def create_agent_run(self, agent_run_data: dict) -> AgentRunDB:
        """Create a new agent run."""
        agent_run = AgentRunDB(**agent_run_data)
        self.session.add(agent_run)
        self.session.commit()
        self.session.refresh(agent_run)
        return agent_run

    def get_agent_run(self, agent_run_id: UUID) -> AgentRunDB | None:
        """Get agent run by ID."""
        return self.session.get(AgentRunDB, agent_run_id)

    def get_agent_runs_for_task(self, task_id: UUID) -> list[AgentRunDB]:
        """Get all agent runs for a task."""
        from sqlmodel import select

        statement = select(AgentRunDB).where(AgentRunDB.task_id == task_id)
        return list(self.session.exec(statement).all())

    def update_agent_run(self, agent_run_id: UUID, updates: dict) -> AgentRunDB | None:
        """Update agent run."""
        agent_run = self.session.get(AgentRunDB, agent_run_id)
        if not agent_run:
            return None

        for key, value in updates.items():
            if hasattr(agent_run, key):
                setattr(agent_run, key, value)

        agent_run.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(agent_run)
        return agent_run

    def create_score(self, score_data: dict) -> ScoreDB:
        """Create a new score."""
        score = ScoreDB(**score_data)
        self.session.add(score)
        self.session.commit()
        self.session.refresh(score)
        return score

    def create_artifact(self, artifact_data: dict) -> ArtifactDB:
        """Create a new artifact."""
        artifact = ArtifactDB(**artifact_data)
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        return artifact

    def list_tasks(
        self, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> tuple[list[TaskDB], int]:
        """List tasks with pagination and optional status filtering."""
        from sqlmodel import select

        # Build query
        statement = select(TaskDB)

        # Apply status filter if provided
        if status:
            statement = statement.where(TaskDB.status == status)

        # Apply ordering (newest first)
        statement = statement.order_by(TaskDB.created_at.desc())

        # Get total count (before pagination)
        count_statement = select(TaskDB)
        if status:
            count_statement = count_statement.where(TaskDB.status == status)
        total = len(list(self.session.exec(count_statement).all()))

        # Apply pagination
        offset = (page - 1) * page_size
        statement = statement.offset(offset).limit(page_size)

        # Execute query
        tasks = list(self.session.exec(statement).all())

        return tasks, total

    def get_scores_for_agent_run(self, agent_run_id: UUID) -> ScoreDB | None:
        """Get scores for a specific agent run."""
        from sqlmodel import select

        statement = select(ScoreDB).where(ScoreDB.agent_run_id == agent_run_id)
        return self.session.exec(statement).first()
