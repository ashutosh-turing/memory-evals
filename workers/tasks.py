"""Background worker tasks for processing memory-break evaluations."""

import logging
import signal
import gc
import resource
import time
from pathlib import Path
from typing import Dict, List
from uuid import UUID

from sqlmodel import Session

from app.config import settings
from app.domain.entities import (
    AgentName, RubricDimension, TaskStatus, AgentRunStatus
)
from app.infrastructure.database import engine, DatabaseManager
from app.agents.registry import get_agent_registry
from app.agents.base import AgentSession
from app.services.pr_service import PRService
from app.services.prompt_service import get_prompt_service
from app.services.judge_service import get_judge_service

logger = logging.getLogger(__name__)


def process_task(task_id: str, **kwargs) -> Dict[str, str]:
    """
    Main worker task to process a memory-break evaluation with CRASH PROTECTION.
    
    This is the orchestrator that coordinates all components:
    1. Analyze GitHub PR
    2. Generate prompts
    3. Run agent sessions
    4. Evaluate results
    5. Store artifacts and scores
    
    Args:
        task_id: Task identifier
        **kwargs: Additional arguments from RQ (e.g., timeout) - ignored
    """
    
    logger.info(f"Starting SAFE MODE task processing: {task_id}")
    
    # CRITICAL: Set memory limits to prevent system crashes
    try:
        # Set memory limit to 2GB per worker process
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, -1))
        logger.info("Memory limit set to 2GB for worker safety")
    except Exception as e:
        logger.warning(f"Could not set memory limit: {e}")
    
    # CRITICAL: Setup timeout signal handler
    def timeout_handler(signum, frame):
        logger.error(f"Task {task_id} TIMEOUT - Force terminating")
        raise TimeoutError(f"Task {task_id} exceeded maximum execution time")
    
    # Set 30-minute timeout for the entire task
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(1800)  # 30 minutes
    
    start_time = time.time()
    initial_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    
    # Initialize services
    pr_service = PRService()
    prompt_service = get_prompt_service()
    judge_service = get_judge_service()
    agent_registry = get_agent_registry()
    
    with Session(engine) as session:
        db = DatabaseManager(session)
        
        try:
            # Get task from database
            task_db = db.get_task(UUID(task_id))
            if not task_db:
                raise ValueError(f"Task {task_id} not found")
            
            # Update task status
            db.update_task(UUID(task_id), {"status": TaskStatus.RUNNING})
            
            # CRITICAL: Monitor memory throughout execution
            def check_memory_and_gc():
                gc.collect()
                current_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                memory_mb = current_memory / 1024 if hasattr(resource, 'RUSAGE_SELF') else current_memory / 1024
                if memory_mb > 1500:  # 1.5GB warning threshold
                    logger.warning(f"HIGH MEMORY USAGE: {memory_mb:.1f}MB - forcing GC")
                    gc.collect()
                return memory_mb
            
            # Step 1: Process GitHub PR with memory monitoring
            logger.info(f"Processing PR: {task_db.pr_url}")
            check_memory_and_gc()
            
            pr_result = pr_service.process_pr(task_db.pr_url, task_id)
            
            # Update task with changed files
            db.update_task(UUID(task_id), {
                "changed_files": pr_result.changed_files
            })
            
            memory_after_pr = check_memory_and_gc()
            logger.info(f"Memory after PR processing: {memory_after_pr:.1f}MB")
            
            # Step 2: Generate prompts with EXTREME SAFETY
            max_files = task_db.max_files if hasattr(task_db, 'max_files') and task_db.max_files else settings.max_files_per_task
            # CRITICAL: Cap max_files at 5 for safety regardless of user input
            safe_max_files = min(max_files, 5)
            logger.info(f"SAFE MODE: Using max_files={safe_max_files} (requested: {max_files}) for crash prevention")
            
            try:
                prompts = prompt_service.generate_prompts(pr_result, safe_max_files)
                prompt_hash = prompt_service.get_prompt_hash(prompts)
                
                memory_after_prompts = check_memory_and_gc()
                logger.info(f"Memory after prompt generation: {memory_after_prompts:.1f}MB")
                
            except Exception as prompt_error:
                logger.error(f"PROMPT GENERATION FAILED: {prompt_error}")
                # Create minimal fallback prompts to prevent total failure
                prompts = {
                    "precompression": f"Analyze PR {pr_result.pr_number} in {pr_result.repo_full_name}",
                    "deepdive": "Provide technical analysis of the code changes",
                    "memory_only": "Based on memory only, recall the PR analysis",
                    "evaluator_set": "Answer questions about the PR from memory"
                }
                prompt_hash = "fallback_prompts"
                logger.warning("Using fallback prompts due to generation failure")
            
            # Update task with prompt hash
            db.update_task(UUID(task_id), {
                "prompt_hash": prompt_hash
            })
            
            # Step 3: Process each agent
            agent_results = {}
            
            for agent_name_str in task_db.agents:
                try:
                    agent_name = AgentName(agent_name_str)
                    logger.info(f"Processing agent: {agent_name.value}")
                    
                    # Run agent session
                    agent_result = run_agent_session(
                        task_id, agent_name, pr_result, prompts, db
                    )
                    agent_results[agent_name.value] = agent_result
                    
                except Exception as e:
                    logger.error(f"Failed to process agent {agent_name_str}: {e}")
                    # Update agent run with error
                    agent_runs = db.get_agent_runs_for_task(UUID(task_id))
                    for run in agent_runs:
                        if run.agent.value == agent_name_str:
                            db.update_agent_run(run.id, {
                                "status": AgentRunStatus.ERROR,
                                "error_message": str(e)
                            })
                            break
                    
                    agent_results[agent_name_str] = {"error": str(e)}
            
            # Step 4: Judge results (if we have successful agent runs)
            successful_agents = [
                name for name, result in agent_results.items()
                if "error" not in result
            ]
            
            if successful_agents:
                logger.info("Starting judging phase")
                db.update_task(UUID(task_id), {"status": TaskStatus.JUDGING})
                
                judge_results(task_id, successful_agents, db, judge_service)
            else:
                logger.warning("No successful agent runs to judge")
            
            # Step 5: Complete task
            db.update_task(UUID(task_id), {"status": TaskStatus.DONE})
            
            logger.info(f"Task processing complete: {task_id}")
            
            return {
                "status": "success",
                "task_id": task_id,
                "agents_processed": len(agent_results),
                "successful_agents": len(successful_agents),
                "prompt_hash": prompt_hash
            }
            
        except Exception as e:
            logger.error(f"Task processing failed for {task_id}: {e}")
            
            # Update task with error
            db.update_task(UUID(task_id), {
                "status": TaskStatus.ERROR,
                "error_message": str(e)
            })
            
            # Cleanup
            try:
                pr_service.cleanup_task_workspace(task_id)
            except Exception as cleanup_e:
                logger.warning(f"Cleanup failed: {cleanup_e}")
            
            return {
                "status": "error",
                "task_id": task_id,
                "error": str(e)
            }


