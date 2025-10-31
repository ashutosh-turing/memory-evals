"""iFlow AI agent adapter with compression detection."""

import re
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


class IFlowCompressionDetector(CompressionDetector):
    """iFlow-specific compression detection using footer analysis."""
    
    def __init__(self, threshold_low: int = 30, jump_threshold: int = 30):
        self.threshold_low = threshold_low
        self.jump_threshold = jump_threshold
        self.footer_regex = re.compile(r"(\d+)% context left")
        self.logger = logging.getLogger("agents.iflow.compression")
    
    def detect_compression(self, session_data: str) -> bool:
        """Detect compression from iFlow session output."""
        # Look for the last context percentage in the session data
        matches = list(self.footer_regex.finditer(session_data))
        if not matches:
            return False
        
        # Get the last match (most recent context percentage)
        last_match = matches[-1]
        context_left = int(last_match.group(1))
        
        self.logger.debug(f"Current context left: {context_left}%")
        
        # Compression detected if context drops to or below threshold
        return context_left <= self.threshold_low
    
    def should_enter_memory_only(self, session_data: str, previous_state: Dict[str, Any]) -> bool:
        """Determine if should enter memory-only mode based on compression jump."""
        matches = list(self.footer_regex.finditer(session_data))
        if len(matches) < 2:
            return self.detect_compression(session_data)
        
        # Get last two context percentages
        current_context = int(matches[-1].group(1))
        previous_context = int(matches[-2].group(1))
        
        self.logger.debug(f"Context transition: {previous_context}% -> {current_context}%")
        
        # Check for compression jump (context suddenly increases by 30%+ = compression occurred)
        compression_jump = current_context - previous_context >= self.jump_threshold
        
        # Also check if context is critically low
        critically_low = current_context <= self.threshold_low
        
        result = compression_jump or critically_low
        if result:
            self.logger.info(
                f"Entering memory-only mode: jump={compression_jump} "
                f"({previous_context}% -> {current_context}%), low={critically_low}"
            )
        
        return result


