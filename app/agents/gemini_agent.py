"""Google Gemini AI agent adapter."""

import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import pexpect

from app.domain.entities import AgentName
from app.agents.base import (
    AgentAdapter, AgentSession, CompressionDetector, AgentCapabilities,
    AgentMetadata, AgentNotFoundError, AgentExecutionError, AgentTimeoutError
)
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiCompressionDetector(CompressionDetector):
    """Gemini-specific compression detection using heuristics."""
    
    def __init__(self, deep_dive_steps: int = 3):
        self.deep_dive_steps = deep_dive_steps
        self.logger = logging.getLogger("agents.gemini.compression")
    
    def detect_compression(self, session_data: str) -> bool:
        """Detect compression based on session progression."""
        # Gemini doesn't expose context stats like iFlow
        # We use step-based detection similar to Claude
        return True  # Assume compression after deep-dive steps
    
    def should_enter_memory_only(self, session_data: str, previous_state: Dict[str, Any]) -> bool:
        """Determine if should enter memory-only mode based on step count."""
        step_count = previous_state.get("deep_dive_steps", 0)
        result = step_count >= self.deep_dive_steps
        
        if result:
            self.logger.info(f"Entering memory-only mode after {step_count} deep-dive steps")
        
        return result


class GeminiAgent(AgentAdapter):
    """Google Gemini AI agent adapter using CLI interaction."""
    
    def __init__(self):
        super().__init__(AgentName.GEMINI, settings.gemini_bin)
        self.compression_detector = GeminiCompressionDetector(deep_dive_steps=3)
        self.session_timeout = settings.agent_session_timeout
    
    def validate_installation(self) -> bool:
        """Validate that Gemini CLI is installed and working."""
        if not self.check_binary_exists():
            self.logger.error(f"Gemini binary not found: {self.binary_path}")
            return False
        
        try:
            # Test basic Gemini command
            result = subprocess.run(
                [self.binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                # Try alternative version check
                result = subprocess.run(
                    [self.binary_path, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode != 0:
                # Try help command as fallback
                result = subprocess.run(
                    [self.binary_path, "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode != 0:
                self.logger.error(f"Gemini validation failed: {result.stderr}")
                return False
            
            self.logger.info(f"Gemini validation successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Gemini validation failed: {e}")
            return False
    
    def get_version_info(self) -> Dict[str, str]:
        """Get Gemini version and system information."""
        version_info = {
            "binary_path": self.binary_path,
            "available": str(self.check_binary_exists()),
        }
        
        try:
            # Try multiple version commands
            for version_cmd in ["--version", "version", "--help"]:
                result = subprocess.run(
                    [self.binary_path, version_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    version_info["version"] = result.stdout.strip()[:200]  # Truncate help output
                    break
            else:
                version_info["version_error"] = "Version command not found"
                
        except Exception as e:
            version_info["version_error"] = str(e)
        
        return version_info
    
    def run_session(self, session: AgentSession) -> Dict[str, Any]:
        """Run complete Gemini session with step-based compression detection."""
        self.setup_output_directory(session.output_dir)
        
        # Create transcript file
        transcript_path = session.output_dir / "transcript.txt"
        
        try:
            with open(transcript_path, "w", encoding="utf-8") as log_file:
                result = self._run_interactive_session(
                    session, log_file
                )
            
            # Add file paths to result
            result["artifacts"]["transcript"] = str(transcript_path)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Gemini session failed: {e}")
            return self.handle_error(e, session)
    
    def _run_interactive_session(
        self,
        session: AgentSession,
        log_file
    ) -> Dict[str, Any]:
        """Run the interactive Gemini session with step-based execution."""
        
        # Initialize session state
        milestones = []
        stats = {}
        compression_detected = False
        deep_dive_steps = 0
        
        # Start Gemini process
        self.logger.info(f"Starting Gemini session in {session.repo_dir}")
        
        try:
            # Use Gemini chat/interactive command
            child = pexpect.spawn(
                f"{self.binary_path} chat",
                cwd=str(session.repo_dir),
                encoding="utf-8",
                timeout=self.session_timeout
            )
            child.logfile = log_file
            
            # Wait for Gemini to be ready
            time.sleep(3)
            milestones.append("initialized")
            
            # Send pre-compression prompt
            self.logger.info("Sending pre-compression prompt")
            child.sendline(session.prompts["pre"])
            child.expect([pexpect.TIMEOUT, ".*"], timeout=30)
            time.sleep(5)
            milestones.append("pre_compression")
            
            # Deep-dive phase with step-based detection
            max_deep_dive_steps = 3
            for step in range(max_deep_dive_steps):
                self.logger.info(f"Deep-dive step {step + 1}")
                
                child.sendline(session.prompts["deep"])
                child.expect([pexpect.TIMEOUT, ".*"], timeout=60)
                time.sleep(8)
                
                deep_dive_steps += 1
                stats[f"deep_dive_step_{step + 1}"] = "completed"
                
                # Check if we should enter memory-only mode
                if self.compression_detector.should_enter_memory_only("", {"deep_dive_steps": deep_dive_steps}):
                    compression_detected = True
                    break
            
            milestones.append("deep_dive_complete")
            
            # Enter memory-only mode
            self.logger.info("Entering memory-only mode")
            child.sendline(session.prompts["memory_only"])
            child.expect([pexpect.TIMEOUT, ".*"], timeout=30)
            time.sleep(3)
            milestones.append("memory_only")
            
            # Run evaluator questions
            self.logger.info("Running evaluator questions")
            evaluator_lines = session.prompts["eval"].splitlines()
            for i, line in enumerate(evaluator_lines):
                if line.strip():
                    self.logger.debug(f"Evaluator question {i + 1}")
                    child.sendline(line.strip())
                    child.expect([pexpect.TIMEOUT, ".*"], timeout=30)
                    time.sleep(3)
            
            milestones.append("evaluation_complete")
            
            # End session - try different exit commands
            for exit_cmd in ["/quit", "/exit", "quit", "exit"]:
                child.sendline(exit_cmd)
                try:
                    child.expect(pexpect.EOF, timeout=5)
                    break
                except pexpect.TIMEOUT:
                    continue
            else:
                # Force terminate if none of the exit commands work
                child.terminate()
            
            milestones.append("session_complete")
            
        except pexpect.TIMEOUT as e:
            self.logger.error(f"Gemini session timeout: {e}")
            raise AgentTimeoutError(self.name.value, f"Session timeout: {e}")
        
        except pexpect.EOF as e:
            self.logger.info("Gemini session ended (EOF)")
        
        except Exception as e:
            self.logger.error(f"Gemini session error: {e}")
            raise AgentExecutionError(self.name.value, f"Session error: {e}")
        
        finally:
            # Ensure child process is terminated
            if 'child' in locals() and child.isalive():
                child.terminate(force=True)
        
        # Prepare final statistics
        stats.update({
            "compression_detected": str(compression_detected),
            "deep_dive_steps": str(deep_dive_steps),
            "detection_method": "step_based",
        })
        
        return {
            "artifacts": {},  # Will be populated by caller
            "stats": stats,
            "compression_detected": compression_detected,
            "milestones": milestones,
        }


# Agent metadata for registry
GEMINI_CAPABILITIES = AgentCapabilities(
    supports_export=False,
    supports_stats=False,
    supports_compression_detection=True,
    supports_interactive_mode=True,
    max_session_duration=1800,
)

GEMINI_METADATA = AgentMetadata(
    name=AgentName.GEMINI,
    display_name="Google Gemini",
    description="Google Gemini AI agent with step-based compression detection",
    version="1.0.0",
    capabilities=GEMINI_CAPABILITIES,
    binary_name="gemini",
    installation_instructions="Install via: pip install google-generativeai",
)
