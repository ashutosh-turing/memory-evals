"""Claude AI agent adapter using Anthropic SDK."""

import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

from anthropic import Anthropic

from app.domain.entities import AgentName
from app.agents.base import (
    AgentAdapter, AgentSession, AgentCapabilities,
    AgentMetadata, AgentExecutionError
)
from app.config import settings
from app.services.task_logger import AgentSessionLogger

logger = logging.getLogger(__name__)


class ClaudeAgent(AgentAdapter):
    """Claude AI agent adapter using Anthropic SDK for direct API interaction."""
    
    def __init__(self):
        super().__init__(AgentName.CLAUDE, "claude")  # No binary needed
        # Don't instantiate the client here - create it in the async context
        self.model = settings.claude_model
        self.max_tokens = settings.max_context_tokens
        self.max_turns = settings.max_turns
        self.session_timeout = settings.agent_session_timeout
    
    def validate_installation(self) -> bool:
        """Validate that Anthropic API key is configured."""
        if not settings.anthropic_api_key:
            self.logger.error("Anthropic API key not configured")
            return False
        
        self.logger.info("Claude (Anthropic SDK) validation successful")
        return True
    
    def get_version_info(self) -> Dict[str, str]:
        """Get Claude version and system information."""
        return {
            "model": self.model,
            "max_tokens": str(self.max_tokens),
            "api_configured": str(bool(settings.anthropic_api_key)),
            "sdk": "anthropic-python",
        }
    
    def _load_repo_files(self, repo_dir: Path, max_files: int = 50) -> str:
        """Load repository files into a context string with token limit."""
        self.logger.info(f"Loading repository files from {repo_dir}")
        
        # Limit initial context to ~50K tokens (leaving room for conversation)
        MAX_CONTEXT_TOKENS = 50000
        
        # Common code file extensions
        code_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
            '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.cs', '.scala',
            '.md', '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.css'
        }
        
        files_content = []
        file_count = 0
        total_tokens = 0
        
        try:
            for file_path in repo_dir.rglob('*'):
                if file_count >= max_files:
                    break
                
                # Skip directories and hidden files
                if file_path.is_dir() or file_path.name.startswith('.'):
                    continue
                
                # Skip common non-code directories
                if any(part in file_path.parts for part in ['.git', 'node_modules', '__pycache__', 'venv', 'dist', 'build']):
                    continue
                
                # Only include code files
                if file_path.suffix not in code_extensions:
                    continue
                
                try:
                    relative_path = file_path.relative_to(repo_dir)
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # Estimate tokens (rough: 1 token ~= 4 characters)
                    file_tokens = len(content) // 4
                    
                    # Stop if we would exceed token limit
                    if total_tokens + file_tokens > MAX_CONTEXT_TOKENS:
                        self.logger.info(f"Stopping at {file_count} files to stay within {MAX_CONTEXT_TOKENS} token limit")
                        break
                    
                    files_content.append(f"### File: {relative_path}\n```{file_path.suffix[1:]}\n{content}\n```\n")
                    file_count += 1
                    total_tokens += file_tokens
                    
                except Exception as e:
                    self.logger.warning(f"Could not read {file_path}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error loading repository files: {e}")
            return f"Error loading repository: {e}"
        
        self.logger.info(f"Loaded {file_count} files (~{total_tokens} tokens) from repository")
        
        if not files_content:
            return "No code files found in repository."
        
        return f"# Repository Code\n\n" + "\n\n".join(files_content)
    
    def run_session(self, session: AgentSession) -> Dict[str, Any]:
        """Run complete Claude session using Anthropic SDK."""
        self.setup_output_directory(session.output_dir)
        
        # Create transcript file
        transcript_path = session.output_dir / "transcript.txt"
        
        # Create session logger for UI streaming
        session_logger = AgentSessionLogger(session.task_id, "claude")
        
        try:
            # Run async session
            result = asyncio.run(self._run_async_session(session, transcript_path, session_logger))
            
            # Add file paths to result
            result["artifacts"]["transcript"] = str(transcript_path)
            
            # Close session logger
            session_logger.close_session("completed", result.get("artifacts", {}))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Claude session failed: {e}", exc_info=True)
            session_logger.close_session("failed", {"error": str(e)})
            return self.handle_error(e, session)
    
    async def _run_async_session(
        self,
        session: AgentSession,
        transcript_path: Path,
        session_logger: AgentSessionLogger
    ) -> Dict[str, Any]:
        """Run the async Claude session using Anthropic SDK."""
        
        milestones = []
        stats = {}
        responses = []
        total_tokens = 0
        hit_limit = False
        
        # Create synchronous client
        client = Anthropic(api_key=settings.anthropic_api_key)
        
        try:
            with open(transcript_path, "w", encoding="utf-8") as log_file:
                # Phase 1: Load repository context
                self.logger.info("=" * 80)
                self.logger.info("PHASE 1: Loading Repository Context")
                self.logger.info("=" * 80)
                
                repo_context = self._load_repo_files(session.repo_dir)
                log_file.write(f"Repository Context Loaded: {len(repo_context)} characters\n")
                log_file.write("=" * 80 + "\n\n")
                
                init_prompt = f"{repo_context}\n\nThis is a code repository. Please analyze it and be ready to answer questions about it."
                messages = [
                    {"role": "user", "content": init_prompt}
                ]
                
                # Log to UI
                session_logger.log_prompt_sent(init_prompt, "repo_initialization")
                
                # Initial context loading
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=messages
                )
                
                total_tokens += response.usage.input_tokens + response.usage.output_tokens
                messages.append({"role": "assistant", "content": response.content[0].text})
                
                log_file.write(f"ASSISTANT: {response.content[0].text}\n\n")
                log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                log_file.write("=" * 80 + "\n\n")
                
                # Log to UI
                session_logger.log_agent_response(response.content[0].text, "repo_analysis")
                session_logger.log_context_stats(f"{total_tokens}/{self.max_tokens}", f"Tokens: {total_tokens:,}")
                
                milestones.append("repo_loaded")
                stats["initial_tokens"] = total_tokens
                
                # Phase 2: Pre-compression prompt
                self.logger.info("=" * 80)
                self.logger.info("PHASE 2: Pre-Compression Analysis")
                self.logger.info("=" * 80)
                
                session_logger.log_prompt_sent(session.prompts["precompression"], "pre_compression")
                messages.append({"role": "user", "content": session.prompts["precompression"]})
                
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=messages
                )
                
                total_tokens += response.usage.input_tokens + response.usage.output_tokens
                messages.append({"role": "assistant", "content": response.content[0].text})
                responses.append({"phase": "pre_compression", "response": response.content[0].text})
                
                log_file.write(f"USER: {session.prompts['precompression']}\n\n")
                log_file.write(f"ASSISTANT: {response.content[0].text}\n\n")
                log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                log_file.write("=" * 80 + "\n\n")
                
                session_logger.log_agent_response(response.content[0].text, "pre_compression_response")
                session_logger.log_context_stats(f"{total_tokens}/{self.max_tokens}", f"Tokens: {total_tokens:,}")
                
                milestones.append("pre_compression")
                stats["pre_compression_tokens"] = total_tokens
                
                # Phase 3: Deep-dive prompts (loop until token limit)
                self.logger.info("=" * 80)
                self.logger.info("PHASE 3: Deep-Dive Analysis")
                self.logger.info("=" * 80)
                
                deep_dive_count = 0
                
                while deep_dive_count < self.max_turns and total_tokens < self.max_tokens * 0.9:
                    deep_dive_count += 1
                    self.logger.info(f"Deep-dive iteration #{deep_dive_count}")
                    self.logger.info(f"Current tokens: {total_tokens:,} / {self.max_tokens:,} ({total_tokens/self.max_tokens*100:.1f}%)")
                    self.logger.info(f"Turn: {deep_dive_count} / {self.max_turns}")
                    
                    messages.append({"role": "user", "content": session.prompts["deepdive"]})
                    
                    try:
                        response = client.messages.create(
                            model=self.model,
                            max_tokens=4096,
                            messages=messages
                        )
                        
                        total_tokens += response.usage.input_tokens + response.usage.output_tokens
                        messages.append({"role": "assistant", "content": response.content[0].text})
                        responses.append({"phase": f"deep_dive_{deep_dive_count}", "response": response.content[0].text})
                        
                        log_file.write(f"USER (Deep-dive #{deep_dive_count}): {session.prompts['deepdive']}\n\n")
                        log_file.write(f"ASSISTANT: {response.content[0].text}\n\n")
                        log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                        log_file.write("=" * 80 + "\n\n")
                        
                        stats[f"deep_dive_{deep_dive_count}_tokens"] = total_tokens
                        
                    except Exception as e:
                        self.logger.error(f"Deep-dive iteration {deep_dive_count} failed: {e}")
                        if "maximum context length" in str(e).lower():
                            self.logger.info("🔴 Hit Claude's context limit")
                            hit_limit = True
                            break
                        raise
                
                milestones.append("deep_dive_complete")
                stats["deep_dive_iterations"] = deep_dive_count
                
                if total_tokens >= self.max_tokens * 0.9:
                    hit_limit = True
                    self.logger.info(f"🔴 Reached token limit threshold: {total_tokens:,} / {self.max_tokens:,}")
                
                # Phase 4: Memory-only evaluation
                self.logger.info("=" * 80)
                self.logger.info("PHASE 4: Memory-Only Evaluation")
                self.logger.info("=" * 80)
                
                messages.append({"role": "user", "content": session.prompts["memory_only"]})
                
                try:
                    response = client.messages.create(
                        model=self.model,
                        max_tokens=4096,
                        messages=messages
                    )
                    
                    total_tokens += response.usage.input_tokens + response.usage.output_tokens
                    messages.append({"role": "assistant", "content": response.content[0].text})
                    responses.append({"phase": "memory_only", "response": response.content[0].text})
                    
                    log_file.write(f"USER (Memory-only): {session.prompts['memory_only']}\n\n")
                    log_file.write(f"ASSISTANT: {response.content[0].text}\n\n")
                    log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                    log_file.write("=" * 80 + "\n\n")
                    
                    milestones.append("memory_only")
                    
                except Exception as e:
                    self.logger.error(f"Memory-only phase failed: {e}")
                    if "maximum context length" in str(e).lower():
                        self.logger.warning("Cannot continue - context limit exceeded")
                    else:
                        raise
                
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
                    
                    messages.append({"role": "user", "content": question})
                    
                    try:
                        response = client.messages.create(
                            model=self.model,
                            max_tokens=500,
                            messages=messages
                        )
                        
                        answer = response.content[0].text
                        total_tokens += response.usage.input_tokens + response.usage.output_tokens
                        messages.append({"role": "assistant", "content": answer})
                        
                        self.logger.info(f"Answer {i+1}: {answer[:200]}...")
                        
                        log_file.write(f"USER (Q{i+1}): {question}\n\n")
                        log_file.write(f"ASSISTANT: {answer}\n\n")
                        log_file.write(f"Tokens used: {total_tokens:,} / {self.max_tokens:,}\n")
                        log_file.write("=" * 80 + "\n\n")
                        
                        evaluation_qa.append({
                            "turn": i + 1,
                            "question": question,
                            "answer": answer
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Question {i+1} failed: {e}")
                        if "maximum context length" in str(e).lower():
                            self.logger.warning("Cannot continue - context limit exceeded")
                            break
                        else:
                            raise
                
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
            "total_tokens": str(total_tokens),
            "hit_limit": str(hit_limit),
            "max_tokens_configured": str(self.max_tokens),
            "detection_method": "api_token_tracking",
        })
        
        return {
            "artifacts": {},  # Will be populated by caller
            "stats": stats,
            "compression_detected": hit_limit,
            "milestones": milestones,
            "responses": responses,
        }


# Agent metadata for registry
CLAUDE_CAPABILITIES = AgentCapabilities(
    supports_export=False,
    supports_stats=True,
    supports_compression_detection=True,
    supports_interactive_mode=False,
    max_session_duration=1800,
)

CLAUDE_METADATA = AgentMetadata(
    name=AgentName.CLAUDE,
    display_name="Claude AI",
    description="Anthropic Claude AI agent using native SDK with token tracking",
    version="2.0.0",
    capabilities=CLAUDE_CAPABILITIES,
    binary_name="claude",
    installation_instructions="Configure ANTHROPIC_API_KEY in .env file",
)
