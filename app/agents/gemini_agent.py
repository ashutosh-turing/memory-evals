"""Google Gemini AI agent adapter using Google SDK."""

import asyncio
import logging
from pathlib import Path
from typing import Any

import google.generativeai as genai

from app.agents.base import (
    AgentAdapter,
    AgentCapabilities,
    AgentExecutionError,
    AgentMetadata,
    AgentSession,
)
from app.config import settings
from app.domain.entities import AgentName

logger = logging.getLogger(__name__)


class GeminiAgent(AgentAdapter):
    """Google Gemini AI agent adapter using Google SDK for direct API interaction."""

    def __init__(self):
        super().__init__(AgentName.GEMINI, "gemini")  # No binary needed

        if settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)

        self.model_name = settings.gemini_model
        self.max_tokens = settings.max_context_tokens
        self.max_turns = settings.max_turns
        self.session_timeout = settings.agent_session_timeout

    def validate_installation(self) -> bool:
        """Validate that Google API key is configured."""
        if not settings.google_api_key:
            self.logger.error("Google API key not configured")
            return False

        self.logger.info("Gemini (Google SDK) validation successful")
        return True

    def get_version_info(self) -> dict[str, str]:
        """Get Gemini version and system information."""
        return {
            "model": self.model_name,
            "max_tokens": str(self.max_tokens),
            "api_configured": str(bool(settings.google_api_key)),
            "sdk": "google-generativeai",
        }

    def _load_repo_files(self, repo_dir: Path, max_files: int = 50) -> str:
        """Load repository files into a context string with token limit."""
        self.logger.info(f"Loading repository files from {repo_dir}")

        # Limit initial context to ~50K tokens (leaving room for conversation)
        MAX_CONTEXT_TOKENS = 50000

        # Common code file extensions
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".cs",
            ".scala",
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
            ".html",
            ".css",
        }

        files_content = []
        file_count = 0
        total_tokens = 0

        try:
            for file_path in repo_dir.rglob("*"):
                if file_count >= max_files:
                    break

                # Skip directories and hidden files
                if file_path.is_dir() or file_path.name.startswith("."):
                    continue

                # Skip common non-code directories
                if any(
                    part in file_path.parts
                    for part in [
                        ".git",
                        "node_modules",
                        "__pycache__",
                        "venv",
                        "dist",
                        "build",
                    ]
                ):
                    continue

                # Only include code files
                if file_path.suffix not in code_extensions:
                    continue

                try:
                    relative_path = file_path.relative_to(repo_dir)
                    content = file_path.read_text(encoding="utf-8", errors="ignore")

                    # Estimate tokens (rough: 1 token ~= 4 characters)
                    file_tokens = len(content) // 4

                    # Stop if we would exceed token limit
                    if total_tokens + file_tokens > MAX_CONTEXT_TOKENS:
                        self.logger.info(
                            f"Stopping at {file_count} files to stay within {MAX_CONTEXT_TOKENS} token limit"
                        )
                        break

                    files_content.append(
                        f"### File: {relative_path}\n```{file_path.suffix[1:]}\n{content}\n```\n"
                    )
                    file_count += 1
                    total_tokens += file_tokens

                except Exception as e:
                    self.logger.warning(f"Could not read {file_path}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error loading repository files: {e}")
            return f"Error loading repository: {e}"

        self.logger.info(
            f"Loaded {file_count} files (~{total_tokens} tokens) from repository"
        )

        if not files_content:
            return "No code files found in repository."

        return "# Repository Code\n\n" + "\n\n".join(files_content)

    def run_session(self, session: AgentSession) -> dict[str, Any]:
        """Run complete Gemini session using Google SDK."""
        self.setup_output_directory(session.output_dir)

        # Create transcript file
        transcript_path = session.output_dir / "transcript.txt"

        try:
            # Run async session
            result = asyncio.run(self._run_async_session(session, transcript_path))

            # Add file paths to result
            result["artifacts"]["transcript"] = str(transcript_path)

            return result

        except Exception as e:
            self.logger.error(f"Gemini session failed: {e}", exc_info=True)
            return self.handle_error(e, session)

    async def _run_async_session(
        self, session: AgentSession, transcript_path: Path
    ) -> dict[str, Any]:
        """Run the async Gemini session using Google SDK."""

        milestones = []
        stats = {}
        responses = []
        total_tokens = 0
        hit_limit = False

        try:
            with open(transcript_path, "w", encoding="utf-8") as log_file:
                # Create model instance
                model = genai.GenerativeModel(self.model_name)

                # Phase 1: Load repository context
                self.logger.info("=" * 80)
                self.logger.info("PHASE 1: Loading Repository Context")
                self.logger.info("=" * 80)

                repo_context = self._load_repo_files(session.repo_dir)
                log_file.write(
                    f"Repository Context Loaded: {len(repo_context)} characters\n"
                )
                log_file.write("=" * 80 + "\n\n")

                # Start chat session
                chat = model.start_chat(history=[])

                # Initial context loading
                response = await chat.send_message_async(
                    f"{repo_context}\n\nThis is a code repository. Please analyze it and be ready to answer questions about it."
                )

                if hasattr(response, "usage_metadata"):
                    total_tokens += response.usage_metadata.prompt_token_count
                    total_tokens += response.usage_metadata.candidates_token_count

                log_file.write(f"ASSISTANT: {response.text}\n\n")
                log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                log_file.write("=" * 80 + "\n\n")

                milestones.append("repo_loaded")
                stats["initial_tokens"] = total_tokens

                # Phase 2: Pre-compression prompt
                self.logger.info("=" * 80)
                self.logger.info("PHASE 2: Pre-Compression Analysis")
                self.logger.info("=" * 80)

                response = await chat.send_message_async(
                    session.prompts["precompression"]
                )

                if hasattr(response, "usage_metadata"):
                    total_tokens += response.usage_metadata.prompt_token_count
                    total_tokens += response.usage_metadata.candidates_token_count

                responses.append(
                    {"phase": "pre_compression", "response": response.text}
                )

                log_file.write(f"USER: {session.prompts['precompression']}\n\n")
                log_file.write(f"ASSISTANT: {response.text}\n\n")
                log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                log_file.write("=" * 80 + "\n\n")

                milestones.append("pre_compression")
                stats["pre_compression_tokens"] = total_tokens

                # Phase 3: Deep-dive prompts (loop until token limit)
                self.logger.info("=" * 80)
                self.logger.info("PHASE 3: Deep-Dive Analysis")
                self.logger.info("=" * 80)

                deep_dive_count = 0

                while (
                    deep_dive_count < self.max_turns
                    and total_tokens < self.max_tokens * 0.9
                ):
                    deep_dive_count += 1
                    self.logger.info(f"Deep-dive iteration #{deep_dive_count}")
                    self.logger.info(
                        f"Current tokens: {total_tokens:,} / {self.max_tokens:,} ({total_tokens / self.max_tokens * 100:.1f}%)"
                    )
                    self.logger.info(f"Turn: {deep_dive_count} / {self.max_turns}")

                    try:
                        response = await chat.send_message_async(
                            session.prompts["deepdive"]
                        )

                        if hasattr(response, "usage_metadata"):
                            total_tokens += response.usage_metadata.prompt_token_count
                            total_tokens += (
                                response.usage_metadata.candidates_token_count
                            )

                        responses.append(
                            {
                                "phase": f"deep_dive_{deep_dive_count}",
                                "response": response.text,
                            }
                        )

                        log_file.write(
                            f"USER (Deep-dive #{deep_dive_count}): {session.prompts['deepdive']}\n\n"
                        )
                        log_file.write(f"ASSISTANT: {response.text}\n\n")
                        log_file.write(
                            f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n"
                        )
                        log_file.write("=" * 80 + "\n\n")

                        stats[f"deep_dive_{deep_dive_count}_tokens"] = total_tokens

                    except Exception as e:
                        self.logger.error(
                            f"Deep-dive iteration {deep_dive_count} failed: {e}"
                        )
                        if "token limit" in str(e).lower() or "quota" in str(e).lower():
                            self.logger.info("🔴 Hit Gemini's token/quota limit")
                            hit_limit = True
                            break
                        raise

                milestones.append("deep_dive_complete")
                stats["deep_dive_iterations"] = deep_dive_count

                if total_tokens >= self.max_tokens * 0.9:
                    hit_limit = True
                    self.logger.info(
                        f"🔴 Reached token limit threshold: {total_tokens:,} / {self.max_tokens:,}"
                    )

                # Phase 4: Memory-only evaluation
                self.logger.info("=" * 80)
                self.logger.info("PHASE 4: Memory-Only Evaluation")
                self.logger.info("=" * 80)

                try:
                    response = await chat.send_message_async(
                        session.prompts["memory_only"]
                    )

                    if hasattr(response, "usage_metadata"):
                        total_tokens += response.usage_metadata.prompt_token_count
                        total_tokens += response.usage_metadata.candidates_token_count

                    responses.append(
                        {"phase": "memory_only", "response": response.text}
                    )

                    log_file.write(
                        f"USER (Memory-only): {session.prompts['memory_only']}\n\n"
                    )
                    log_file.write(f"ASSISTANT: {response.text}\n\n")
                    log_file.write(
                        f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n"
                    )
                    log_file.write("=" * 80 + "\n\n")

                    milestones.append("memory_only")

                except Exception as e:
                    self.logger.error(f"Memory-only phase failed: {e}")
                    if "token limit" in str(e).lower() or "quota" in str(e).lower():
                        self.logger.warning(
                            "Cannot continue - token/quota limit exceeded"
                        )
                    else:
                        raise

                # Phase 5: Evaluator questions
                self.logger.info("=" * 80)
                self.logger.info("PHASE 5: Evaluator Questions")
                self.logger.info("=" * 80)

                try:
                    response = await chat.send_message_async(
                        session.prompts["evaluator_set"]
                    )

                    if hasattr(response, "usage_metadata"):
                        total_tokens += response.usage_metadata.prompt_token_count
                        total_tokens += response.usage_metadata.candidates_token_count

                    responses.append({"phase": "evaluation", "response": response.text})

                    log_file.write(
                        f"USER (Evaluation): {session.prompts['evaluator_set']}\n\n"
                    )
                    log_file.write(f"ASSISTANT: {response.text}\n\n")
                    log_file.write(
                        f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n"
                    )
                    log_file.write("=" * 80 + "\n\n")

                    milestones.append("evaluation_complete")

                except Exception as e:
                    self.logger.error(f"Evaluation phase failed: {e}")
                    if "token limit" in str(e).lower() or "quota" in str(e).lower():
                        self.logger.warning(
                            "Cannot continue - token/quota limit exceeded"
                        )
                    else:
                        raise

                milestones.append("session_complete")

        except Exception as e:
            self.logger.error(f"Session error: {e}", exc_info=True)
            raise AgentExecutionError(self.name.value, f"Session error: {e}")

        # Prepare final statistics
        stats.update(
            {
                "total_tokens": str(total_tokens),
                "hit_limit": str(hit_limit),
                "max_tokens_configured": str(self.max_tokens),
                "detection_method": "api_token_tracking",
            }
        )

        return {
            "artifacts": {},  # Will be populated by caller
            "stats": stats,
            "compression_detected": hit_limit,
            "milestones": milestones,
            "responses": responses,
        }


# Agent metadata for registry
GEMINI_CAPABILITIES = AgentCapabilities(
    supports_export=False,
    supports_stats=True,
    supports_compression_detection=True,
    supports_interactive_mode=False,
    max_session_duration=1800,
)

GEMINI_METADATA = AgentMetadata(
    name=AgentName.GEMINI,
    display_name="Google Gemini",
    description="Google Gemini AI agent using native SDK with token tracking",
    version="2.0.0",
    capabilities=GEMINI_CAPABILITIES,
    binary_name="gemini",
    installation_instructions="Configure GOOGLE_API_KEY in .env file",
)
