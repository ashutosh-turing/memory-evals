"""Live logging and streaming endpoints."""

import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.infrastructure.database import get_session, DatabaseManager
from app.infrastructure.queue import get_queue_manager, QueueManager
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{task_id}/stream")
async def stream_task_logs(
    task_id: UUID,
    db: DatabaseManager = Depends(lambda session=Depends(get_session): DatabaseManager(session)),
) -> StreamingResponse:
    """Stream live logs for a task using Server-Sent Events."""
    
    # Verify task exists
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def log_generator() -> AsyncGenerator[str, None]:
        """Generate Server-Sent Events for live logs."""
        import time
        import asyncio
        
        try:
            # Send initial connection event  
            yield f"data: {json.dumps({'type': 'connected', 'level': 'INFO', 'task_id': str(task_id), 'message': 'Connected to live log stream', 'timestamp': task.created_at.isoformat()})}\n\n"
            
            # Get log file path
            log_file_path = Path(settings.run_root).expanduser() / str(task_id) / "task.log"
            
            # Debug info
            yield f"data: {json.dumps({'type': 'info', 'level': 'INFO', 'message': f'Monitoring log file: {log_file_path}', 'timestamp': task.created_at.isoformat()})}\n\n"
            
            # Check if log file exists, if not wait and check periodically
            max_wait_for_file = 60  # Wait up to 1 minute for log file to appear
            file_wait_start = time.time()
            
            while not log_file_path.exists() and (time.time() - file_wait_start) < max_wait_for_file:
                yield f"data: {json.dumps({'type': 'info', 'level': 'INFO', 'message': 'Waiting for task to start...', 'timestamp': task.created_at.isoformat()})}\n\n"
                await asyncio.sleep(2)
                
                # Check if task status changed
                updated_task = db.get_task(task_id)
                if updated_task and updated_task.status in ['done', 'error']:
                    yield f"data: {json.dumps({'type': 'info', 'level': 'INFO', 'message': f'Task completed with status: {updated_task.status}', 'timestamp': updated_task.updated_at.isoformat()})}\n\n"
                    return
            
            if not log_file_path.exists():
                yield f"data: {json.dumps({'type': 'error', 'level': 'ERROR', 'message': f'Log file not found after waiting. Task may have failed to start.', 'timestamp': task.created_at.isoformat()})}\n\n"
                return
            
            # Stream log file content
            last_position = 0
            max_stream_time = 600  # 10 minutes max streaming
            stream_start = time.time()
            
            with open(log_file_path, 'r', encoding='utf-8') as f:
                # Send any existing content first
                existing_content = f.read()
                if existing_content.strip():
                    for line in existing_content.split('\n'):
                        if line.strip():
                            try:
                                log_data = json.loads(line)
                                # Ensure required fields
                                if 'timestamp' not in log_data:
                                    log_data['timestamp'] = task.created_at.isoformat()
                                if 'level' not in log_data:
                                    log_data['level'] = 'INFO'
                                yield f"data: {json.dumps(log_data)}\n\n"
                            except json.JSONDecodeError:
                                # Handle plain text logs
                                yield f"data: {json.dumps({'type': 'log', 'level': 'INFO', 'message': line, 'timestamp': task.created_at.isoformat()})}\n\n"
                
                last_position = f.tell()
                
                # Follow file for new content
                while (time.time() - stream_start) < max_stream_time:
                    # Check if task completed
                    updated_task = db.get_task(task_id)
                    if updated_task and updated_task.status in ['done', 'error']:
                        yield f"data: {json.dumps({'type': 'completed', 'level': 'INFO', 'status': updated_task.status, 'message': f'Task completed: {updated_task.status}', 'timestamp': updated_task.updated_at.isoformat()})}\n\n"
                        break
                    
                    f.seek(last_position)
                    new_content = f.read()
                    if new_content:
                        for line in new_content.split('\n'):
                            if line.strip():
                                try:
                                    log_data = json.loads(line)
                                    # Ensure required fields
                                    if 'timestamp' not in log_data:
                                        log_data['timestamp'] = task.created_at.isoformat()
                                    if 'level' not in log_data:
                                        log_data['level'] = 'INFO'
                                    yield f"data: {json.dumps(log_data)}\n\n"
                                except json.JSONDecodeError:
                                    yield f"data: {json.dumps({'type': 'log', 'level': 'INFO', 'message': line, 'timestamp': task.created_at.isoformat()})}\n\n"
                        last_position = f.tell()
                    
                    # Send heartbeat to keep connection alive
                    if int(time.time()) % 30 == 0:  # Every 30 seconds
                        yield f"data: {json.dumps({'type': 'heartbeat', 'level': 'INFO', 'message': 'Connection alive', 'timestamp': task.created_at.isoformat()})}\n\n"
                    
                    await asyncio.sleep(1)  # Non-blocking sleep
                        
        except Exception as e:
            logger.error(f"Error streaming logs for task {task_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'level': 'ERROR', 'message': f'Stream error: {str(e)}', 'timestamp': task.created_at.isoformat()})}\n\n"
    
    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",  # Proper SSE content type
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",  # Fix CORS issues
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )


