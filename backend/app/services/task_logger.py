"""Structured logging for task execution with detailed tracing."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID

from app.config import settings


class TaskLogger:
    """Structured logger for task execution with real-time streaming support."""
    
    def __init__(self, task_id: UUID, agent_name: Optional[str] = None):
        self.task_id = str(task_id)
        self.agent_name = agent_name
        self.task_dir = Path(settings.run_root) / self.task_id
        self.task_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log files
        self.main_log_file = self.task_dir / "task.log"
        
        if agent_name:
            self.agent_dir = self.task_dir / "agents" / agent_name
            self.agent_dir.mkdir(parents=True, exist_ok=True)
            self.agent_log_file = self.agent_dir / "session.log"
            self.transcript_file = self.agent_dir / "transcript.txt"
        else:
            self.agent_log_file = None
            self.transcript_file = None
        
        # Setup logger
        self.logger = logging.getLogger(f"task.{self.task_id}")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to prevent duplicates
        self.logger.handlers.clear()
        
        # Add file handler for main task log
        main_handler = logging.FileHandler(self.main_log_file, encoding='utf-8')
        main_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(main_handler)
        
        # Add agent-specific handler if needed
        if self.agent_log_file:
            agent_handler = logging.FileHandler(self.agent_log_file, encoding='utf-8')
            agent_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(agent_handler)
    
    def log_structured(self, event_type: str, data: Dict[str, Any], level: str = "INFO"):
        """Log structured JSON data."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.task_id,
            "agent": self.agent_name,
            "type": event_type,
            "level": level,
            **data
        }
        
        # Write to appropriate log files
        log_line = json.dumps(log_entry, ensure_ascii=False)
        
        with open(self.main_log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
            f.flush()
        
        if self.agent_log_file and self.agent_name:
            with open(self.agent_log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
                f.flush()
    
    async def log_task_event(self, task_id: str, event_type: str, message: str):
        """Generic async task event logging for worker compatibility."""
        self.log_structured(event_type.lower(), {
            "message": message
        })
    
    def log_task_started(self, pr_url: str, agents: list, rubric: list):
        """Log task initiation."""
        self.log_structured("task_started", {
            "pr_url": pr_url,
            "agents": agents,
            "rubric": rubric,
            "message": f"Task started for PR: {pr_url}"
        })
    
    def log_pr_cloned(self, repo_path: str, changed_files: list):
        """Log PR clone completion."""
        self.log_structured("pr_cloned", {
            "repo_path": repo_path,
            "changed_files": changed_files,
            "file_count": len(changed_files),
            "message": f"PR cloned successfully with {len(changed_files)} changed files"
        })
    
    def log_prompt_generated(self, prompt_type: str, prompt_content: str, file_list: list):
        """Log LLM prompt generation."""
        self.log_structured("prompt_generated", {
            "prompt_type": prompt_type,
            "prompt_content": prompt_content[:500] + "..." if len(prompt_content) > 500 else prompt_content,
            "prompt_length": len(prompt_content),
            "files_included": file_list,
            "message": f"Generated {prompt_type} prompt with {len(file_list)} files"
        })
    
    def log_agent_started(self, agent_name: str, command: str):
        """Log agent session start."""
        self.log_structured("agent_started", {
            "agent": agent_name,
            "command": command,
            "message": f"Started {agent_name} agent session"
        })
    
    def log_agent_interaction(self, agent_name: str, interaction_type: str, content: str, context: dict = None):
        """Log agent interactions (prompts sent, responses received, etc.)."""
        self.log_structured("agent_interaction", {
            "agent": agent_name,
            "interaction_type": interaction_type,  # 'prompt_sent', 'response_received', 'command_executed'
            "content": content[:1000] + "..." if len(content) > 1000 else content,
            "content_length": len(content),
            "context": context or {},
            "message": f"Agent {agent_name}: {interaction_type}"
        })
        
        # Also write to transcript file for raw output
        if self.transcript_file:
            timestamp = datetime.utcnow().isoformat()
            with open(self.transcript_file, 'a', encoding='utf-8') as f:
                f.write(f"\n[{timestamp}] {interaction_type.upper()}: {agent_name}\n")
                f.write(content + '\n')
                f.write("-" * 80 + '\n')
                f.flush()
    
    def log_compression_detected(self, agent_name: str, before_context: str, after_context: str, method: str):
        """Log memory compression detection."""
        self.log_structured("compression_detected", {
            "agent": agent_name,
            "detection_method": method,  # 'context_jump', 'percentage_threshold', 'heuristic'
            "before_context": before_context,
            "after_context": after_context,
            "message": f"Memory compression detected for {agent_name} via {method}"
        })
    
    def log_memory_only_started(self, agent_name: str, evaluator_questions: list):
        """Log start of memory-only evaluation phase."""
        self.log_structured("memory_only_started", {
            "agent": agent_name,
            "evaluator_questions": evaluator_questions,
            "question_count": len(evaluator_questions),
            "message": f"Started memory-only evaluation for {agent_name} with {len(evaluator_questions)} questions"
        })
    
    def log_evaluation_qa(self, agent_name: str, question: str, answer: str, question_index: int):
        """Log evaluation question and answer pairs."""
        self.log_structured("evaluation_qa", {
            "agent": agent_name,
            "question_index": question_index,
            "question": question,
            "answer": answer[:500] + "..." if len(answer) > 500 else answer,
            "answer_length": len(answer),
            "message": f"Q&A {question_index + 1} completed for {agent_name}"
        })
    
    def log_agent_completed(self, agent_name: str, status: str, artifacts: dict, duration: float):
        """Log agent session completion."""
        self.log_structured("agent_completed", {
            "agent": agent_name,
            "status": status,
            "artifacts": artifacts,
            "duration_seconds": duration,
            "message": f"Agent {agent_name} completed with status: {status}"
        })
    
    def log_judge_started(self, judge_type: str, agent_results: dict):
        """Log judge evaluation start."""
        self.log_structured("judge_started", {
            "judge_type": judge_type,
            "agents_evaluated": list(agent_results.keys()),
            "message": f"Started {judge_type} judge evaluation"
        })
    
    def log_judge_scoring(self, agent_name: str, dimension: str, score: float, rationale: str):
        """Log individual scoring decisions."""
        self.log_structured("judge_scoring", {
            "agent": agent_name,
            "dimension": dimension,
            "score": score,
            "rationale": rationale[:300] + "..." if len(rationale) > 300 else rationale,
            "message": f"Scored {agent_name} on {dimension}: {score}"
        })
    
    def log_task_completed(self, status: str, final_scores: dict, duration: float):
        """Log task completion."""
        self.log_structured("task_completed", {
            "status": status,
            "final_scores": final_scores,
            "duration_seconds": duration,
            "message": f"Task completed with status: {status}"
        })
    
    def log_error(self, error_type: str, error_message: str, context: dict = None, exception: Exception = None):
        """Log errors with context."""
        error_data = {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
        }
        
        if exception:
            error_data["exception_type"] = type(exception).__name__
            error_data["exception_details"] = str(exception)
        
        self.log_structured("error", error_data, level="ERROR")
    
    def log_progress_update(self, stage: str, progress_percent: int, current_step: str, details: dict = None):
        """Log progress updates for UI consumption."""
        self.log_structured("progress_update", {
            "stage": stage,  # 'pr_clone', 'agent_run', 'evaluation', 'judging'
            "progress_percent": progress_percent,
            "current_step": current_step,
            "details": details or {},
            "message": f"{stage}: {current_step} ({progress_percent}%)"
        })
    
    def close(self):
        """Close logger and cleanup handlers."""
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)


def get_task_logger(task_id: UUID, agent_name: Optional[str] = None) -> TaskLogger:
    """Factory function to create task loggers."""
    return TaskLogger(task_id, agent_name)


class AgentSessionLogger:
    """Specialized logger for agent sessions with transcript capture."""
    
    def __init__(self, task_id: UUID, agent_name: str):
        self.task_logger = TaskLogger(task_id, agent_name)
        self.agent_name = agent_name
        self.session_start_time = time.time()
        
        # Log session start
        self.task_logger.log_agent_started(agent_name, f"{agent_name} CLI session")
    
    def log_prompt_sent(self, prompt: str, prompt_type: str = "user_input"):
        """Log prompts sent to the agent."""
        self.task_logger.log_agent_interaction(
            self.agent_name,
            "prompt_sent",
            prompt,
            {"prompt_type": prompt_type}
        )
    
    def log_agent_response(self, response: str, response_type: str = "output"):
        """Log responses received from the agent."""
        self.task_logger.log_agent_interaction(
            self.agent_name,
            "response_received", 
            response,
            {"response_type": response_type}
        )
    
    def log_command_executed(self, command: str, result: str = None):
        """Log commands executed within the agent session."""
        context = {"command": command}
        if result:
            context["result"] = result[:200] + "..." if len(result) > 200 else result
        
        self.task_logger.log_agent_interaction(
            self.agent_name,
            "command_executed",
            command,
            context
        )
    
    def log_context_stats(self, context_left: str, stats_output: str):
        """Log context statistics from agent."""
        self.task_logger.log_agent_interaction(
            self.agent_name,
            "context_stats",
            stats_output,
            {"context_left": context_left}
        )
    
    def close_session(self, status: str = "completed", artifacts: dict = None):
        """Close the agent session."""
        duration = time.time() - self.session_start_time
        self.task_logger.log_agent_completed(
            self.agent_name,
            status,
            artifacts or {},
            duration
        )
        self.task_logger.close()
