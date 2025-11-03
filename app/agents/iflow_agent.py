"""iFlow AI agent adapter using Python SDK."""

import asyncio
import logging
import os
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from iflow_sdk import (
    AssistantMessage,
    IFlowClient,
    IFlowOptions,
    PlanMessage,
    StopReason,
    TaskFinishMessage,
    ToolCallMessage,
)

from app.agents.base import (
    AgentAdapter,
    AgentCapabilities,
    AgentExecutionError,
    AgentMetadata,
    AgentSession,
)
from app.config import settings
from app.domain.entities import AgentName
from app.services.task_logger import AgentSessionLogger

logger = logging.getLogger(__name__)


class IFlowAgent(AgentAdapter):
    """iFlow AI agent adapter using Python SDK for direct interaction."""

    def __init__(self):
        super().__init__(AgentName.IFLOW, settings.iflow_bin)
        self.max_tokens = settings.max_context_tokens
        self.max_turns = settings.max_turns
        self.session_timeout = settings.agent_session_timeout
        self.iflow_process = None
        self.port = 8090
        self.iflow_stdout_log = None
        self.iflow_stderr_log = None

    def validate_installation(self) -> bool:
        """Validate that iFlow CLI is installed and working."""
        if not self.check_binary_exists():
            self.logger.error(f"iFlow binary not found: {self.binary_path}")
            return False

        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                self.logger.error(f"iFlow version check failed: {result.stderr}")
                return False

            self.logger.info(f"iFlow validation successful: {result.stdout.strip()}")
            return True

        except Exception as e:
            self.logger.error(f"iFlow validation failed: {e}")
            return False

    def get_version_info(self) -> dict[str, str]:
        """Get iFlow version and system information."""
        version_info = {
            "binary_path": self.binary_path,
            "available": str(self.check_binary_exists()),
        }

        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                version_info["version"] = result.stdout.strip()
            else:
                version_info["version_error"] = result.stderr

        except Exception as e:
            version_info["version_error"] = str(e)

        return version_info

    def _start_iflow_process(self, repo_dir: Path) -> subprocess.Popen:
        """Start iFlow CLI process with ACP mode and token limit."""
        # Validate repo directory exists and is accessible
        if not repo_dir.exists():
            raise AgentExecutionError(
                self.name.value,
                f"Repository directory does not exist: {repo_dir}. "
                "The repo may not have been cloned or copied correctly.",
            )

        if not repo_dir.is_dir():
            raise AgentExecutionError(
                self.name.value,
                f"Repository path is not a directory: {repo_dir}",
            )

        # Check if directory is readable
        if not os.access(repo_dir, os.R_OK):
            raise AgentExecutionError(
                self.name.value,
                f"Repository directory is not readable: {repo_dir}. "
                "Please check file permissions.",
            )

        self.logger.info(
            f"Starting iFlow process in {repo_dir} with {self.max_tokens} token limit"
        )
        self.logger.debug(f"Repository directory exists: {repo_dir.exists()}")
        self.logger.debug(
            f"Repository directory is readable: {os.access(repo_dir, os.R_OK)}"
        )

        # Create log files for iFlow output
        log_dir = repo_dir.parent / "iflow_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stdout_log = log_dir / f"iflow_{timestamp}_stdout.log"
        stderr_log = log_dir / f"iflow_{timestamp}_stderr.log"

        # Open files and keep them open for the duration of the process
        # Note: Cannot use context manager here as files must remain open for subprocess
        stdout_file = open(stdout_log, "w", encoding="utf-8")  # noqa: SIM115
        stderr_file = open(stderr_log, "w", encoding="utf-8")  # noqa: SIM115

        # Store log paths for later access
        self.iflow_stdout_log = stdout_log
        self.iflow_stderr_log = stderr_log

        # Prepare environment variables for iFlow CLI
        # iFlow CLI reads API key from environment variables
        env = os.environ.copy()
        if settings.iflow_api_key:
            env["IFLOW_API_KEY"] = settings.iflow_api_key
            self.logger.debug("IFLOW_API_KEY configured for iFlow process")
        else:
            self.logger.warning(
                "IFLOW_API_KEY not set - iFlow CLI may fail to authenticate"
            )

        # Add other iFlow config as environment variables if needed
        if settings.iflow_base_url:
            env["IFLOW_BASE_URL"] = settings.iflow_base_url
        if settings.iflow_model_name:
            env["IFLOW_MODEL_NAME"] = settings.iflow_model_name

        # Start iFlow with experimental ACP mode and token limit
        # Redirect output to files to avoid blocking
        process = subprocess.Popen(
            [
                self.binary_path,
                "--experimental-acp",
                "--port",
                str(self.port),
                "--max-tokens",
                str(self.max_tokens),
                "--yolo",  # Auto-accept actions
            ],
            cwd=str(repo_dir),
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            env=env,  # Pass environment variables including API key
        )

        self.iflow_process = process
        self.logger.info(f"iFlow process started with PID {process.pid}")
        self.logger.info(f"iFlow stdout log: {stdout_log}")
        self.logger.info(f"iFlow stderr log: {stderr_log}")
        return process

    async def _wait_for_iflow_ready(self, max_attempts: int = 30) -> bool:
        """Wait for iFlow WebSocket server to be ready."""
        for attempt in range(max_attempts):
            # Check if process is still running
            if self.iflow_process and self.iflow_process.poll() is not None:
                # Process has terminated
                exit_code = self.iflow_process.returncode
                self.logger.error(
                    f"iFlow process terminated early (exit code: {exit_code})"
                )

                # Try to read error from stderr log file
                if hasattr(self, "iflow_stderr_log") and self.iflow_stderr_log.exists():
                    try:
                        stderr_content = self.iflow_stderr_log.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        if stderr_content.strip():
                            self.logger.error(f"iFlow stderr: {stderr_content[:500]}")
                        elif (
                            hasattr(self, "iflow_stdout_log")
                            and self.iflow_stdout_log.exists()
                        ):
                            # Check stdout for errors
                            stdout_content = self.iflow_stdout_log.read_text(
                                encoding="utf-8", errors="replace"
                            )
                            if stdout_content.strip():
                                self.logger.error(
                                    f"iFlow stdout: {stdout_content[:500]}"
                                )
                    except Exception as e:
                        self.logger.debug(f"Could not read iFlow log files: {e}")
                else:
                    self.logger.error(
                        "iFlow process terminated early - check stderr log for details"
                    )
                return False

            # Check if port is listening
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", self.port))
                sock.close()
                if result == 0:
                    # Port is open - give WebSocket server a moment to fully initialize
                    # before confirming readiness
                    self.logger.debug(
                        f"Port {self.port} is open, waiting for WebSocket protocol initialization..."
                    )
                    await asyncio.sleep(2)  # Allow WebSocket server to fully initialize
                    self.logger.info(
                        f"iFlow WebSocket server is ready on port {self.port}"
                    )
                    return True
            except Exception as e:
                self.logger.debug(f"Port check attempt {attempt + 1} failed: {e}")

            # Wait before next attempt
            await asyncio.sleep(1)
            if attempt % 5 == 0:  # Log every 5 attempts
                self.logger.debug(
                    f"Waiting for iFlow WebSocket server... (attempt {attempt + 1}/{max_attempts})"
                )

        self.logger.error(
            f"iFlow WebSocket server did not become ready after {max_attempts} attempts"
        )
        return False

    def _get_context_stats(self) -> dict[str, Any] | None:
        """Get context statistics by running /stats model command via subprocess."""
        try:
            # This is a workaround - we'd need to send this through the WebSocket
            # For now, we'll track tokens from the SDK responses
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get context stats: {e}")
            return None

    async def _send_and_collect(
        self,
        client: IFlowClient,
        message: str,
        log_file,
        session_logger: AgentSessionLogger,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Send a message and collect all responses until task finishes."""
        self.logger.info(f"📤 Sending: {message[:100]}...")

        # Log to transcript file
        log_file.write(f"\n{'=' * 80}\n")
        log_file.write(f"[{datetime.now().isoformat()}] USER: {message}\n")
        log_file.write(f"{'=' * 80}\n")
        log_file.flush()

        # Log to UI stream
        session_logger.log_prompt_sent(message, "user_prompt")

        await client.send_message(message)

        response_text = []
        tool_calls = []
        plans = []
        stop_reason = None

        try:
            async for msg in client.receive_messages():
                if isinstance(msg, AssistantMessage):
                    text = msg.chunk.text
                    response_text.append(text)
                    log_file.write(text)
                    log_file.flush()

                elif isinstance(msg, ToolCallMessage):
                    tool_info = {
                        "status": msg.status,
                        "tool_name": (
                            msg.tool_name if hasattr(msg, "tool_name") else None
                        ),
                        "label": msg.label if hasattr(msg, "label") else None,
                    }
                    tool_calls.append(tool_info)
                    log_file.write(f"\n[TOOL CALL: {tool_info}]\n")
                    log_file.flush()

                elif isinstance(msg, PlanMessage):
                    plan_info = {
                        "entries": [
                            {
                                "content": entry.content,
                                "status": entry.status,
                                "priority": (
                                    entry.priority
                                    if hasattr(entry, "priority")
                                    else None
                                ),
                            }
                            for entry in msg.entries
                        ]
                    }
                    plans.append(plan_info)
                    log_file.write(f"\n[PLAN: {len(msg.entries)} entries]\n")
                    log_file.flush()

                elif isinstance(msg, TaskFinishMessage):
                    stop_reason = msg.stop_reason
                    log_file.write(f"\n[TASK FINISHED: {stop_reason}]\n")
                    log_file.flush()
                    break

        except TimeoutError:
            self.logger.warning(f"Timeout waiting for response after {timeout}s")
            stop_reason = "timeout"

        full_response = "".join(response_text)

        # Log response to UI stream
        session_logger.log_agent_response(
            full_response, f"response_{len(tool_calls)}_tools_{len(plans)}_plans"
        )

        return {
            "response": full_response,
            "tool_calls": tool_calls,
            "plans": plans,
            "stop_reason": stop_reason,
            "hit_token_limit": stop_reason == StopReason.MAX_TOKENS,
        }

    def run_session(self, session: AgentSession) -> dict[str, Any]:
        """Run complete iFlow session using SDK."""
        self.setup_output_directory(session.output_dir)

        # Create transcript file
        transcript_path = session.output_dir / "transcript.txt"

        # Create session logger for UI streaming
        session_logger = AgentSessionLogger(session.task_id, "iflow")

        try:
            # Run async session
            result = asyncio.run(
                self._run_async_session(session, transcript_path, session_logger)
            )

            # Add file paths to result
            result["artifacts"]["transcript"] = str(transcript_path)

            # Close session logger
            session_logger.close_session("completed", result.get("artifacts", {}))

            return result

        except Exception as e:
            self.logger.error(f"iFlow session failed: {e}", exc_info=True)
            session_logger.close_session("failed", {"error": str(e)})
            return self.handle_error(e, session)
        finally:
            # Cleanup iFlow process
            if self.iflow_process and self.iflow_process.poll() is None:
                self.logger.info("Terminating iFlow process")
                self.iflow_process.terminate()
                try:
                    self.iflow_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.logger.warning("Force killing iFlow process")
                    self.iflow_process.kill()

    async def _run_async_session(
        self,
        session: AgentSession,
        transcript_path: Path,
        session_logger: AgentSessionLogger,
    ) -> dict[str, Any]:
        """Run the async iFlow session using SDK."""

        milestones = []
        stats = {}
        responses = []
        total_tokens_estimate = 0
        compression_detected = False

        # Start iFlow process
        self._start_iflow_process(session.repo_dir)

        # Wait for iFlow WebSocket server to be ready
        self.logger.info("Waiting for iFlow process to initialize...")
        if not await self._wait_for_iflow_ready():
            raise AgentExecutionError(
                self.name.value,
                "Failed to connect: iFlow process did not start properly or WebSocket server is not ready",
            )
        milestones.append("iflow_started")

        try:
            with open(transcript_path, "w", encoding="utf-8") as log_file:
                # Connect via SDK with retry logic
                options = IFlowOptions(
                    auto_start_process=False,
                    url=f"ws://localhost:{self.port}/acp",
                    timeout=float(self.session_timeout),
                )

                self.logger.info(f"Connecting to iFlow at {options.url}")

                # Retry connection with exponential backoff
                max_connection_attempts = 5
                connection_delay = 1.0
                connected = False
                last_error = None

                for conn_attempt in range(max_connection_attempts):
                    try:
                        # Attempt to create and connect client using context manager
                        async with IFlowClient(options) as client:
                            self.logger.info(
                                f"Successfully connected to iFlow on attempt {conn_attempt + 1}"
                            )
                            milestones.append("sdk_connected")
                            connected = True

                            # Phase 1: Initialize repository with /init
                            self.logger.info("=" * 80)
                            self.logger.info("PHASE 1: Repository Initialization")
                            self.logger.info("=" * 80)

                            init_result = await self._send_and_collect(
                                client, "/init", log_file, session_logger, timeout=600
                            )
                            responses.append({"phase": "init", **init_result})
                            milestones.append("repo_initialized")

                            # Estimate tokens (rough: 1 token ≈ 4 chars)
                            total_tokens_estimate += len(init_result["response"]) // 4
                            stats["init_tokens_estimate"] = total_tokens_estimate

                            # Phase 2: Pre-compression prompt
                            self.logger.info("=" * 80)
                            self.logger.info("PHASE 2: Pre-Compression Analysis")
                            self.logger.info("=" * 80)

                            pre_result = await self._send_and_collect(
                                client,
                                session.prompts.get("pre")
                                or session.prompts.get("precompression", ""),
                                log_file,
                                session_logger,
                                timeout=300,
                            )
                            responses.append({"phase": "pre_compression", **pre_result})
                            milestones.append("pre_compression")

                            total_tokens_estimate += len(pre_result["response"]) // 4
                            stats["pre_compression_tokens_estimate"] = (
                                total_tokens_estimate
                            )

                            # Phase 3: Deep-dive prompts (loop until token limit or compression)
                            self.logger.info("=" * 80)
                            self.logger.info("PHASE 3: Deep-Dive Analysis")
                            self.logger.info("=" * 80)

                            deep_dive_count = 0

                            while deep_dive_count < self.max_turns:
                                deep_dive_count += 1
                                self.logger.info(
                                    f"Deep-dive iteration #{deep_dive_count}"
                                )

                                deep_result = await self._send_and_collect(
                                    client,
                                    session.prompts.get("deep")
                                    or session.prompts.get("deepdive", ""),
                                    log_file,
                                    session_logger,
                                    timeout=300,
                                )
                                responses.append(
                                    {
                                        "phase": f"deep_dive_{deep_dive_count}",
                                        **deep_result,
                                    }
                                )

                                total_tokens_estimate += (
                                    len(deep_result["response"]) // 4
                                )
                                stats[f"deep_dive_{deep_dive_count}_tokens"] = (
                                    total_tokens_estimate
                                )

                                # Log token usage
                                hit_limit = deep_result["hit_token_limit"]
                                self.logger.info(
                                    f"📊 Token estimate: {total_tokens_estimate:,} / {self.max_tokens:,} ({total_tokens_estimate / self.max_tokens * 100:.1f}%)"
                                )
                                self.logger.info(
                                    f"📊 Stop reason: {deep_result.get('stop_reason', 'unknown')} | Hit token limit: {hit_limit}"
                                )
                                self.logger.info(
                                    f"📊 Turn: {deep_dive_count} / {self.max_turns}"
                                )
                                session_logger.log_context_stats(
                                    f"{total_tokens_estimate}/{self.max_tokens}",
                                    f"Tokens: {total_tokens_estimate:,} ({total_tokens_estimate / self.max_tokens * 100:.1f}%)",
                                )

                                # Check if we hit token limit (reported by iFlow SDK)
                                if hit_limit:
                                    self.logger.info(
                                        "🔴 Token limit reached - iFlow will compress context on next interaction"
                                    )
                                    compression_detected = True
                                    break

                                # FALLBACK: Check if our estimate exceeds limit (even if iFlow doesn't report it)
                                if total_tokens_estimate >= self.max_tokens:
                                    self.logger.info(
                                        f"🔴 Token estimate exceeded limit ({total_tokens_estimate:,} >= {self.max_tokens:,}) - proceeding to memory-only evaluation"
                                    )
                                    compression_detected = True
                                    break

                                # Check if approaching limit (90% of max)
                                if total_tokens_estimate > self.max_tokens * 0.9:
                                    self.logger.info(
                                        f"⚠️  Approaching token limit: {total_tokens_estimate:,} / {self.max_tokens:,}"
                                    )

                            milestones.append("deep_dive_complete")
                            stats["deep_dive_iterations"] = deep_dive_count

                            # Phase 4: Memory-only evaluation
                            self.logger.info("=" * 80)
                            self.logger.info("PHASE 4: Memory-Only Evaluation")
                            self.logger.info("=" * 80)

                            memory_result = await self._send_and_collect(
                                client,
                                session.prompts["memory_only"],
                                log_file,
                                session_logger,
                                timeout=300,
                            )
                            responses.append({"phase": "memory_only", **memory_result})
                            milestones.append("memory_only")

                            # Phase 5: Evaluator questions
                            self.logger.info("=" * 80)
                            self.logger.info("PHASE 5: Evaluator Questions")
                            self.logger.info("=" * 80)

                            eval_result = await self._send_and_collect(
                                client,
                                session.prompts.get("eval")
                                or session.prompts.get("evaluator_set", ""),
                                log_file,
                                session_logger,
                                timeout=300,
                            )
                            responses.append({"phase": "evaluation", **eval_result})
                            milestones.append("evaluation_complete")

                            milestones.append("session_complete")
                            break  # Successfully completed session, exit retry loop

                    except Exception as conn_error:
                        last_error = conn_error
                        if conn_attempt < max_connection_attempts - 1:
                            wait_time = connection_delay * (2**conn_attempt)
                            self.logger.warning(
                                f"Connection attempt {conn_attempt + 1} failed: {conn_error}. "
                                f"Retrying in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            # Last attempt failed
                            self.logger.error(
                                f"Failed to connect after {max_connection_attempts} attempts: {conn_error}"
                            )
                            raise AgentExecutionError(
                                self.name.value,
                                f"Failed to connect: Failed to initialize protocol: {conn_error}",
                            ) from conn_error

                if not connected:
                    raise AgentExecutionError(
                        self.name.value,
                        f"Failed to connect: Could not establish connection to iFlow WebSocket server. Last error: {last_error}",
                    )

        except Exception as e:
            self.logger.error(f"Session error: {e}", exc_info=True)
            raise AgentExecutionError(self.name.value, f"Session error: {e}") from e

        # Prepare final statistics
        stats.update(
            {
                "compression_detected": str(compression_detected),
                "total_tokens_estimate": str(total_tokens_estimate),
                "detection_method": "token_limit_based",
                "max_tokens_configured": str(self.max_tokens),
            }
        )

        return {
            "artifacts": {},  # Will be populated by caller
            "stats": stats,
            "compression_detected": compression_detected,
            "milestones": milestones,
            "responses": responses,
        }


# Agent metadata for registry
IFLOW_CAPABILITIES = AgentCapabilities(
    supports_export=True,
    supports_stats=True,
    supports_compression_detection=True,
    supports_interactive_mode=True,
    max_session_duration=3600,
)

IFLOW_METADATA = AgentMetadata(
    name=AgentName.IFLOW,
    display_name="iFlow AI",
    description="iFlow AI agent with automatic memory compression using Python SDK",
    version="2.0.0",
    capabilities=IFLOW_CAPABILITIES,
    binary_name="iflow",
    installation_instructions="Install via: npm install -g @iflow-ai/iflow-cli && pip install iflow-cli-sdk",
)
