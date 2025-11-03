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
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
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
from app.agents.registry import get_agent_registry
from app.agents.base import AgentSession

logger = logging.getLogger(__name__)
def run_agent_process(task_id: str, agent_type: str, task_data: Dict) -> Dict[str, str]:
    """Run a single agent in a separate process and return its result dict."""
    import time
    from uuid import UUID
    from pathlib import Path
    from sqlmodel import Session
    from app.infrastructure.database import engine, DatabaseManager
    from app.domain.entities import AgentName, AgentRunStatus, RubricDimension
    from app.agents.registry import get_agent_registry, initialize_agent_registry
    from app.config import settings
    
    # Ensure registry is initialized in subprocess
    try:
        initialize_agent_registry()
    except Exception:
        pass
    
    try:
        start_time = time.time()
        # Resolve agent enum robustly
        def coerce_agent_enum(agent_str: str) -> AgentName:
            try:
                return AgentName(agent_str)
            except Exception:
                pass
            try:
                return AgentName[agent_str.upper()]
            except Exception:
                pass
            for member in AgentName:
                if str(member.value).lower() == agent_str.lower() or member.name.lower() == agent_str.lower():
                    return member
            raise ValueError(f"Unknown agent: {agent_str}")
        
        agent_name = coerce_agent_enum(agent_type)
        agent_registry = get_agent_registry()
        agent = agent_registry.get_agent(agent_name)
        
        # Update agent run status to RUNNING in database
        with Session(engine) as db_session:
            db = DatabaseManager(db_session)
            agent_runs = db.get_agent_runs_for_task(UUID(task_id))
            agent_run = next((r for r in agent_runs if (r.agent.value if hasattr(r.agent, 'value') else r.agent) == agent_name.value), None)
            if agent_run:
                db.update_agent_run(agent_run.id, {"status": AgentRunStatus.RUNNING})
        
        # Prepare session-like object
        repo_dir = Path(task_data['pr_result']['repo_path'])
        agent_dir = Path(settings.run_root) / task_id / "agents" / agent_name.value.lower()
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        session = type('AgentSession', (), {
            'task_id': UUID(task_id),
            'agent_run_id': UUID(task_data.get('agent_run_id', task_id)),
            'repo_dir': repo_dir,
            'output_dir': agent_dir,
            'prompts': task_data.get('prompts', {}),
            'timeout': settings.agent_session_timeout
        })()
        
        # Run the agent
        result = agent.run_session(session)
        exec_time = time.time() - start_time
        
        # Persist results
        with Session(engine) as db_session:
            db = DatabaseManager(db_session)
            agent_runs = db.get_agent_runs_for_task(UUID(task_id))
            agent_run = next((r for r in agent_runs if (r.agent.value if hasattr(r.agent, 'value') else r.agent) == agent_name.value), None)
            if result.get("artifacts"):
                if agent_run:
                    db.update_agent_run(agent_run.id, {
                        "status": AgentRunStatus.DONE,
                        "artifacts": result.get("artifacts", {}),
                        "stats": result.get("stats", {}),
                        "milestones": {f"milestone_{i}": m for i, m in enumerate(result.get("milestones", []))}
                    })
                return {
                    "status": "success",
                    "execution_time": exec_time,
                    "artifacts": result.get("artifacts", {}),
                    "stats": result.get("stats", {}),
                    "milestones": result.get("milestones", []),
                    "compression_detected": result.get("compression_detected", False),
                }
            else:
                if agent_run:
                    db.update_agent_run(agent_run.id, {
                        "status": AgentRunStatus.ERROR,
                        "error_message": result.get("error", "Agent execution failed")
                    })
                return {"status": "failed", "error": result.get("error", "Agent execution failed")}
    except Exception as e:
        # On error, persist in DB if possible
        try:
            with Session(engine) as db_session:
                db = DatabaseManager(db_session)
                agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                agent_run = next((r for r in agent_runs if (r.agent.value if hasattr(r.agent, 'value') else r.agent) == agent_type), None)
                if agent_run:
                    db.update_agent_run(agent_run.id, {"status": AgentRunStatus.ERROR, "error_message": str(e)})
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}


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
                
                # Step 4: Judging summary (agents are now judged immediately upon completion)
                successful_agents = [
                    name for name, result in agent_results.items()
                    if result.get("status") == "success"
                ]
                
                if successful_agents:
                    logger.info(f"All agents completed. {len(successful_agents)} successful agents were judged immediately.")
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'JUDGING_COMPLETED', f'{len(successful_agents)} agent(s) were judged immediately upon completion'
                    ))
                    self.task_logger.log_progress_update('judging', 95, 'All agents judged')
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
        """Process agents in parallel using dual executor pattern for true parallelism."""
        
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
        
        # Dual executor pattern: one for agents (processes), one for judging (threads)
        # This ensures true parallelism - agents run in parallel AND judging happens in parallel
        with ProcessPoolExecutor(max_workers=len(task_db.agents)) as agent_executor, \
             ThreadPoolExecutor(max_workers=len(task_db.agents)) as judge_executor:
            
            # Phase 1: Submit all agents for parallel execution
            agent_futures = {}
            for agent_name_str in task_db.agents:
                try:
                    agent_name = AgentName(agent_name_str)
                    logger.info(f"Submitting agent for parallel execution: {agent_name.value}")
                    
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
                    
                    # Submit agent to run in a separate process
                    future = agent_executor.submit(run_agent_process, task_id, agent_name.value, agent_task_data)
                    agent_futures[future] = agent_name.value
                    
                except Exception as e:
                    logger.error(f"Failed to submit agent {agent_name_str}: {e}")
                    agent_results[agent_name_str] = {"status": "failed", "error": str(e)}
            
            logger.info(f"Waiting for {len(agent_futures)} agents to complete in parallel...")
            
            # Phase 2: As each agent completes, immediately submit judging (non-blocking)
            judge_futures = {}
            for future in as_completed(agent_futures):
                agent_name = agent_futures[future]
                try:
                    result = future.result()
                    agent_results[agent_name] = result
                    
                    # Log agent completion
                    status = result.get("status", "unknown")
                    asyncio.run(self.task_logger.log_task_event(
                        task_id, 'AGENT_PROCESSED', 
                        f'{agent_name} completed with status: {status}'
                    ))
                    
                    if status == "success":
                        asyncio.run(self.task_logger.log_task_event(
                            task_id, 'AGENT_SUCCESS',
                            f'{agent_name} evaluation completed successfully'
                        ))
                        
                        # Submit judging to separate thread pool (NON-BLOCKING!)
                        # This allows other agents to be judged in parallel
                        logger.info(f"Submitting {agent_name} for parallel judging")
                        judge_future = judge_executor.submit(
                            self._judge_single_agent_wrapper,
                            task_id, agent_name, db
                        )
                        judge_futures[judge_future] = agent_name
                    else:
                        error_msg = result.get("error", "Unknown error")
                        asyncio.run(self.task_logger.log_task_event(
                            task_id, 'AGENT_FAILED',
                            f'{agent_name} failed: {error_msg}'
                        ))
                        
                except Exception as e:
                    logger.error(f"Failed to process agent {agent_name}: {e}")
                    agent_results[agent_name] = {"status": "failed", "error": str(e)}
            
            # Phase 3: Wait for all judging to complete
            logger.info(f"Waiting for {len(judge_futures)} agents to be judged in parallel...")
            for judge_future in as_completed(judge_futures):
                agent_name = judge_futures[judge_future]
                try:
                    judge_result = judge_future.result()
                    logger.info(f"Judging completed for {agent_name}: {judge_result}")
                except Exception as e:
                    logger.error(f"Failed to judge {agent_name}: {e}")
        
        return agent_results
    
    def _judge_single_agent_wrapper(self, task_id: str, agent_name: str, db: DatabaseManager):
        """Wrapper for judging a single agent - used by thread pool executor."""
        try:
            from app.services.judge_service import get_judge_service
            judge_service = get_judge_service()
            logger.info(f"Starting judging for {agent_name}")
            return self._judge_single_agent(task_id, agent_name, db, judge_service)
        except Exception as e:
            logger.error(f"Failed to judge {agent_name}: {e}", exc_info=True)
            raise
    
    def _coerce_agent_enum(self, agent_str: str) -> AgentName:
        """Convert arbitrary agent string to AgentName enum, case-insensitive and by name/value."""
        try:
            return AgentName(agent_str)  # direct by value
        except Exception:
            pass
        try:
            return AgentName[agent_str.upper()]  # by name
        except Exception:
            pass
        for member in AgentName:
            if str(member.value).lower() == agent_str.lower() or member.name.lower() == agent_str.lower():
                return member
        raise ValueError(f"Unknown agent: {agent_str}")

    def _run_agent_container(
        self, 
        task_id: str, 
        agent_type: str, 
        task_data: Dict
    ) -> Dict[str, str]:
        """Run a single agent using SDK (no Docker)."""
        
        try:
            start_time = time.time()
            
            # Get agent from registry
            agent_registry = get_agent_registry()
            agent_name = self._coerce_agent_enum(agent_type)
            agent = agent_registry.get_agent(agent_name)
            
            # Update agent run status to RUNNING in database
            with Session(engine) as db_session:
                db = DatabaseManager(db_session)
                agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                # Handle both string and enum types for agent
                agent_run = next((r for r in agent_runs if self._get_agent_name(r) == agent_type), None)
                if agent_run:
                    db.update_agent_run(agent_run.id, {"status": AgentRunStatus.RUNNING})
                    logger.info(f"Updated {agent_type} agent status to RUNNING")
            
            # Create agent directory in storage
            agent_dir = Path(settings.run_root) / task_id / "agents" / agent_name.value.lower()
            agent_dir.mkdir(parents=True, exist_ok=True)
            
            # Create AgentSession
            session = type('AgentSession', (), {
                'task_id': UUID(task_id),
                'agent_run_id': UUID(task_data.get('agent_run_id', task_id)),
                'repo_dir': Path(task_data['pr_result']['repo_path']),
                'output_dir': agent_dir,
                'prompts': task_data.get('prompts', {}),
                'timeout': settings.agent_session_timeout
            })()
            
            logger.info(f"Running {agent_type} agent with SDK (no Docker)")
            
            # Run the agent session directly
            result = agent.run_session(session)
            
            execution_time = time.time() - start_time
            
            if result.get("artifacts"):
                logger.info(f"Agent {agent_type} completed successfully in {execution_time:.1f}s")
                
                # Update agent run status to DONE in database
                with Session(engine) as db_session:
                    db = DatabaseManager(db_session)
                    agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                    agent_run = next((r for r in agent_runs if self._get_agent_name(r) == agent_type), None)
                    if agent_run:
                        db.update_agent_run(agent_run.id, {
                            "status": AgentRunStatus.DONE,
                            "artifacts": result.get("artifacts", {}),
                            "stats": result.get("stats", {}),
                            "milestones": {f"milestone_{i}": m for i, m in enumerate(result.get("milestones", []))}
                        })
                        logger.info(f"Updated {agent_type} agent status to DONE")
                
                return {
                    "status": "success",
                    "execution_time": execution_time,
                    "artifacts": result.get("artifacts", {}),
                    "stats": result.get("stats", {}),
                    "milestones": result.get("milestones", []),
                    "compression_detected": result.get("compression_detected", False),
                    "log_dir": str(agent_dir)
                }
            else:
                logger.error(f"Agent {agent_type} failed: {result.get('error', 'Unknown error')}")
                
                # Update agent run status to ERROR in database
                with Session(engine) as db_session:
                    db = DatabaseManager(db_session)
                    agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                    agent_run = next((r for r in agent_runs if self._get_agent_name(r) == agent_type), None)
                    if agent_run:
                        db.update_agent_run(agent_run.id, {
                            "status": AgentRunStatus.ERROR,
                            "error_message": result.get("error", "Agent execution failed")
                        })
                        logger.info(f"Updated {agent_type} agent status to ERROR")
                
                return {
                    "status": "failed",
                    "error": result.get("error", "Agent execution failed"),
                    "log_dir": str(agent_dir)
                }
                
        except Exception as e:
            logger.error(f"Failed to run {agent_type} agent: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Update agent run status to ERROR in database
            try:
                with Session(engine) as db_session:
                    db = DatabaseManager(db_session)
                    agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                    agent_run = next((r for r in agent_runs if self._get_agent_name(r) == agent_type), None)
                    if agent_run:
                        db.update_agent_run(agent_run.id, {
                            "status": AgentRunStatus.ERROR,
                            "error_message": str(e)
                        })
            except Exception as db_error:
                logger.error(f"Failed to update agent status in database: {db_error}")
            
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _cleanup_task_containers(self, task_id: str):
        """Cleanup method (no longer needed - kept for compatibility)."""
        # No Docker containers to clean up anymore
        self.running_containers.pop(task_id, None)
    
    def _get_agent_name(self, agent_run) -> str:
        """Safely extract agent name from agent run, handling both string and enum types."""
        if hasattr(agent_run.agent, 'value'):
            return agent_run.agent.value
        else:
            return str(agent_run.agent)
    
    def _get_agent_status(self, agent_run) -> str:
        """Safely extract agent status from agent run, handling both string and enum types."""
        if hasattr(agent_run.status, 'value'):
            return agent_run.status.value
        else:
            return str(agent_run.status)
    
    def _safe_get_enum_value(self, enum_field) -> str:
        """Safely get the value from an enum field, handling both enum and string types."""
        if hasattr(enum_field, 'value'):
            return enum_field.value
        else:
            return str(enum_field)
    
    def _judge_single_agent(
        self, 
        task_id: str, 
        agent_name: str, 
        db: DatabaseManager, 
        judge_service
    ):
        """Judge a single agent's results immediately upon completion."""
        try:
            logger.info(f"Judging {agent_name} results")
            
            # Create a new database session for thread safety
            from sqlmodel import Session
            from app.infrastructure.database import engine, DatabaseManager
            
            with Session(engine) as judge_session:
                judge_db = DatabaseManager(judge_session)
                
                # Get rubric dimensions from task
                task_db = judge_db.get_task(UUID(task_id))
                if not task_db:
                    raise ValueError(f"Task {task_id} not found")
                
                rubric = [RubricDimension(dim) for dim in task_db.rubric]
                
                # Get thresholds from task (default to 0.7 for all dimensions if not set)
                if hasattr(task_db, 'rubric_thresholds') and task_db.rubric_thresholds:
                    thresholds = task_db.rubric_thresholds
                else:
                    thresholds = {dim: 0.7 for dim in rubric}
                
                # Get agent runs for task
                agent_runs = judge_db.get_agent_runs_for_task(UUID(task_id))
                agent_run = next((run for run in agent_runs if self._get_agent_name(run) == agent_name), None)
                
                if not agent_run:
                    logger.warning(f"Agent run not found for {agent_name}")
                    return
                
                # Try to use LLM judge first, fallback to heuristic if no evaluation data
                try:
                    # Extract evaluation data from agent run artifacts
                    from app.config import settings
                    questions, pre_answers, post_answers = self._extract_evaluation_data(agent_run)
                    
                    # Store Q&A interactions in database
                    if questions and post_answers:
                        qa_interactions = []
                        for i, (q, a) in enumerate(zip(questions, post_answers)):
                            qa_interactions.append({
                                "turn": i + 1,
                                "question": q,
                                "answer": a,
                                "ground_truth": pre_answers[i] if i < len(pre_answers) else None
                            })
                        
                        # Update agent_run with Q&A interactions
                        db.update_agent_run(agent_run.id, {"qa_interactions": qa_interactions})
                        logger.info(f"Stored {len(qa_interactions)} Q&A interactions for {agent_name}")
                    
                    if questions and post_answers:
                        # Use LLM judge
                        logger.info(f"Using LLM judge for {agent_name}")
                        scores, rationale, judge_type_used = judge_service.evaluate_agent_performance(
                            questions=questions,
                            pre_compression_answers=pre_answers,
                            post_compression_answers=post_answers,
                            rubric=rubric,
                            judge_type=settings.default_judge
                        )
                        
                        # Create Score entity to validate against thresholds
                        from app.domain.entities import Score
                        score_entity = Score(
                            agent_run_id=agent_run.id,
                            task_id=UUID(task_id),
                            agent=AgentName(agent_name),
                            scores=scores,  # Dict[RubricDimension, float]
                            judge_type=judge_type_used,
                            judge_model=settings.judge_model if judge_type_used == "llm" else None,
                            rationale=rationale
                        )
                        
                        # Calculate overall score and validate against thresholds
                        score_entity.calculate_overall_score(thresholds)
                        
                        # Convert scores dict to serializable format
                        scores_dict = {}
                        for dim, score in scores.items():
                            if hasattr(dim, 'value'):
                                scores_dict[dim.value] = score
                            else:
                                scores_dict[str(dim)] = score
                        
                        overall_score = score_entity.overall_score
                        passed = score_entity.passed
                        
                        # Log breaking analysis if failed
                        if not passed:
                            logger.warning(
                                f"Agent {agent_name} FAILED - Breaking dimensions: "
                                f"{', '.join(score_entity.breaking_dimensions)}"
                            )
                            for detail in score_entity.breaking_details.values():
                                logger.info(f"  {detail}")
                        
                    else:
                        # Fallback to heuristic evaluation
                        logger.info(f"No evaluation data found for {agent_name}, using heuristic judge")
                        scores_dict_temp, _, _, rationale = self._evaluate_agent_run(
                            agent_run, rubric
                        )
                        judge_type_used = "heuristic"
                        
                        # Convert scores back to RubricDimension keys for Score entity
                        scores = {RubricDimension(k): v for k, v in scores_dict_temp.items()}
                        
                        # Create Score entity to validate against thresholds
                        from app.domain.entities import Score
                        score_entity = Score(
                            agent_run_id=agent_run.id,
                            task_id=UUID(task_id),
                            agent=AgentName(agent_name),
                            scores=scores,
                            judge_type=judge_type_used,
                            rationale=rationale
                        )
                        score_entity.calculate_overall_score(thresholds)
                        
                        scores_dict = scores_dict_temp
                        overall_score = score_entity.overall_score
                        passed = score_entity.passed
                        
                        # Log breaking analysis if failed
                        if not passed:
                            logger.warning(
                                f"Agent {agent_name} FAILED - Breaking dimensions: "
                                f"{', '.join(score_entity.breaking_dimensions)}"
                            )
                            for detail in score_entity.breaking_details.values():
                                logger.info(f"  {detail}")
                        
                except Exception as e:
                    logger.warning(f"LLM judge failed for {agent_name}, using heuristic fallback: {e}")
                    scores_dict_temp, _, _, rationale = self._evaluate_agent_run(
                        agent_run, rubric
                    )
                    judge_type_used = "heuristic"
                    
                    # Convert scores back to RubricDimension keys for Score entity
                    scores = {RubricDimension(k): v for k, v in scores_dict_temp.items()}
                    
                    # Create Score entity to validate against thresholds
                    from app.domain.entities import Score
                    score_entity = Score(
                        agent_run_id=agent_run.id,
                        task_id=UUID(task_id),
                        agent=AgentName(agent_name),
                        scores=scores,
                        judge_type=judge_type_used,
                        rationale=rationale
                    )
                    score_entity.calculate_overall_score(thresholds)
                    
                    scores_dict = scores_dict_temp
                    overall_score = score_entity.overall_score
                    passed = score_entity.passed
                    
                    # Log breaking analysis if failed
                    if not passed:
                        logger.warning(
                            f"Agent {agent_name} FAILED - Breaking dimensions: "
                            f"{', '.join(score_entity.breaking_dimensions)}"
                        )
                        for detail in score_entity.breaking_details.values():
                            logger.info(f"  {detail}")
                
                # Store score in database with breaking analysis
                score_data = {
                    "agent_run_id": agent_run.id,
                    "task_id": UUID(task_id),
                    "agent": AgentName(agent_name),
                    "scores": scores_dict,
                    "overall_score": overall_score,
                    "passed": passed,
                    "judge_type": judge_type_used,
                    "judge_model": settings.judge_model if judge_type_used == "llm" else None,
                    "rationale": rationale,
                    "breaking_dimensions": score_entity.breaking_dimensions if 'score_entity' in locals() else [],
                    "breaking_details": score_entity.breaking_details if 'score_entity' in locals() else {},
                    "thresholds_used": {dim.value: threshold for dim, threshold in (score_entity.thresholds_used.items() if 'score_entity' in locals() else {})}
                }
                
                judge_db.create_score(score_data)
                
                asyncio.run(self.task_logger.log_task_event(
                    task_id, 'AGENT_JUDGED', 
                    f'Judged {agent_name}: Overall score {overall_score:.2f}, Passed: {passed}'
                ))
                
                logger.info(f"Successfully judged {agent_name}: score={overall_score:.2f}, passed={passed}")
            
        except Exception as e:
            logger.error(f"Failed to judge {agent_name}: {e}")
    
    def _judge_results(
        self, 
        task_id: str, 
        successful_agents: List[str], 
        db: DatabaseManager, 
        judge_service
    ):
        """Judge the results from successful agents (batch mode - kept for compatibility)."""
        logger.info(f"Judging results for task {task_id}: {successful_agents}")
        
        # Process each agent's results
        for agent_name in successful_agents:
            self._judge_single_agent(task_id, agent_name, db, judge_service)
    
    def _create_fallback_prompts(self, pr_result) -> Dict[str, str]:
        """Create minimal fallback prompts if prompt generation fails."""
        return {
            "precompression": f"Analyze PR {pr_result.pr_number} in {pr_result.repo_full_name}",
            "deepdive": "Provide technical analysis of the code changes",
            "memory_only": "Based on memory only, recall the PR analysis",
            "evaluator_set": "Answer questions about the PR from memory"
        }
    
    def _evaluate_agent_run(self, agent_run, rubric: List[RubricDimension]) -> Tuple[Dict[str, float], float, bool, str]:
        """
        Evaluate an agent run using heuristic or LLM judge.
        
        Returns:
            Tuple of (scores_dict, overall_score, passed, rationale)
        """
        from app.services.judge_service import JudgeService
        
        # For now, use a simplified heuristic evaluation based on agent stats
        # In a full implementation, we would extract Q&A from transcripts
        
        stats = agent_run.stats or {}
        milestones = agent_run.milestones or {}
        
        # Calculate scores based on agent performance
        scores = {}
        
        # Get agent status safely
        agent_status = self._get_agent_status(agent_run)
        
        for dim in rubric:
            dim_value = self._safe_get_enum_value(dim)
            
            if dim == RubricDimension.AR:  # Accuracy & Relevance
                # Score based on completion and error-free execution
                score = 0.8 if agent_status == "done" else 0.3
                if stats.get("compression_detected"):
                    score += 0.1  # Bonus for handling compression
                scores[dim_value] = min(1.0, score)
                
            elif dim == RubricDimension.TTL:  # Token-to-Learning efficiency
                # Score based on token usage efficiency
                total_tokens = int(stats.get("total_tokens_estimate", 0)) if stats.get("total_tokens_estimate") else 0
                deep_dive_iterations = int(stats.get("deep_dive_iterations", 0)) if stats.get("deep_dive_iterations") else 0
                if deep_dive_iterations > 0:
                    # More iterations with reasonable token usage = better
                    score = min(1.0, (deep_dive_iterations / 10.0) * 0.8)
                else:
                    score = 0.5
                scores[dim_value] = score
                
            elif dim == RubricDimension.LRU:  # Long-term Retention & Understanding
                # Score based on memory-only evaluation completion
                has_memory_eval = "memory_only" in [m for m in milestones.values()] if isinstance(milestones, dict) else "memory_only" in milestones
                score = 0.9 if has_memory_eval else 0.5
                scores[dim_value] = score
                
            elif dim == RubricDimension.SF:  # Scalability & Future-proofing
                # Score based on handling large context and compression
                compression_detected = str(stats.get("compression_detected", "False")).lower() == "true"
                max_tokens = int(stats.get("max_tokens_configured", 200000)) if stats.get("max_tokens_configured") else 200000
                total_tokens = int(stats.get("total_tokens_estimate", 0)) if stats.get("total_tokens_estimate") else 0
                
                if compression_detected:
                    score = 0.9  # Successfully handled compression
                elif total_tokens > max_tokens * 0.7:
                    score = 0.7  # Used significant portion of context
                else:
                    score = 0.6
                scores[dim_value] = score
        
        # Calculate overall score as average
        overall_score = sum(scores.values()) / len(scores) if scores else 0.0
        passed = overall_score >= 0.6
        
        # Generate rationale
        rationale = f"Agent completed with {agent_run.status.value if hasattr(agent_run.status, 'value') else agent_run.status} status. "
        if stats.get("compression_detected"):
            rationale += "Successfully handled context compression. "
        if stats.get("deep_dive_iterations"):
            rationale += f"Completed {stats['deep_dive_iterations']} deep-dive iterations. "
        rationale += f"Overall score: {overall_score:.2f}"
        
        agent_name = self._get_agent_name(agent_run)
        logger.info(f"Evaluated {agent_name}: overall={overall_score:.2f}, scores={scores}")
        
        return scores, overall_score, passed, rationale
    
    def _extract_evaluation_data(self, agent_run) -> tuple:
        """Extract real evaluation Q&A from agent run."""
        
        stats = agent_run.stats or {}
        
        # Check for real Q&A data
        if "evaluation_qa" in stats:
            logger.info(f"Using REAL Q&A from agent execution")
            evaluation_qa = stats["evaluation_qa"]
            
            questions = [qa["question"] for qa in evaluation_qa]
            post_answers = [qa["answer"] for qa in evaluation_qa]
            
            # Pre-answers: empty for now (we only have post-compression answers)
            pre_answers = [""] * len(questions)
            
            logger.info(f"Extracted {len(questions)} real Q&A pairs")
            return questions, pre_answers, post_answers
        
        # Fallback: No real Q&A available
        agent_name = self._get_agent_name(agent_run)
        logger.warning(f"No real Q&A found in agent stats for {agent_name} - cannot judge properly")
        raise ValueError(f"Agent {agent_name} has no evaluation_qa data")


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
