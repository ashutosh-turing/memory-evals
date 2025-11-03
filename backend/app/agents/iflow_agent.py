"""iFlow AI agent adapter using Python SDK."""

import asyncio
import logging
import subprocess
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from iflow_sdk import IFlowClient, IFlowOptions, AssistantMessage, TaskFinishMessage, StopReason, ToolCallMessage, PlanMessage

from app.domain.entities import AgentName
from app.agents.base import (
    AgentAdapter, AgentSession, CompressionDetector, AgentCapabilities,
    AgentMetadata, AgentNotFoundError, AgentExecutionError, AgentTimeoutError
)
from app.config import settings
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
    
    def validate_installation(self) -> bool:
        """Validate that iFlow CLI is installed and working."""
        if not self.check_binary_exists():
            self.logger.error(f"iFlow binary not found: {self.binary_path}")
            return False
        
        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.logger.error(f"iFlow version check failed: {result.stderr}")
                return False
            
            self.logger.info(f"iFlow validation successful: {result.stdout.strip()}")
            return True
            
        except Exception as e:
            self.logger.error(f"iFlow validation failed: {e}")
            return False
    
    def get_version_info(self) -> Dict[str, str]:
        """Get iFlow version and system information."""
        version_info = {
            "binary_path": self.binary_path,
            "available": str(self.check_binary_exists()),
        }
        
        try:
            result = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
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
        self.logger.info(f"Starting iFlow process in {repo_dir} with {self.max_tokens} token limit")
        
        # Start iFlow with experimental ACP mode and token limit
        process = subprocess.Popen(
            [
                self.binary_path,
                "--experimental-acp",
                "--port", str(self.port),
                "--max-tokens", str(self.max_tokens),
                "--yolo"  # Auto-accept actions
            ],
            cwd=str(repo_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.iflow_process = process
        self.logger.info(f"iFlow process started with PID {process.pid}")
        return process
    
    def _get_context_stats(self) -> Optional[Dict[str, Any]]:
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
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Send a message and collect all responses until task finishes."""
        self.logger.info(f"📤 Sending: {message[:100]}...")
        
        # Log to transcript file
        log_file.write(f"\n{'='*80}\n")
        log_file.write(f"[{datetime.now().isoformat()}] USER: {message}\n")
        log_file.write(f"{'='*80}\n")
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
                        "tool_name": msg.tool_name if hasattr(msg, 'tool_name') else None,
                        "label": msg.label if hasattr(msg, 'label') else None
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
                                "priority": entry.priority if hasattr(entry, 'priority') else None
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
                    
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout waiting for response after {timeout}s")
            stop_reason = "timeout"
        
        full_response = "".join(response_text)
        
        # Log response to UI stream
        session_logger.log_agent_response(
            full_response,
            f"response_{len(tool_calls)}_tools_{len(plans)}_plans"
        )
        
        return {
            "response": full_response,
            "tool_calls": tool_calls,
            "plans": plans,
            "stop_reason": stop_reason,
            "hit_token_limit": stop_reason == StopReason.MAX_TOKENS
        }
    
    def run_session(self, session: AgentSession) -> Dict[str, Any]:
        """Run complete iFlow session using SDK."""
        self.setup_output_directory(session.output_dir)
        
        # Create transcript file
        transcript_path = session.output_dir / "transcript.txt"
        
        # Create session logger for UI streaming
        session_logger = AgentSessionLogger(session.task_id, "iflow")
        
        try:
            # Run async session
            result = asyncio.run(self._run_async_session(session, transcript_path, session_logger))
            
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
        session_logger: AgentSessionLogger
    ) -> Dict[str, Any]:
        """Run the async iFlow session using SDK."""
        
        milestones = []
        stats = {}
        responses = []
        total_tokens_estimate = 0
        compression_detected = False
        
        # Start iFlow process
        self._start_iflow_process(session.repo_dir)
        
        # Wait for iFlow to start
        await asyncio.sleep(5)
        milestones.append("iflow_started")
        
        try:
            with open(transcript_path, "w", encoding="utf-8") as log_file:
                # Connect via SDK
                options = IFlowOptions(
                    auto_start_process=False,
                    url=f"ws://localhost:{self.port}/acp",
                    timeout=float(self.session_timeout)
                )
                
                self.logger.info(f"Connecting to iFlow at {options.url}")
                
                async with IFlowClient(options) as client:
                    milestones.append("sdk_connected")
                    
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
                        client, session.prompts.get("pre") or session.prompts.get("precompression", ""), log_file, session_logger, timeout=300
                    )
                    responses.append({"phase": "pre_compression", **pre_result})
                    milestones.append("pre_compression")
                    
                    total_tokens_estimate += len(pre_result["response"]) // 4
                    stats["pre_compression_tokens_estimate"] = total_tokens_estimate
                    
                    # Phase 3: Deep-dive prompts (loop until token limit or compression)
                    self.logger.info("=" * 80)
                    self.logger.info("PHASE 3: Deep-Dive Analysis")
                    self.logger.info("=" * 80)
                    
                    deep_dive_count = 0
                    prev_tokens = 0
                    detection_method = "none"
                    
                    while deep_dive_count < self.max_turns:
                        deep_dive_count += 1
                        self.logger.info(f"Deep-dive iteration #{deep_dive_count}")
                        
                        # Store previous token count for jump detection
                        prev_tokens = total_tokens_estimate
                        
                        deep_result = await self._send_and_collect(
                            client, session.prompts.get("deep") or session.prompts.get("deepdive", ""), log_file, session_logger, timeout=300
                        )
                        responses.append({"phase": f"deep_dive_{deep_dive_count}", **deep_result})
                        
                        total_tokens_estimate += len(deep_result["response"]) // 4
                        stats[f"deep_dive_{deep_dive_count}_tokens"] = total_tokens_estimate
                        
                        # Log token usage
                        hit_limit = deep_result["hit_token_limit"]
                        self.logger.info(f"📊 Token estimate: {total_tokens_estimate:,} / {self.max_tokens:,} ({total_tokens_estimate/self.max_tokens*100:.1f}%)")
                        self.logger.info(f"📊 Stop reason: {deep_result.get('stop_reason', 'unknown')} | Hit token limit: {hit_limit}")
                        self.logger.info(f"📊 Turn: {deep_dive_count} / {self.max_turns}")
                        session_logger.log_context_stats(
                            f"{total_tokens_estimate}/{self.max_tokens}",
                            f"Tokens: {total_tokens_estimate:,} ({total_tokens_estimate/self.max_tokens*100:.1f}%)"
                        )
                        
                        # Method 1: Token jump detection (compression occurred)
                        # If tokens suddenly drop by 30% or more, compression likely happened
                        if prev_tokens > 0 and total_tokens_estimate < prev_tokens * 0.7:
                            self.logger.info(f"🔴 Token jump detected: {prev_tokens:,} → {total_tokens_estimate:,} (compression occurred!)")
                            compression_detected = True
                            detection_method = "token_jump"
                            break
                        
                        # Method 2: Response analysis - check for compression indicators
                        response_text = deep_result.get("response", "").lower()
                        compression_keywords = ["memory", "compressed", "summarized", "context window", "token limit"]
                        if any(keyword in response_text for keyword in compression_keywords):
                            self.logger.info(f"🔴 Compression indicator detected in response (keywords: {compression_keywords})")
                            compression_detected = True
                            detection_method = "response_analysis"
                            break
                        
                        # Method 3: Hit limit flag (existing - from iFlow SDK)
                        if hit_limit:
                            self.logger.info("🔴 Token limit reached - iFlow will compress context on next interaction")
                            compression_detected = True
                            detection_method = "token_limit_flag"
                            break
                        
                        # Method 4: FALLBACK - Check if our estimate exceeds limit
                        if total_tokens_estimate >= self.max_tokens:
                            self.logger.info(f"🔴 Token estimate exceeded limit ({total_tokens_estimate:,} >= {self.max_tokens:,}) - proceeding to memory-only evaluation")
                            compression_detected = True
                            detection_method = "token_estimate_exceeded"
                            break
                        
                        # Check if approaching limit (90% of max)
                        if total_tokens_estimate > self.max_tokens * 0.9:
                            self.logger.info(f"⚠️  Approaching token limit: {total_tokens_estimate:,} / {self.max_tokens:,}")
                    
                    milestones.append("deep_dive_complete")
                    stats["deep_dive_iterations"] = deep_dive_count
                    
                    # Phase 4: Memory-only evaluation
                    self.logger.info("=" * 80)
                    self.logger.info("PHASE 4: Memory-Only Evaluation")
                    self.logger.info("=" * 80)
                    
                    memory_result = await self._send_and_collect(
                        client, session.prompts["memory_only"], log_file, session_logger, timeout=300
                    )
                    responses.append({"phase": "memory_only", **memory_result})
                    milestones.append("memory_only")
                    
                    # Phase 5: Evaluator questions - PARSE INDIVIDUAL Q&A
                    self.logger.info("=" * 80)
                    self.logger.info("PHASE 5: Evaluator Questions")
                    self.logger.info("=" * 80)
                    
                    # Define evaluation questions
                    eval_questions = [
                        "What is the main purpose of this PR?",
                        "List the key files that were changed and their roles.",
                        "How would you implement a similar feature?",
                        "What are the long-term implications of this approach?"
                    ]
                    
                    # Ask each question and collect answers
                    evaluation_qa = []
                    for i, question in enumerate(eval_questions):
                        self.logger.info(f"Question {i+1}: {question}")
                        
                        # Send question to agent
                        qa_result = await self._send_and_collect(
                            client, question, log_file, session_logger, timeout=60
                        )
                        
                        answer = qa_result["response"]
                        self.logger.info(f"Answer {i+1}: {answer[:200]}...")
                        
                        evaluation_qa.append({
                            "turn": i + 1,
                            "question": question,
                            "answer": answer
                        })
                    
                    # Store in stats
                    stats["evaluation_qa"] = evaluation_qa
                    self.logger.info(f"Stored {len(evaluation_qa)} Q&A pairs in stats")
                    
                    milestones.append("evaluation_complete")
                    
                    milestones.append("session_complete")
        
        except Exception as e:
            self.logger.error(f"Session error: {e}", exc_info=True)
            raise AgentExecutionError(self.name.value, f"Session error: {e}")
        
        # Prepare final statistics
        stats.update({
            "compression_detected": str(compression_detected),
            "total_tokens_estimate": str(total_tokens_estimate),
            "detection_method": detection_method,
            "max_tokens_configured": str(self.max_tokens),
        })
        
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
