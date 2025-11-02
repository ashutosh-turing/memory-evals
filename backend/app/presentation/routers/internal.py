"""Internal endpoints for Cloud Tasks and system operations.

These endpoints are not exposed through the API Gateway and should only
be accessible from internal services (Cloud Tasks, Pub/Sub, etc.).
"""

import logging
from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infrastructure.cloud_queue import get_pubsub_manager
from app.infrastructure.database import get_session, DatabaseManager
from app.domain.entities import TaskStatus

router = APIRouter()
logger = logging.getLogger(__name__)


class TaskProcessRequest(BaseModel):
    """Request model for task processing."""
    task_id: str
    metadata: Dict[str, Any] = {}


@router.post("/tasks/{task_id}/process")
async def process_task_internal(
    task_id: UUID,
    request: Request,
) -> Dict[str, str]:
    """
    Internal endpoint called by Cloud Tasks to process a task.
    
    This endpoint:
    1. Receives the Cloud Task webhook
    2. Publishes the task to Pub/Sub for worker processing
    3. Returns 200 OK immediately (< 1s response time)
    
    The actual task processing happens asynchronously via Pub/Sub workers.
    """
    
    logger.info(f"Received Cloud Task for task {task_id}")
    
    try:
        # Parse request body
        body = await request.json()
        task_id_str = body.get("task_id", str(task_id))
        metadata = body.get("metadata", {})
        
        # Verify task exists in database
        with next(get_session()) as session:
            db = DatabaseManager(session)
            task_db = db.get_task(task_id)
            
            if not task_db:
                logger.error(f"Task {task_id} not found in database")
                raise HTTPException(status_code=404, detail="Task not found")
            
            # Check if task is still in QUEUED status
            if task_db.status != TaskStatus.QUEUED:
                logger.warning(
                    f"Task {task_id} is not in QUEUED status (current: {task_db.status})"
                )
                return {
                    "message": f"Task already processed (status: {task_db.status})",
                    "task_id": str(task_id)
                }
        
        # Publish to Pub/Sub for worker processing
        pubsub_manager = get_pubsub_manager()
        message_id = pubsub_manager.publish_task(
            task_id=task_id_str,
            task_data=metadata
        )
        
        if message_id:
            logger.info(
                f"Task {task_id} published to Pub/Sub: {message_id}"
            )
            return {
                "message": "Task published for processing",
                "task_id": str(task_id),
                "message_id": message_id
            }
        else:
            logger.error(f"Failed to publish task {task_id} to Pub/Sub")
            raise HTTPException(
                status_code=500,
                detail="Failed to publish task to Pub/Sub"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing internal task {task_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/health")
async def internal_health() -> Dict[str, str]:
    """Internal health check endpoint."""
    return {
        "status": "healthy",
        "service": "internal-api"
    }


@router.post("/tasks/{task_id}/retry")
async def retry_task_internal(
    task_id: UUID,
) -> Dict[str, str]:
    """
    Internal endpoint to retry a failed task.
    
    This can be called by monitoring systems or manual intervention.
    """
    
    logger.info(f"Retry requested for task {task_id}")
    
    try:
        # Verify task exists and is in ERROR status
        with next(get_session()) as session:
            db = DatabaseManager(session)
            task_db = db.get_task(task_id)
            
            if not task_db:
                raise HTTPException(status_code=404, detail="Task not found")
            
            if task_db.status not in [TaskStatus.ERROR, TaskStatus.DONE]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Task cannot be retried in status: {task_db.status}"
                )
            
            # Reset task to QUEUED
            db.update_task(task_id, {
                "status": TaskStatus.QUEUED,
                "error_message": None
            })
        
        # Publish to Pub/Sub for reprocessing
        pubsub_manager = get_pubsub_manager()
        message_id = pubsub_manager.publish_task(
            task_id=str(task_id),
            task_data={"retry": True}
        )
        
        if message_id:
            logger.info(f"Task {task_id} requeued for retry: {message_id}")
            return {
                "message": "Task requeued for retry",
                "task_id": str(task_id),
                "message_id": message_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to requeue task"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying task {task_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )

