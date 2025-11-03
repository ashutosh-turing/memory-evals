"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory (where .env is located)
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=False,
    )

    # Application
    app_name: str = Field(default="Memory-Break Orchestrator", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")

    # API Server
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql://user:password@localhost:5432/memory_break_db",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # File Storage
    run_root: str = Field(default="storage", alias="RUN_ROOT")
    max_files_per_task: int = Field(default=50, alias="MAX_FILES_PER_TASK")

    # Agent CLIs
    iflow_bin: str = Field(default="iflow", alias="IFLOW_BIN")
    claude_bin: str = Field(default="claude", alias="CLAUDE_BIN")
    gemini_bin: str = Field(default="gemini", alias="GEMINI_BIN")

    # iFlow Configuration
    iflow_api_key: str | None = Field(default=None, alias="IFLOW_API_KEY")
    iflow_base_url: str = Field(
        default="https://apis.iflow.cn/v1", alias="IFLOW_BASE_URL"
    )
    iflow_model_name: str = Field(default="qwen3-coder-plus", alias="IFLOW_MODEL_NAME")

    # Claude Configuration
    claude_model: str = Field(
        default="claude-sonnet-4-5-20250929", alias="CLAUDE_MODEL"
    )

    # Gemini Configuration
    gemini_model: str = Field(default="gemini-2.5-pro", alias="GEMINI_MODEL")

    # API Keys (for LLM Judge)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    github_token: str | None = Field(
        default=None, alias="GITHUB_TOKEN"
    )  # Optional: For higher rate limits

    # Security
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="ALLOWED_ORIGINS",
    )

    # Task Processing
    task_timeout_seconds: int = Field(
        default=7200, alias="TASK_TIMEOUT_SECONDS"
    )  # 2 hours
    agent_session_timeout: int = Field(
        default=3600, alias="AGENT_SESSION_TIMEOUT"
    )  # 1 hour

    # Agent Token Limits (for fair comparison)
    max_context_tokens: int = Field(
        default=200000, alias="MAX_CONTEXT_TOKENS"
    )  # 200K tokens for all agents
    max_turns: int = Field(
        default=100, alias="MAX_TURNS"
    )  # Maximum deep-dive iterations

    # Compression Detection
    compression_threshold_low: int = Field(
        default=30, alias="COMPRESSION_THRESHOLD_LOW"
    )
    compression_jump_threshold: int = Field(
        default=30, alias="COMPRESSION_JUMP_THRESHOLD"
    )

    # Judge Configuration
    default_judge: str = Field(default="llm", alias="DEFAULT_JUDGE")  # heuristic | llm
    judge_model: str = Field(default="gpt-4o", alias="JUDGE_MODEL")

    # Prompt Generation Configuration
    use_gpt_prompts: bool = Field(
        default=True, alias="USE_GPT_PROMPTS"
    )  # Use GPT for prompt generation
    prompt_model: str = Field(
        default="gpt-4o", alias="PROMPT_MODEL"
    )  # Use GPT-4o which supports temperature
    prompt_temperature: float = Field(
        default=1.0, alias="PROMPT_TEMPERATURE"
    )  # Use default temperature for compatibility
    prompt_max_tokens: int = Field(
        default=4000, alias="PROMPT_MAX_TOKENS"
    )  # Max tokens per prompt

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        return str(self.database_url)

    @property
    def redis_url_str(self) -> str:
        """Get Redis URL as string."""
        return str(self.redis_url)


# Global settings instance
settings = Settings()