def run_agent_session(
    task_id: str,
    agent_name: AgentName,
    pr_result,  # PRAnalysisResult
    prompts: Dict[str, str],
    db: DatabaseManager
) -> Dict[str, str]:
    """Run a complete agent session through all phases."""
    
    logger.info(f"Running {agent_name.value} session for task {task_id}")
    
    # Get agent runs for this task
    agent_runs = db.get_agent_runs_for_task(UUID(task_id))
    agent_run = next((run for run in agent_runs if run.agent == agent_name), None)
    
    if not agent_run:
        raise ValueError(f"Agent run not found for {agent_name.value}")
    
    try:
        # Get agent adapter
        agent_registry = get_agent_registry()
        agent = agent_registry.get_agent(agent_name)
        
        # Update agent run status
        db.update_agent_run(agent_run.id, {"status": AgentRunStatus.RUNNING})
        
        # Create isolated repository copy for this agent
        pr_service = PRService()
        agent_repo_path = pr_service.create_agent_repo_copy(
            task_id=task_id,
            agent_name=agent_name.value,
            agent_run_id=str(agent_run.id),
            master_repo_path=pr_result.repo_path
        )
        
        # Setup agent session with isolated repository
        task_dir = Path(settings.run_root).expanduser() / task_id
        agent_output_dir = task_dir / "agents" / agent_name.value
        
        # Create AgentSession with isolated repo
        session = type('AgentSession', (), {
            'task_id': UUID(task_id),
            'agent_run_id': agent_run.id,
            'repo_dir': agent_repo_path,  # ← Now points to isolated copy!
            'output_dir': agent_output_dir,
            'prompts': {
                'pre': prompts.get('precompression', ''),
                'deep': prompts.get('deepdive', ''),
                'memory_only': prompts.get('memory_only', ''),
                'eval': prompts.get('evaluator_set', '')
            },
            'timeout': settings.agent_session_timeout
        })()
        
        # Run the agent session
        logger.info(f"Starting {agent_name.value} agent session")
        result = agent.run_session(session)
        
        # Update agent run with results
        artifacts = result.get("artifacts", {})
        stats = result.get("stats", {})
        milestones = result.get("milestones", [])
        
        # Convert milestone list to dict with timestamps
        milestone_dict = {}
        for i, milestone in enumerate(milestones):
            milestone_dict[f"milestone_{i}_{milestone}"] = str(agent_run.updated_at)
        
        # Store compression detection status
        if result.get("compression_detected", False):
            db.update_agent_run(agent_run.id, {"status": AgentRunStatus.MEMORY_ONLY})
        
        # Update with final results
        db.update_agent_run(agent_run.id, {
            "status": AgentRunStatus.DONE,
            "artifacts": artifacts,
            "stats": stats,
            "milestones": milestone_dict
        })
        
        # Create artifact records in database
        for artifact_name, artifact_path in artifacts.items():
            if artifact_path and Path(artifact_path).exists():
                artifact_data = {
                    "agent_run_id": agent_run.id,
                    "task_id": UUID(task_id),
                    "agent": agent_name,
                    "name": artifact_name,
                    "file_path": artifact_path,
                    "file_type": artifact_name,
                    "size_bytes": Path(artifact_path).stat().st_size
                }
                db.create_artifact(artifact_data)
        
        logger.info(f"Successfully completed {agent_name.value} session")
        
        return {
            "status": "success",
            "agent": agent_name.value,
            "artifacts": artifacts,
            "stats": stats,
            "compression_detected": result.get("compression_detected", False)
        }
        
    except Exception as e:
        logger.error(f"Agent session failed for {agent_name.value}: {e}")
        
        # Update agent run with error
        db.update_agent_run(agent_run.id, {
            "status": AgentRunStatus.ERROR,
            "error_message": str(e)
        })
        
        raise


