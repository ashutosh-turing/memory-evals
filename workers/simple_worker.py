"""
Simple background task worker for processing memory-break evaluations.
No Redis dependencies - just simple threading for background task processing.
"""

import asyncio
import logging
import threading
import time
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
import queue

from sqlmodel import Session

from app.config import settings
from app.domain.entities import (
    AgentName, RubricDimension, TaskStatus, AgentRunStatus
)
from app.infrastructure.database import engine, DatabaseManager
from app.services.pr_service import PRService
from app.services.prompt_service import get_prompt_service
from app.services.judge_service import get_judge_service
from app.services.task_logger import TaskLogger

logger = logging.getLogger(__name__)

class SimpleTaskQueue:
    """Simple in-memory task queue using Python's queue module."""
    
    def __init__(self, max_workers=2):
        self.task_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_tasks, daemon=True)
        self.worker_thread.start()
        
    def enqueue_task(self, task_id: str, **kwargs):
        """Add a task to the processing queue."""
        self.task_queue.put((task_id, kwargs))
        logger.info(f"Enqueued task: {task_id}")
    
    def _process_tasks(self):
        """Main worker loop processing tasks from the queue."""
        worker = SimpleWorker()
        
        while self.running:
            try:
                # Get task from queue (blocks until available)
                task_id, kwargs = self.task_queue.get(timeout=1.0)
                
                logger.info(f"Processing task: {task_id}")
                
                # Process task in executor to avoid blocking
                future = self.executor.submit(worker.process_task, task_id, **kwargs)
                
                # Mark task as done
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def shutdown(self):
        """Gracefully shutdown the worker."""
        self.running = False
        self.worker_thread.join(timeout=5)
        self.executor.shutdown(wait=True)