class IFlowAgent(AgentAdapter):
    """iFlow AI agent adapter using pexpect for CLI interaction."""
    
    def __init__(self):
        super().__init__(AgentName.IFLOW, settings.iflow_bin)
        self.compression_detector = IFlowCompressionDetector(
            threshold_low=settings.compression_threshold_low,
            jump_threshold=settings.compression_jump_threshold
        )
        self.session_timeout = settings.agent_session_timeout
    
    def validate_installation(self) -> bool:
        """Validate that iFlow CLI is installed and working."""
        if not self.check_binary_exists():
            self.logger.error(f"iFlow binary not found: {self.binary_path}")
            return False
        
        try:
            # Test basic iFlow command
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
                version_info["version_error"] = result.stderr.strip()
                
        except Exception as e:
            version_info["version_error"] = str(e)
        
        return version_info
    
    def run_session(self, session: AgentSession) -> Dict[str, Any]:
        """Run complete iFlow session with compression detection."""
        self.setup_output_directory(session.output_dir)
        
        # Create transcript file
        transcript_path = session.output_dir / "transcript.txt"
        export_path = session.output_dir / "export.json"
        
        try:
            with open(transcript_path, "w", encoding="utf-8") as log_file:
                result = self._run_interactive_session(
                    session, log_file, export_path
                )
            
            # Add file paths to result
            result["artifacts"]["transcript"] = str(transcript_path)
            if export_path.exists():
                result["artifacts"]["export"] = str(export_path)
            
            return result
            
        except Exception as e:
            self.logger.error(f"iFlow session failed: {e}")
            return self.handle_error(e, session)
    
    def _run_interactive_session(
        self,
        session: AgentSession,
        log_file,
        export_path: Path
    ) -> Dict[str, Any]:
        """Run the interactive iFlow session with step-by-step execution."""
        
        # Initialize session state
        milestones = []
        stats = {}
        compression_detected = False
        context_history = []
        
        # Start iFlow process
        self.logger.info(f"Starting iFlow session in {session.repo_dir}")
        
        child = pexpect.spawn(
            self.binary_path,
            cwd=str(session.repo_dir),
            encoding="utf-8",
            timeout=self.session_timeout
        )
        child.logfile = log_file
        
        try:
            # Wait for initial prompt
            child.expect("Type your message", timeout=120)
            milestones.append("initialized")
            
            # Initialize iFlow
            self.logger.info("Initializing iFlow session")
            child.sendline("/init")
            time.sleep(2)
            milestones.append("init_command")
            
            # Send pre-compression prompt
            self.logger.info("Sending pre-compression prompt")
            child.sendline(session.prompts["pre"])
            time.sleep(6)
            milestones.append("pre_compression")
            
            # Deep-dive loop with compression detection
            last_context_left = 100
            for iteration in range(6):  # Max 6 iterations to prevent infinite loops
                self.logger.info(f"Deep-dive iteration {iteration + 1}")
                
                # Get current stats
                child.sendline("/stats")
                time.sleep(2)
                
                # Parse context from output
                output_buffer = child.before or ""
                context_match = self.compression_detector.footer_regex.search(output_buffer)
                
                if context_match:
                    current_context = int(context_match.group(1))
                    context_history.append(current_context)
                    stats[f"context_iteration_{iteration + 1}"] = str(current_context)
                    
                    self.logger.info(f"Context left: {current_context}%")
                    
                    # Check if we should exit deep-dive phase
                    if current_context <= self.compression_detector.threshold_low:
                        self.logger.info("Low context detected, exiting deep-dive")
                        compression_detected = True
                        break
                    
                    # Check for compression jump (context increased significantly)
                    if len(context_history) >= 2:
                        jump = current_context - context_history[-2]
                        if jump >= self.compression_detector.jump_threshold:
                            self.logger.info(f"Compression jump detected: +{jump}%")
                            compression_detected = True
                            break
                    
                    last_context_left = current_context
                else:
                    self.logger.warning("Could not parse context percentage from /stats output")
                
                # Continue with deep-dive
                child.sendline(session.prompts["deep"])
                time.sleep(8)
                
                # Check stats again after deep-dive
                child.sendline("/stats")
                time.sleep(2)
            
            milestones.append("deep_dive_complete")
            
            # Enter memory-only mode
            self.logger.info("Entering memory-only mode")
            child.sendline(session.prompts["memory_only"])
            time.sleep(2)
            milestones.append("memory_only")
            
            # Run evaluator questions
            self.logger.info("Running evaluator questions")
            evaluator_lines = session.prompts["eval"].splitlines()
            for line in evaluator_lines:
                if line.strip():
                    child.sendline(line.strip())
                    time.sleep(2)
            
            milestones.append("evaluation_complete")
            
            # Export session data (if supported)
            self.logger.info(f"Exporting session data to {export_path}")
            child.sendline(f"/export --format json --path {export_path}")
            time.sleep(4)
            
            if export_path.exists():
                milestones.append("export_complete")
            
            # Exit iFlow
            try:
                child.sendline("/exit")
                child.expect(pexpect.EOF, timeout=5)
            except pexpect.TIMEOUT:
                # Force terminate if /exit doesn't work
                child.terminate()
            
            milestones.append("session_complete")
            
        except pexpect.TIMEOUT as e:
            self.logger.error(f"iFlow session timeout: {e}")
            raise AgentTimeoutError(self.name.value, f"Session timeout: {e}")
        
        except pexpect.EOF as e:
            self.logger.info("iFlow session ended (EOF)")
        
        except Exception as e:
            self.logger.error(f"iFlow session error: {e}")
            raise AgentExecutionError(self.name.value, f"Session error: {e}")
        
        finally:
            # Ensure child process is terminated
            if child.isalive():
                child.terminate(force=True)
        
        # Prepare final statistics
        stats.update({
            "compression_detected": str(compression_detected),
            "final_context_left": str(context_history[-1] if context_history else "unknown"),
            "context_history": ",".join(map(str, context_history)),
            "total_iterations": str(len(context_history)),
        })
        
        return {
            "artifacts": {},  # Will be populated by caller
            "stats": stats,
            "compression_detected": compression_detected,
            "milestones": milestones,
        }


# Agent metadata for registry
IFLOW_CAPABILITIES = AgentCapabilities(
    supports_export=True,
    supports_stats=True,
    supports_compression_detection=True,
    supports_interactive_mode=True,
    max_session_duration=1800,
)

IFLOW_METADATA = AgentMetadata(
    name=AgentName.IFLOW,
    display_name="iFlow AI",
    description="iFlow AI agent with advanced compression detection capabilities",
    version="1.0.0",
    capabilities=IFLOW_CAPABILITIES,
    binary_name="iflow",
    installation_instructions="Install via: bash -c \"$(curl -fsSL https://cloud.iflow.cn/iflow-cli/install.sh)\"",
)
