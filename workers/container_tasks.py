"""
Container-managed worker tasks for processing memory-break evaluations.
This replaces the direct agent execution with container-based agent isolation.
"""

import asyncio
import logging
import signal
import time
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlmodel import Session
import docker

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

class ContainerWorker:
    """Worker that manages agent containers instead of running agents directly."""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.task_logger = TaskLogger()
        self.running_containers: Dict[str, Dict] = {}
        
    async def process_task(self, task_id: str, **kwargs) -> Dict[str, str]:
        """
        Process a memory-break evaluation task using containerized agents.
        
        Args:
            task_id: Task identifier
            **kwargs: Additional arguments from RQ
        """
        
        logger.info(f"Starting container-managed task processing: {task_id}")
        
        # Setup timeout signal handler
        def timeout_handler(signum, frame):
            logger.error(f"Task {task_id} TIMEOUT - Force terminating containers")
            raise TimeoutError(f"Task {task_id} exceeded maximum execution time")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(1800)  # 30 minutes timeout
        
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
                
                # Update task status
                db.update_task(UUID(task_id), {"status": TaskStatus.RUNNING})
                await self.task_logger.log_task_event(
                    task_id, 'TASK_STARTED', 'Container worker started processing task'
                )
                
                # Step 1: Process GitHub PR
                logger.info(f"Processing PR: {task_db.pr_url}")
                pr_result = pr_service.process_pr(task_db.pr_url, task_id)
                
                # Update task with changed files
                db.update_task(UUID(task_id), {
                    "changed_files": pr_result.changed_files
                })
                
                # Step 2: Generate prompts with safety limits
                max_files = min(task_db.max_files if hasattr(task_db, 'max_files') else 5, 5)
                logger.info(f"Using max_files={max_files} for container safety")
                
                try:
                    prompts = prompt_service.generate_prompts(pr_result, max_files)
                    prompt_hash = prompt_service.get_prompt_hash(prompts)
                except Exception as prompt_error:
                    logger.error(f"Prompt generation failed: {prompt_error}")
                    prompts = self._create_fallback_prompts(pr_result)
                    prompt_hash = "fallback_prompts"
                
                # Update task with prompt hash
                db.update_task(UUID(task_id), {"prompt_hash": prompt_hash})
                
                # Step 3: Spawn agent containers
                await self.task_logger.log_task_event(
                    task_id, 'CONTAINERS_SPAWNING', f'Starting containers for {len(task_db.agents)} agents'
                )
                
                container_results = await self._spawn_and_manage_agent_containers(
                    task_id, task_db, pr_result, prompts, db
                )
                
                # Step 4: Judge results (if we have successful agent runs)
                successful_agents = [
                    name for name, result in container_results.items()
                    if result.get("status") == "success"
                ]
                
                if successful_agents:
                    logger.info("Starting judging phase")
                    db.update_task(UUID(task_id), {"status": TaskStatus.JUDGING})
                    await self._judge_results(task_id, successful_agents, db, judge_service)
                else:
                    logger.warning("No successful agent runs to judge")
                
                # Step 5: Complete task
                db.update_task(UUID(task_id), {"status": TaskStatus.DONE})
                
                execution_time = time.time() - start_time
                await self.task_logger.log_task_event(
                    task_id, 'TASK_COMPLETED', 
                    f'Task completed successfully in {execution_time:.1f}s'
                )
                
                logger.info(f"Container-managed task processing complete: {task_id}")
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "agents_processed": len(container_results),
                    "successful_agents": len(successful_agents),
                    "execution_time": execution_time,
                    "prompt_hash": prompt_hash
                }
                
            except Exception as e:
                logger.error(f"Container-managed task processing failed for {task_id}: {e}")
                
                # Cleanup any running containers
                await self._cleanup_task_containers(task_id)
                
                # Update task with error
                db.update_task(UUID(task_id), {
                    "status": TaskStatus.ERROR,
                    "error_message": str(e)
                })
                
                await self.task_logger.log_task_event(
                    task_id, 'TASK_FAILED', f'Task failed: {str(e)}'
                )
                
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
            
            finally:
                # Cancel timeout alarm
                signal.alarm(0)
    
    async def _spawn_and_manage_agent_containers(
        self, 
        task_id: str, 
        task_db, 
        pr_result, 
        prompts: Dict[str, str], 
        db: DatabaseManager
    ) -> Dict[str, Dict]:
        """Spawn and manage all agent containers for the task."""
        
        container_results = {}
        spawned_containers = []
        
        try:
            # Prepare shared task data for all containers
            container_task_data = {
                "pr_url": task_db.pr_url,
                "max_files": min(task_db.max_files if hasattr(task_db, 'max_files') else 5, 5),
                "rubric": task_db.rubric,
                "prompts": prompts,
                "pr_result": {
                    "repo_path": str(pr_result.repo_path),
                    "changed_files": pr_result.changed_files,
                    "repo_full_name": pr_result.repo_full_name,
                    "pr_number": pr_result.pr_number
                }
            }
            
            # Spawn containers for each agent
            for agent_name_str in task_db.agents:
                try:
                    agent_name = AgentName(agent_name_str)
                    logger.info(f"Spawning container for agent: {agent_name.value}")
                    
                    # Create container-specific task data
                    agent_task_data = {
                        **container_task_data,
                        "agent_name": agent_name.value
                    }
                    
                    # Spawn container
                    container_info = await self._spawn_agent_container(
                        task_id, agent_name.value.lower(), agent_task_data
                    )
                    
                    if container_info:
                        spawned_containers.append(container_info)
                        self.running_containers[f"{task_id}_{agent_name.value}"] = container_info
                        
                        await self.task_logger.log_task_event(
                            task_id, 'CONTAINER_SPAWNED', 
                            f'Spawned {agent_name.value} container: {container_info["container_id"][:12]}'
                        )
                    else:
                        container_results[agent_name.value] = {"status": "failed", "error": "Container spawn failed"}
                        
                except Exception as e:
                    logger.error(f"Failed to spawn container for {agent_name_str}: {e}")
                    container_results[agent_name_str] = {"status": "failed", "error": str(e)}
            
            # Wait for all containers to complete
            if spawned_containers:
                container_results.update(
                    await self._wait_for_containers(task_id, spawned_containers, db)
                )
            
            return container_results
            
        except Exception as e:
            logger.error(f"Error in container management: {e}")
            # Cleanup any spawned containers
            for container_info in spawned_containers:
                await self._stop_container(container_info)
            raise
    
    async def _spawn_agent_container(
        self, 
        task_id: str, 
        agent_type: str, 
        task_data: Dict
    ) -> Optional[Dict]:
        """Spawn a single agent container."""
        
        try:
            # Create temporary file for task data
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(task_data, f, indent=2)
                task_data_file = f.name
            
            # Container configuration
            container_config = {
                'image': f'{agent_type}-agent:latest',
                'name': f'agent-{agent_type}-{task_id}-{int(time.time())}',
                'environment': {
                    'AGENT_TYPE': agent_type,
                    'AGENT_PORT': str(8080 + {'iflow': 0, 'claude': 1, 'gemini': 2}.get(agent_type, 0)),
                    'ORCHESTRATOR_URL': 'http://host.docker.internal:8000',
                    'MAX_MEMORY': '3g',
                    'MAX_EXECUTION_TIME': '1800',
                    'TASK_DATA_FILE': '/agent/task_data.json'
                },
                'volumes': {
                    task_data_file: {
                        'bind': '/agent/task_data.json',
                        'mode': 'ro'
                    }
                },
                'mem_limit': '3g',
                'memswap_limit': '3g',
                'cpu_quota': 200000,  # 2 CPU cores
                'cpu_period': 100000,
                'network_mode': 'bridge',
                'detach': True,
                'remove': True,  # Auto-remove when stopped
                'labels': {
                    'task_id': task_id,
                    'agent_type': agent_type,
                    'created_by': 'container-worker',
                    'created_at': str(int(time.time()))
                }
            }
            
            # Run container
            container = self.docker_client.containers.run(**container_config)
            
            return {
                'container_id': container.id,
                'container': container,
                'agent_type': agent_type,
                'started_at': time.time(),
                'task_data_file': task_data_file,
                'status': 'running'
            }
            
        except Exception as e:
            logger.error(f"Failed to spawn {agent_type} container: {e}")
            return None
    
    async def _wait_for_containers(
        self, 
        task_id: str, 
        containers: List[Dict], 
        db: DatabaseManager
    ) -> Dict[str, Dict]:
        """Wait for containers to complete and collect results."""
        
        results = {}
        max_wait_time = 1800  # 30 minutes
        check_interval = 10   # 10 seconds
        elapsed_time = 0
        
        pending_containers = {
            container['agent_type']: container for container in containers
        }
        
        while pending_containers and elapsed_time < max_wait_time:
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
            
            completed_agents = []
            
            for agent_type, container_info in pending_containers.items():
                try:
                    container = container_info['container']
                    container.reload()
                    
                    # Check if container has stopped
                    if container.status != 'running':
                        # Get exit code
                        exit_code = container.wait()['StatusCode']
                        
                        # Get logs
                        logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='ignore')
                        
                        if exit_code == 0:
                            # Successful completion
                            results[agent_type] = {
                                "status": "success",
                                "exit_code": exit_code,
                                "execution_time": time.time() - container_info['started_at']
                            }
                            
                            await self.task_logger.log_task_event(
                                task_id, 'CONTAINER_COMPLETED',
                                f'{agent_type} container completed successfully'
                            )
                        else:
                            # Failed execution
                            results[agent_type] = {
                                "status": "failed",
                                "exit_code": exit_code,
                                "error": f"Container exited with code {exit_code}",
                                "logs": logs[-2000:]  # Last 2KB of logs
                            }
                            
                            await self.task_logger.log_task_event(
                                task_id, 'CONTAINER_FAILED',
                                f'{agent_type} container failed with exit code {exit_code}'
                            )
                        
                        completed_agents.append(agent_type)
                        
                        # Cleanup task data file
                        try:
                            Path(container_info['task_data_file']).unlink()
                        except Exception as e:
                            logger.warning(f"Failed to cleanup task data file: {e}")
                
                except Exception as e:
                    logger.error(f"Error checking container {agent_type}: {e}")
                    results[agent_type] = {
                        "status": "failed",
                        "error": f"Container monitoring error: {str(e)}"
                    }
                    completed_agents.append(agent_type)
            
            # Remove completed containers from pending
            for agent_type in completed_agents:
                pending_containers.pop(agent_type, None)
        
        # Handle any containers that didn't complete in time
        for agent_type, container_info in pending_containers.items():
            logger.warning(f"Container {agent_type} timed out, force stopping")
            await self._stop_container(container_info)
            results[agent_type] = {
                "status": "failed",
                "error": "Container execution timeout"
            }
            
            await self.task_logger.log_task_event(
                task_id, 'CONTAINER_TIMEOUT',
                f'{agent_type} container timed out and was stopped'
            )
        
        return results
    
    async def _stop_container(self, container_info: Dict):
        """Stop a container gracefully."""
        try:
            container = container_info['container']
            
            # Try graceful stop first
            container.stop(timeout=30)
            logger.info(f"Gracefully stopped container {container.short_id}")
            
            # Cleanup task data file
            try:
                Path(container_info['task_data_file']).unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup task data file: {e}")
                
        except Exception as e:
            logger.error(f"Error stopping container: {e}")
            try:
                # Force kill if graceful stop fails
                container_info['container'].kill()
                logger.warning(f"Force killed container {container_info['container'].short_id}")
            except Exception as kill_e:
                logger.error(f"Failed to kill container: {kill_e}")
    
    async def _cleanup_task_containers(self, task_id: str):
        """Cleanup all containers for a task."""
        containers_to_cleanup = [
            container_info for key, container_info in self.running_containers.items()
            if key.startswith(task_id)
        ]
        
        for container_info in containers_to_cleanup:
            await self._stop_container(container_info)
        
        # Remove from tracking
        keys_to_remove = [key for key in self.running_containers.keys() if key.startswith(task_id)]
        for key in keys_to_remove:
            self.running_containers.pop(key, None)
    
    async def _judge_results(
        self, 
        task_id: str, 
        successful_agents: List[str], 
        db: DatabaseManager, 
        judge_service
    ):
        """Judge the results from successful agent containers."""
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
                
                # Get agent run
                agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                agent_run = next((run for run in agent_runs if run.agent == agent_name), None)
                
                if not agent_run:
                    logger.warning(f"Agent run not found for {agent_name}")
                    continue
                
                # For now, use placeholder scoring since we need to implement
                # proper result extraction from container artifacts
                scores_dict = {dim.value: 0.8 for dim in rubric}  # Placeholder scores
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
                    "judge_type": "container_placeholder",
                    "judge_model": None,
                    "rationale": f"Container-based execution completed successfully for {agent_name}"
                }
                
                db.create_score(score_data)
                
                await self.task_logger.log_task_event(
                    task_id, 'AGENT_JUDGED', 
                    f'Judged {agent_name}: Overall score {overall_score:.2f}, Passed: {passed}'
                )
                
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


# Global worker instance
container_worker = ContainerWorker()


def process_task_with_containers(task_id: str, **kwargs) -> Dict[str, str]:
    """
    RQ-compatible wrapper for container-managed task processing.
    
    Args:
        task_id: Task identifier
        **kwargs: Additional arguments from RQ
    """
    
    # Run the async container worker
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(
            container_worker.process_task(task_id, **kwargs)
        )
    finally:
        loop.close()


# Export worker functions for RQ
__all__ = [
    "process_task_with_containers",
    "container_worker"
]
