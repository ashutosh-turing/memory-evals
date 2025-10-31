"""Task management endpoints."""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session
from pydantic import BaseModel, HttpUrl, Field

from app.domain.entities import (
    Task, AgentRun, TaskStatus, AgentRunStatus, AgentName, RubricDimension
)
from app.infrastructure.database import get_session, DatabaseManager
from workers.simple_worker import process_task_simple
from app.agents.registry import get_agent_registry, validate_agent_list
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response Models
class CreateTaskRequest(BaseModel):
    """Request model for creating a new task."""
    pr_url: HttpUrl
    agents: List[AgentName] = Field(default=[AgentName.IFLOW, AgentName.CLAUDE, AgentName.GEMINI])
    rubric: List[RubricDimension] = Field(default_factory=lambda: list(RubricDimension))
    max_files: int = Field(default=50, ge=1, le=1000)


class TaskResponse(BaseModel):
    """Response model for task information."""
    id: str
    pr_url: str
    repo: str
    pr_number: int
    agents: List[str]
    rubric: List[str]
    status: str
    max_files: int
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    changed_files: List[str] = []
    error_message: Optional[str] = None


class AgentRunResponse(BaseModel):
    """Response model for agent run information."""
    id: str
    task_id: str
    agent: str
    status: str
    milestones: Dict[str, Any]
    artifacts: Dict[str, Any]
    stats: Dict[str, Any]
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class StatusUpdateRequest(BaseModel):
    """Request model for status updates from agent containers."""
    task_id: str
    agent_type: str
    status: str
    message: Optional[str] = None
    progress: Optional[float] = None
    timestamp: Optional[str] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None


class TaskListResponse(BaseModel):
    """Response model for task listing."""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


# Dependencies
def get_db_manager(session: Session = Depends(get_session)) -> DatabaseManager:
    """Get database manager dependency."""
    return DatabaseManager(session)