@router.get("/{task_id}/agent/{agent_name}/stream")
async def stream_agent_logs(
    task_id: UUID,
    agent_name: str,
    db: DatabaseManager = Depends(lambda session=Depends(get_session): DatabaseManager(session)),
) -> StreamingResponse:
    """Stream live logs for a specific agent."""
    
    # Verify task exists
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Verify agent exists in task
    if agent_name not in task.agents:
        raise HTTPException(status_code=404, detail="Agent not found in task")
    
    async def agent_log_generator() -> AsyncGenerator[str, None]:
        """Generate Server-Sent Events for agent-specific logs."""
        
        yield f"data: {json.dumps({'type': 'connected', 'agent': agent_name, 'task_id': str(task_id)})}\n\n"
        
        # Get agent log file path
        agent_log_path = Path(settings.run_root).expanduser() / str(task_id) / "agents" / agent_name / "session.log"
        
        if not agent_log_path.exists():
            yield f"data: {json.dumps({'type': 'info', 'message': f'Agent {agent_name} log not found. Agent may not have started yet.'})}\n\n"
            return
        
        try:
            with open(agent_log_path, 'r', encoding='utf-8') as f:
                import time
                last_position = 0
                max_wait_time = 300
                start_time = time.time()
                
                while time.time() - start_time < max_wait_time:
                    f.seek(last_position)
                    new_content = f.read()
                    if new_content:
                        for line in new_content.split('\n'):
                            if line.strip():
                                try:
                                    log_data = json.loads(line)
                                    yield f"data: {json.dumps(log_data)}\n\n"
                                except json.JSONDecodeError:
                                    yield f"data: {json.dumps({'type': 'agent_log', 'agent': agent_name, 'message': line})}\n\n"
                        last_position = f.tell()
                    
                    # Check agent status
                    agent_runs = db.get_agent_runs_for_task(task_id)
                    agent_run = next((run for run in agent_runs if run.agent == agent_name), None)
                    if agent_run and agent_run.status in ['done', 'error']:
                        yield f"data: {json.dumps({'type': 'agent_completed', 'agent': agent_name, 'status': agent_run.status})}\n\n"
                        break
                    
                    time.sleep(1)
                        
        except Exception as e:
            logger.error(f"Error streaming agent logs for {agent_name}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error reading agent logs: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        agent_log_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/{task_id}/artifacts/logs")
async def get_task_log_files(
    task_id: UUID,
    db: DatabaseManager = Depends(lambda session=Depends(get_session): DatabaseManager(session)),
):
    """Get available log files for a task."""
    
    # Verify task exists
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_dir = Path(settings.run_root).expanduser() / str(task_id)
    log_files = []
    
    if task_dir.exists():
        # Main task log
        task_log = task_dir / "task.log"
        if task_log.exists():
            log_files.append({
                "name": "task.log",
                "path": "task.log",
                "size": task_log.stat().st_size,
                "modified": task_log.stat().st_mtime
            })
        
        # Agent logs
        agents_dir = task_dir / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    session_log = agent_dir / "session.log"
                    if session_log.exists():
                        log_files.append({
                            "name": f"{agent_dir.name}_session.log",
                            "path": f"agents/{agent_dir.name}/session.log",
                            "size": session_log.stat().st_size,
                            "modified": session_log.stat().st_mtime
                        })
                    
                    transcript = agent_dir / "transcript.txt"
                    if transcript.exists():
                        log_files.append({
                            "name": f"{agent_dir.name}_transcript.txt",
                            "path": f"agents/{agent_dir.name}/transcript.txt", 
                            "size": transcript.stat().st_size,
                            "modified": transcript.stat().st_mtime
                        })
    
    return {"task_id": str(task_id), "log_files": log_files}