def judge_results(
    task_id: str,
    successful_agents: List[str],
    db: DatabaseManager,
    judge_service
) -> None:
    """Judge the results from successful agent runs."""
    
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
            agent_run = next((run for run in agent_runs if run.agent.value == agent_name), None)
            
            if not agent_run:
                logger.warning(f"Agent run not found for {agent_name}")
                continue
            
            # Extract answers from artifacts (this would need to be implemented based on
            # how we store the evaluation Q&A in the artifacts)
            questions, pre_answers, post_answers = extract_evaluation_data(agent_run)
            
            if not questions or not post_answers:
                logger.warning(f"No evaluation data found for {agent_name}")
                continue
            
            # Run judge evaluation
            scores, rationale, judge_type_used = judge_service.evaluate_agent_performance(
                questions=questions,
                pre_compression_answers=pre_answers,
                post_compression_answers=post_answers,
                rubric=rubric,
                judge_type=settings.default_judge
            )
            
            # Convert scores dict to serializable format
            scores_dict = {dim.value: score for dim, score in scores.items()}
            
            # Calculate overall score
            overall_score = sum(scores.values()) / len(scores) if scores else 0.0
            passing_scores = sum(1 for score in scores.values() if score >= 0.5)
            passed = passing_scores >= max(3, len(rubric) * 0.75)
            
            # Store score in database
            score_data = {
                "agent_run_id": agent_run.id,
                "task_id": UUID(task_id),
                "agent": AgentName(agent_name),
                "scores": scores_dict,
                "overall_score": overall_score,
                "passed": passed,
                "judge_type": judge_type_used,
                "judge_model": settings.judge_model if judge_type_used == "llm" else None,
                "rationale": rationale
            }
            
            db.create_score(score_data)
            
            logger.info(
                f"Judging complete for {agent_name}: "
                f"Overall: {overall_score:.2f}, Passed: {passed}"
            )
            
        except Exception as e:
            logger.error(f"Failed to judge {agent_name}: {e}")


def extract_evaluation_data(agent_run) -> tuple:
    """
    Extract evaluation questions and answers from agent run artifacts.
    
    This is a placeholder implementation. In a real system, you would need to
    parse the agent transcripts or export files to extract the actual Q&A pairs.
    """
    
    # For now, return dummy data
    # In reality, you would parse the transcript or export file to extract:
    # 1. The evaluation questions that were asked
    # 2. The answers given before memory-only mode
    # 3. The answers given after entering memory-only mode
    
    dummy_questions = [
        "What is the main purpose of this PR?",
        "List the key files that were changed and their roles.",
        "How would you implement a similar feature?",
        "What are the long-term implications of this approach?"
    ]
    
    dummy_pre_answers = [
        "The PR implements feature X with changes to files A, B, C...",
        "File A handles data processing, File B manages API calls...",
        "I would use a similar pattern with proper error handling...",
        "This approach provides good scalability and maintainability..."
    ]
    
    dummy_post_answers = [
        "The PR adds functionality for handling user requests...",
        "Several files were modified including the main handler...",
        "A similar implementation would focus on modularity...",
        "The long-term benefits include easier maintenance and testing..."
    ]
    
    return dummy_questions, dummy_pre_answers, dummy_post_answers


def cleanup_failed_task(task_id: str) -> None:
    """Clean up resources for a failed task."""
    
    logger.info(f"Cleaning up failed task: {task_id}")
    
    try:
        # Cleanup file system
        pr_service = PRService()
        pr_service.cleanup_task_workspace(task_id)
        
        # Update database status
        with Session(engine) as session:
            db = DatabaseManager(session)
            db.update_task(UUID(task_id), {
                "status": TaskStatus.ERROR,
                "error_message": "Task cleanup performed"
            })
        
        logger.info(f"Cleanup complete for task: {task_id}")
        
    except Exception as e:
        logger.error(f"Cleanup failed for task {task_id}: {e}")


# Export worker functions for RQ
__all__ = [
    "process_task",
    "run_agent_session", 
    "judge_results",
    "cleanup_failed_task"
]