# Endpoints
@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    request: CreateTaskRequest,
    db: DatabaseManager = Depends(get_db_manager),
) -> TaskResponse:
    """Create a new memory-break evaluation task."""
    
    logger.info(f"Creating task for PR: {request.pr_url}")
    
    # Validate agents are available
    if not validate_agent_list(request.agents):
        raise HTTPException(
            status_code=400,
            detail="One or more requested agents are not available"
        )
    
    # Parse GitHub PR URL
    pr_info = _parse_github_pr_url(str(request.pr_url))
    if not pr_info:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub PR URL format. Expected: https://github.com/owner/repo/pull/number"
        )
    
    try:
        # Create task in database
        task_data = {
            "pr_url": str(request.pr_url),
            "repo": f"{pr_info['owner']}/{pr_info['repo']}",
            "pr_number": pr_info["pr_number"],
            "agents": [agent.value for agent in request.agents],
            "rubric": [dim.value for dim in request.rubric],
            "status": TaskStatus.QUEUED,
            "max_files": request.max_files,
        }
        
        task_db = db.create_task(task_data)
        
        # Create agent runs
        for agent in request.agents:
            agent_run_data = {
                "task_id": task_db.id,
                "agent": agent.value,  # Convert enum to string for database
                "status": AgentRunStatus.QUEUED.value,  # Convert enum to string for database
            }
            db.create_agent_run(agent_run_data)
        
        # Automatically enqueue task for simple processing
        try:
            # Update task status to running
            db.update_task(task_db.id, {"status": TaskStatus.RUNNING.value})
            
            # Enqueue simple task processing job
            result = process_task_simple(str(task_db.id))
            
            logger.info(f"Created and auto-enqueued task {task_db.id} for simple processing: {result}")
            
            # Get updated task with running status
            updated_task = db.get_task(task_db.id)
            return _task_db_to_response(updated_task)
            
        except Exception as e:
            logger.error(f"Failed to enqueue task {task_db.id}: {e}")
            # Reset task status on failure
            db.update_task(task_db.id, {
                "status": TaskStatus.ERROR.value,
                "error_message": f"Failed to enqueue: {str(e)}"
            })
            # Return the task even if enqueueing failed
            updated_task = db.get_task(task_db.id)
            return _task_db_to_response(updated_task)
        
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[TaskStatus] = None,
    db: DatabaseManager = Depends(get_db_manager),
) -> TaskListResponse:
    """List tasks with pagination and optional filtering."""
    
    try:
        # Convert enum to string for database query
        status_str = status.value if status else None
        
        # Get tasks from database
        tasks_db, total = db.list_tasks(page=page, page_size=page_size, status=status_str)
        
        # Convert to response models
        tasks = [_task_db_to_response(task) for task in tasks_db]
        
        return TaskListResponse(
            tasks=tasks,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tasks")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> TaskResponse:
    """Get task by ID."""
    
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return _task_db_to_response(task_db)


@router.post("/{task_id}/run", response_model=TaskResponse)
async def run_task(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> TaskResponse:
    """Start execution of a task."""
    
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_db.status != TaskStatus.QUEUED:
        raise HTTPException(
            status_code=400,
            detail=f"Task cannot be run in status: {task_db.status}"
        )
    
    try:
        # Update task status to running
        db.update_task(task_id, {"status": TaskStatus.RUNNING})
        
        # Enqueue simple task processing job
        result = process_task_simple(str(task_id))
        
        logger.info(f"Enqueued task {task_id} for simple processing: {result}")
        
        # Return updated task
        updated_task = db.get_task(task_id)
        return _task_db_to_response(updated_task)
        
    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {e}")
        # Reset task status on failure
        db.update_task(task_id, {
            "status": TaskStatus.ERROR,
            "error_message": f"Failed to start: {str(e)}"
        })
        raise HTTPException(status_code=500, detail="Failed to start task")


@router.get("/{task_id}/agents", response_model=List[AgentRunResponse])
async def get_task_agents(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> List[AgentRunResponse]:
    """Get all agent runs for a task."""
    
    # Verify task exists
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get agent runs
    agent_runs = db.get_agent_runs_for_task(task_id)
    
    return [_agent_run_db_to_response(run) for run in agent_runs]


@router.get("/{task_id}/agents/{agent}", response_model=AgentRunResponse)
async def get_task_agent(
    task_id: UUID,
    agent: AgentName,
    db: DatabaseManager = Depends(get_db_manager),
) -> AgentRunResponse:
    """Get specific agent run for a task."""
    
    # Verify task exists
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get agent runs and find the specific one
    agent_runs = db.get_agent_runs_for_task(task_id)
    agent_run = next((run for run in agent_runs if run.agent == agent), None)
    
    if not agent_run:
        raise HTTPException(
            status_code=404,
            detail=f"Agent run for {agent.value} not found"
        )
    
    return _agent_run_db_to_response(agent_run)


@router.post("/{task_id}/status")
async def update_task_status(
    task_id: UUID,
    status_data: StatusUpdateRequest,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, str]:
    """Update task status from agent container."""
    
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        # Log the status update with all details
        logger.info(
            f"Task {task_id} status update from {status_data.agent_type}: "
            f"{status_data.status} - {status_data.message} "
            f"(progress: {status_data.progress}, mem: {status_data.memory_usage}MB, cpu: {status_data.cpu_usage}%)"
        )
        
        # Optionally update task status if provided
        if status_data.status in ['RUNNING', 'DONE', 'ERROR']:
            db.update_task(task_id, {"status": status_data.status})
        
        return {"message": "Status updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to update task status {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update status")


@router.delete("/{task_id}")
async def cancel_task(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, str]:
    """Cancel a running task."""
    
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_db.status in [TaskStatus.DONE, TaskStatus.ERROR]:
        raise HTTPException(
            status_code=400,
            detail="Task is already completed and cannot be cancelled"
        )
    
    try:
        # Update task status (simple worker will check this and stop)
        db.update_task(task_id, {
            "status": TaskStatus.ERROR,
            "error_message": "Task cancelled by user"
        })
        
        # Update agent runs
        agent_runs = db.get_agent_runs_for_task(task_id)
        for run in agent_runs:
            if run.status in [AgentRunStatus.QUEUED, AgentRunStatus.RUNNING]:
                db.update_agent_run(run.id, {
                    "status": AgentRunStatus.ERROR,
                    "error_message": "Task cancelled"
                })
        
        logger.info(f"Cancelled task {task_id} - marked for termination")
        
        return {"message": "Task cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel task")


# Helper functions
def _parse_github_pr_url(url: str) -> Optional[Dict[str, Any]]:
    """Parse GitHub PR URL to extract owner, repo, and PR number."""
    import re
    
    pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, url)
    
    if not match:
        return None
    
    return {
        "owner": match.group(1),
        "repo": match.group(2),
        "pr_number": int(match.group(3)),
    }


def _task_db_to_response(task_db) -> TaskResponse:
    """Convert database task to response model."""
    return TaskResponse(
        id=str(task_db.id),
        pr_url=task_db.pr_url,
        repo=task_db.repo,
        pr_number=task_db.pr_number,
        agents=task_db.agents,
        rubric=task_db.rubric,
        status=task_db.status,  # Already stored as string in DB
        max_files=task_db.max_files,
        created_at=task_db.created_at.isoformat(),
        updated_at=task_db.updated_at.isoformat(),
        started_at=task_db.started_at.isoformat() if task_db.started_at else None,
        completed_at=task_db.completed_at.isoformat() if task_db.completed_at else None,
        changed_files=task_db.changed_files,
        error_message=task_db.error_message,
    )


def _agent_run_db_to_response(agent_run_db) -> AgentRunResponse:
    """Convert database agent run to response model."""
    return AgentRunResponse(
        id=str(agent_run_db.id),
        task_id=str(agent_run_db.task_id),
        agent=agent_run_db.agent,  # Already stored as string in DB
        status=agent_run_db.status,  # Already stored as string in DB
        milestones=agent_run_db.milestones,
        artifacts=agent_run_db.artifacts,
        stats=agent_run_db.stats,
        created_at=agent_run_db.created_at.isoformat(),
        updated_at=agent_run_db.updated_at.isoformat(),
        started_at=agent_run_db.started_at.isoformat() if agent_run_db.started_at else None,
        completed_at=agent_run_db.completed_at.isoformat() if agent_run_db.completed_at else None,
        error_message=agent_run_db.error_message,
        retry_count=agent_run_db.retry_count,
    )


@router.get("/{task_id}/comparison")
async def get_task_comparison(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Get side-by-side comparison of all agents for a task."""
    
    # Verify task exists
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get all agent runs
    agent_runs = db.get_agent_runs_for_task(task_id)
    
    comparison = {
        "task_id": str(task_id),
        "pr_url": task_db.pr_url,
        "repo": task_db.repo,
        "pr_number": task_db.pr_number,
        "status": task_db.status,
        "agents": {},
        "summary": {
            "total_agents": len(agent_runs),
            "completed": 0,
            "failed": 0,
            "running": 0
        }
    }
    
    for run in agent_runs:
        agent_data = {
            "agent": run.agent,
            "status": run.status,
            "stats": run.stats or {},
            "milestones": run.milestones or {},
            "error_message": run.error_message,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        
        # Extract key metrics from stats
        stats = run.stats or {}
        agent_data["metrics"] = {
            "total_tokens": int(stats.get("total_tokens", stats.get("total_tokens_estimate", 0))),
            "hit_limit": stats.get("hit_limit", "false") == "true",
            "compression_detected": stats.get("compression_detected", "false") == "true",
            "deep_dive_iterations": int(stats.get("deep_dive_iterations", 0)),
            "detection_method": stats.get("detection_method", "unknown")
        }
        
        comparison["agents"][run.agent] = agent_data
        
        # Update summary counts
        if run.status == "done":
            comparison["summary"]["completed"] += 1
        elif run.status == "error":
            comparison["summary"]["failed"] += 1
        elif run.status in ["running", "queued"]:
            comparison["summary"]["running"] += 1
    
    # Calculate winner (agent that handled memory best)
    winner = None
    best_score = -1
    
    for agent_name, agent_data in comparison["agents"].items():
        if agent_data["status"] != "done":
            continue
        
        metrics = agent_data["metrics"]
        # Score based on: completed iterations, handled limit gracefully, compression worked
        score = 0
        score += metrics["deep_dive_iterations"] * 10  # More iterations = better
        if metrics["compression_detected"]:
            score += 50  # Bonus for compression
        if not metrics["hit_limit"]:
            score += 20  # Bonus for staying under limit
        
        if score > best_score:
            best_score = score
            winner = agent_name
    
    comparison["winner"] = winner
    comparison["best_score"] = best_score
    
    return comparison


@router.get("/{task_id}/leaderboard")
async def get_task_leaderboard(
    task_id: str,
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Get leaderboard for a specific task showing agent comparison."""
    
    db = DatabaseManager(session)
    
    # Get all agent runs for the task
    agent_runs = db.get_agent_runs_for_task(UUID(task_id))
    
    if not agent_runs:
        raise HTTPException(status_code=404, detail="Task not found or no agent runs available")
    
    leaderboard_data = []
    
    for run in agent_runs:
        # Get scores for this agent run
        scores = db.get_scores_for_agent_run(run.id)
        
        # Calculate execution time
        execution_time = 0.0
        if run.completed_at and run.started_at:
            execution_time = (run.completed_at - run.started_at).total_seconds()
        elif run.updated_at and run.created_at:
            execution_time = (run.updated_at - run.created_at).total_seconds()
        
        leaderboard_entry = {
            "agent": run.agent.value,
            "status": run.status.value,
            "overall_score": scores.overall_score if scores else 0.0,
            "scores": {
                "AR": scores.scores.get("AR", 0.0) if scores else 0.0,
                "TTL": scores.scores.get("TTL", 0.0) if scores else 0.0,
                "LRU": scores.scores.get("LRU", 0.0) if scores else 0.0,
                "SF": scores.scores.get("SF", 0.0) if scores else 0.0,
            },
            "passed": scores.passed if scores else False,
            "execution_time": execution_time,
            "compression_detected": run.stats.get("compression_detected", False) if run.stats else False
        }
        leaderboard_data.append(leaderboard_entry)
    
    # Sort by overall score (descending)
    leaderboard_data.sort(key=lambda x: x["overall_score"], reverse=True)
    
    return {
        "task_id": task_id,
        "leaderboard": leaderboard_data
    }