class SimpleWorker:
    """Simple worker that processes tasks without complex container management."""
    
    def __init__(self):
        self.task_logger = None  # Will be created per task
        self.running_containers: Dict[str, str] = {}  # task_id -> container_id
        
    def process_task(self, task_id: str, **kwargs) -> Dict[str, str]:
        """
        Process a memory-break evaluation task using simple subprocess calls.
        
        Args:
            task_id: Task identifier
            **kwargs: Additional arguments
        """
        
        logger.info(f"Starting simple task processing: {task_id}")
        start_time = time.time()
        
        # Initialize services
        pr_service = PRService()
        prompt_service = get_prompt_service()
        judge_service = get_judge_service()
        
        with Session(engine) as session:
            db = DatabaseManager(session)
            
            try:
                # Get task from database
                task_db = db.get_task(UUID(task_id))
                if not task_db:
                    raise ValueError(f"Task {task_id} not found")
                
                # Create task logger for this task
                self.task_logger = TaskLogger(task_id)
                
                # Update task status
                db.update_task(UUID(task_id), {"status": TaskStatus.RUNNING})
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'TASK_STARTED', 'Simple worker started processing task'
                ))
                
                # Step 1: Process GitHub PR
                logger.info(f"Processing PR: {task_db.pr_url}")
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'PR_PROCESSING', f'Cloning and analyzing PR: {task_db.pr_url}'
                ))
                self.task_logger.log_progress_update('pr_clone', 20, 'Cloning repository')
                
                pr_result = pr_service.process_pr(task_db.pr_url, task_id)
                
                # Log PR clone completion
                self.task_logger.log_pr_cloned(
                    str(pr_result.repo_path),
                    pr_result.changed_files
                )
                self.task_logger.log_progress_update('pr_clone', 40, f'Cloned {len(pr_result.changed_files)} files')
                
                # Update task with changed files
                db.update_task(UUID(task_id), {
                    "changed_files": pr_result.changed_files
                })
                
                # Step 2: Generate prompts
                max_files = min(getattr(task_db, 'max_files', 5), 5)
                logger.info(f"Using max_files={max_files}")
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'PROMPT_GENERATION', f'Generating prompts for {max_files} files'
                ))
                self.task_logger.log_progress_update('prompt_generation', 50, 'Generating evaluation prompts')
                
                try:
                    prompts = prompt_service.generate_prompts(pr_result, max_files)
                    prompt_hash = prompt_service.get_prompt_hash(prompts)
                    
                    # Log each generated prompt
                    for prompt_type, prompt_content in prompts.items():
                        self.task_logger.log_prompt_generated(
                            prompt_type,
                            prompt_content,
                            pr_result.changed_files[:max_files]
                        )
                        asyncio.run(self.task_logger.log_task_event(
                            task_id, 'PROMPT_GENERATED', 
                            f'Generated {prompt_type} prompt: {len(prompt_content)} chars'
                        ))
                    
                    self.task_logger.log_progress_update('prompt_generation', 60, 'All prompts generated')
                    
                except Exception as prompt_error:
                    logger.error(f"Prompt generation failed: {prompt_error}")
                    self.task_logger.log_error(
                        'prompt_generation_failed',
                        str(prompt_error),
                        {'max_files': max_files},
                        prompt_error
                    )
                    prompts = self._create_fallback_prompts(pr_result)
                    prompt_hash = "fallback_prompts"
                
                # Update task with prompt hash
                db.update_task(UUID(task_id), {"prompt_hash": prompt_hash})
                
                # Step 3: Process agents using simple subprocess calls
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'AGENTS_STARTING', f'Starting {len(task_db.agents)} agents'
                ))
                self.task_logger.log_progress_update('agent_run', 70, f'Starting {len(task_db.agents)} agent(s)')
                
                agent_results = self._process_agents_simple(
                    task_id, task_db, pr_result, prompts, db
                )
                
                self.task_logger.log_progress_update('agent_run', 85, 'All agents completed')
                
                # Step 4: Judge results (if we have successful agent runs)
                successful_agents = [
                    name for name, result in agent_results.items()
                    if result.get("status") == "success"
                ]
                
                if successful_agents:
                    logger.info("Starting judging phase")
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'JUDGING_STARTED', f'Judging {len(successful_agents)} successful agent(s)'
                    ))
                    self.task_logger.log_progress_update('judging', 90, 'Evaluating agent results')
                    
                    db.update_task(UUID(task_id), {"status": TaskStatus.JUDGING})
                    self._judge_results(task_id, successful_agents, db, judge_service)
                    
                    self.task_logger.log_progress_update('judging', 95, 'Judging complete')
                else:
                    logger.warning("No successful agent runs to judge")
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'JUDGING_SKIPPED', 'No successful agent runs to judge'
                    ))
                
                # Step 5: Complete task
                db.update_task(UUID(task_id), {"status": TaskStatus.DONE})
                
                execution_time = time.time() - start_time
                
                # Log final completion
                self.task_logger.log_task_completed(
                    'done',
                    agent_results,
                    execution_time
                )
                self.task_logger.log_progress_update('complete', 100, 'Task completed successfully')
                
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'TASK_COMPLETED', 
                    f'Task completed successfully in {execution_time:.1f}s'
                ))
                
                logger.info(f"Simple task processing complete: {task_id}")
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "agents_processed": len(agent_results),
                    "successful_agents": len(successful_agents),
                    "execution_time": execution_time,
                    "prompt_hash": prompt_hash
                }
                
            except Exception as e:
                import traceback
                logger.error(f"Simple task processing failed for {task_id}: {e}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                
                # Cleanup any running containers
                self._cleanup_task_containers(task_id)
                
                # Update task with error
                db.update_task(UUID(task_id), {
                    "status": TaskStatus.ERROR,
                    "error_message": str(e)
                })
                
                # Log error only if task_logger was initialized
                if self.task_logger:
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'TASK_FAILED', f'Task failed: {str(e)}'
                    ))
                
                # Cleanup file system
                try:
                    pr_service.cleanup_task_workspace(task_id)
                except Exception as cleanup_e:
                    logger.warning(f"Cleanup failed: {cleanup_e}")
                
                return {
                    "status": "error",
                    "task_id": task_id,
                    "error": str(e)
                }
    
    def _process_agents_simple(
        self, 
        task_id: str, 
        task_db, 
        pr_result, 
        prompts: Dict[str, str], 
        db: DatabaseManager
    ) -> Dict[str, Dict]:
        """Process agents using simple subprocess calls to Docker CLI."""
        
        agent_results = {}
        
        # Prepare shared task data
        task_data = {
            "pr_url": task_db.pr_url,
            "max_files": min(getattr(task_db, 'max_files', 5), 5),
            "rubric": task_db.rubric,
            "prompts": prompts,
            "pr_result": {
                "repo_path": str(pr_result.repo_path),
                "changed_files": pr_result.changed_files,
                "repo_full_name": pr_result.repo_full_name,
                "pr_number": pr_result.pr_number
            }
        }
        
        # Process each agent
        for agent_name_str in task_db.agents:
            try:
                agent_name = AgentName(agent_name_str)
                logger.info(f"Processing agent: {agent_name.value}")
                
                # Log agent start
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'AGENT_STARTED', 
                    f'Starting {agent_name.value} agent'
                ))
                
                # Create agent-specific task data
                agent_task_data = {
                    **task_data,
                    "task_id": task_id,
                    "agent_name": agent_name.value
                }
                
                # Process agent using subprocess (fork-safe)
                result = self._run_agent_container(
                    task_id, agent_name.value.lower(), agent_task_data
                )
                
                agent_results[agent_name.value] = result
                
                # Log agent completion
                status = result.get("status", "unknown")
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'AGENT_PROCESSED', 
                    f'{agent_name.value} completed with status: {status}'
                ))
                
                if status == "success":
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'AGENT_SUCCESS',
                        f'{agent_name.value} evaluation completed successfully'
                    ))
                else:
                    error_msg = result.get("error", "Unknown error")
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'AGENT_FAILED',
                        f'{agent_name.value} failed: {error_msg}'
                    ))
                
            except Exception as e:
                logger.error(f"Failed to process agent {agent_name_str}: {e}")
                agent_results[agent_name_str] = {"status": "failed", "error": str(e)}
        
        return agent_results
    
    def _run_agent_container(
        self, 
        task_id: str, 
        agent_type: str, 
        task_data: Dict
    ) -> Dict[str, str]:
        """Run a single agent container using subprocess (fork-safe)."""
        
        try:
            # Create agent directory in storage
            agent_dir = Path(settings.run_root) / task_id / "agents" / agent_type
            agent_dir.mkdir(parents=True, exist_ok=True)
            
            # Create log files for container output
            container_stdout_file = agent_dir / "container_stdout.log"
            container_stderr_file = agent_dir / "container_stderr.log"
            
            # Create temporary file for task data
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(task_data, f, indent=2, default=str)
                task_data_file = f.name
            
            container_name = f'agent-{agent_type}-{task_id}-{int(time.time())}'
            
            # Build Docker command using subprocess (fork-safe)
            docker_cmd = [
                'docker', 'run',
                '--rm',  # Auto-remove when stopped
                '--name', container_name,
                '--memory', '3g',
                '--cpus', '2.0',
                '-v', f'{task_data_file}:/agent/task_data.json:ro',
                '-e', f'AGENT_TYPE={agent_type}',
                '-e', f'TASK_DATA_FILE=/agent/task_data.json',
                '-e', 'ORCHESTRATOR_URL=http://host.docker.internal:8000',
            ]
            
            # Add iFlow-specific environment variables
            if agent_type == 'iflow' and settings.iflow_api_key:
                docker_cmd.extend([
                    '-e', f'IFLOW_API_KEY={settings.iflow_api_key}',
                    '-e', f'IFLOW_BASE_URL={settings.iflow_base_url}',
                    '-e', f'IFLOW_MODEL_NAME={settings.iflow_model_name}',
                ])
            
            docker_cmd.append(f'{agent_type}-agent:latest')
            
            logger.info(f"Running Docker command: {' '.join(docker_cmd)}")
            
            # Track running container
            self.running_containers[task_id] = container_name
            
            start_time = time.time()
            
            # Run container with timeout
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=settings.task_timeout_seconds,
                check=False
            )
            
            execution_time = time.time() - start_time
            
            # Remove from tracking
            self.running_containers.pop(task_id, None)
            
            # Write container output to log files
            try:
                with open(container_stdout_file, 'w', encoding='utf-8') as f:
                    f.write(result.stdout)
                with open(container_stderr_file, 'w', encoding='utf-8') as f:
                    f.write(result.stderr if result.stderr else "")
                logger.info(f"Saved container logs to {agent_dir}")
            except Exception as e:
                logger.warning(f"Failed to write container logs: {e}")
            
            # Clean up task data file
            try:
                Path(task_data_file).unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup task data file: {e}")
            
            if result.returncode == 0:
                logger.info(f"Agent {agent_type} completed successfully in {execution_time:.1f}s")
                return {
                    "status": "success",
                    "exit_code": result.returncode,
                    "execution_time": execution_time,
                    "stdout": result.stdout[-1000:],  # Last 1KB
                    "stderr": result.stderr[-1000:] if result.stderr else "",
                    "log_dir": str(agent_dir)
                }
            else:
                logger.error(f"Agent {agent_type} failed with exit code {result.returncode}")
                logger.error(f"Container stderr: {result.stderr[:500]}")
                return {
                    "status": "failed",
                    "exit_code": result.returncode,
                    "error": f"Container exited with code {result.returncode}",
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:] if result.stderr else "",
                    "log_dir": str(agent_dir)
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"Agent {agent_type} timed out")
            # Try to stop the container
            try:
                subprocess.run(['docker', 'stop', container_name], timeout=30)
            except Exception as e:
                logger.warning(f"Failed to stop timed out container: {e}")
            
            return {
                "status": "failed",
                "error": "Container execution timeout"
            }
            
        except Exception as e:
            logger.error(f"Failed to run {agent_type} container: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _cleanup_task_containers(self, task_id: str):
        """Cleanup any running containers for the task."""
        container_name = self.running_containers.get(task_id)
        if container_name:
            try:
                subprocess.run(['docker', 'stop', container_name], timeout=30)
                logger.info(f"Stopped container: {container_name}")
            except Exception as e:
                logger.warning(f"Failed to stop container {container_name}: {e}")
            finally:
                self.running_containers.pop(task_id, None)
    
    def _judge_results(
        self, 
        task_id: str, 
        successful_agents: List[str], 
        db: DatabaseManager, 
        judge_service
    ):
        """Judge the results from successful agents."""
        logger.info(f"Judging results for task {task_id}: {successful_agents}")
        
        # Get rubric dimensions from task
        task_db = db.get_task(UUID(task_id))
        if not task_db:
            raise ValueError(f"Task {task_id} not found")
        
        rubric = [RubricDimension(dim) for dim in task_db.rubric]
        
        # Process each agent's results
        for agent_name in successful_agents:
            try:
                logger.info(f"Judging {agent_name} results")
                
                # Get agent runs for task
                agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                agent_run = next((run for run in agent_runs if run.agent == agent_name), None)
                
                if not agent_run:
                    logger.warning(f"Agent run not found for {agent_name}")
                    continue
                
                # Use placeholder scoring for now
                scores_dict = {dim.value: 0.8 for dim in rubric}
                overall_score = 0.8
                passed = True
                
                # Store score in database
                score_data = {
                    "agent_run_id": agent_run.id,
                    "task_id": UUID(task_id),
                    "agent": AgentName(agent_name),
                    "scores": scores_dict,
                    "overall_score": overall_score,
                    "passed": passed,
                    "judge_type": "simple_placeholder",
                    "judge_model": None,
                    "rationale": f"Simple execution completed successfully for {agent_name}"
                }
                
                db.create_score(score_data)
                
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'AGENT_JUDGED', 
                    f'Judged {agent_name}: Overall score {overall_score:.2f}, Passed: {passed}'
                ))
                
            except Exception as e:
                logger.error(f"Failed to judge {agent_name}: {e}")
    
    def _create_fallback_prompts(self, pr_result) -> Dict[str, str]:
        """Create minimal fallback prompts if prompt generation fails."""
        return {
            "precompression": f"Analyze PR {pr_result.pr_number} in {pr_result.repo_full_name}",
            "deepdive": "Provide technical analysis of the code changes",
            "memory_only": "Based on memory only, recall the PR analysis",
            "evaluator_set": "Answer questions about the PR from memory"
        }


# Global simple task queue instance
simple_queue = SimpleTaskQueue(max_workers=2)


def process_task_simple(task_id: str, **kwargs):
    """
    Queue a task for simple background processing.
    
    Args:
        task_id: Task identifier
        **kwargs: Additional arguments
    """
    simple_queue.enqueue_task(task_id, **kwargs)
    return {"status": "queued", "task_id": task_id}


# Export for use
__all__ = [
    "SimpleTaskQueue",
    "SimpleWorker", 
    "process_task_simple",
    "simple_queue"
]
