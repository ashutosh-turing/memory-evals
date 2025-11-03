"""Artifact download endpoints."""

import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.config import settings
from app.infrastructure.database import DatabaseManager, get_session

router = APIRouter()
logger = logging.getLogger(__name__)


def get_db_manager(session: Session = Depends(get_session)) -> DatabaseManager:
    """Get database manager dependency."""
    return DatabaseManager(session)


@router.get("/{task_id}/{agent}/{artifact_name}")
async def download_artifact(
    task_id: UUID,
    agent: str,
    artifact_name: str,
    db: DatabaseManager = Depends(get_db_manager),
) -> FileResponse:
    """Download an artifact file for a specific task and agent."""

    logger.info(f"Downloading artifact: {task_id}/{agent}/{artifact_name}")

    # Verify task exists
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get agent runs for this task
    agent_runs = db.get_agent_runs_for_task(task_id)
    agent_run = next(
        (
            run
            for run in agent_runs
            if (run.agent.value if hasattr(run.agent, "value") else run.agent) == agent
        ),
        None,
    )

    if not agent_run:
        raise HTTPException(status_code=404, detail=f"Agent run for {agent} not found")

    # Check if artifact exists in agent run
    if artifact_name not in agent_run.artifacts:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact {artifact_name} not found for agent {agent}",
        )

    # Get file path
    file_path = Path(agent_run.artifacts[artifact_name])

    # Security check - ensure file is within expected directory
    # Note: Artifacts are stored in storage/{task_id}/agents/{agent}/
    expected_base = (
        Path(settings.run_root).expanduser() / str(task_id) / "agents" / agent
    )
    try:
        file_path = file_path.resolve()
        expected_base = expected_base.resolve()

        # Check if file is within the expected directory
        if not str(file_path).startswith(str(expected_base)):
            logger.warning(
                f"Security violation: attempted access to {file_path}, expected under {expected_base}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

    except (OSError, ValueError) as e:
        logger.error(f"Path resolution error: {e}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Artifact file not found: {artifact_name}"
        )

    # Check if file is readable
    if not os.access(file_path, os.R_OK):
        logger.error(f"File not readable: {file_path}")
        raise HTTPException(status_code=403, detail="File not accessible")

    # Determine media type based on file extension
    media_type = _get_media_type(file_path)

    # Create appropriate filename for download
    filename = f"{task_id}_{agent}_{artifact_name}{file_path.suffix}"

    logger.info(f"Serving file: {file_path} as {filename}")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={"Cache-Control": "public, max-age=3600"},  # Cache for 1 hour
    )


@router.get("/{task_id}/bundle")
async def download_task_bundle(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> FileResponse:
    """Download a zip bundle of all artifacts for a task."""

    logger.info(f"Creating bundle for task: {task_id}")

    # Verify task exists
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get all agent runs
    agent_runs = db.get_agent_runs_for_task(task_id)
    if not agent_runs:
        raise HTTPException(status_code=404, detail="No agent runs found for task")

    # Create bundle
    import tempfile
    import zipfile

    try:
        # Create temporary zip file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip:
            temp_zip_path = temp_zip.name

        with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add task metadata
            task_info = {
                "task_id": str(task_id),
                "repo": task_db.repo,
                "pr_number": task_db.pr_number,
                "status": task_db.status.value,
                "agents": task_db.agents,
                "created_at": task_db.created_at.isoformat(),
            }

            import json

            zipf.writestr("task_info.json", json.dumps(task_info, indent=2))

            # Add artifacts from each agent
            for agent_run in agent_runs:
                agent_name = (
                    agent_run.agent.value
                    if hasattr(agent_run.agent, "value")
                    else agent_run.agent
                )

                # Add agent run metadata
                agent_info = {
                    "agent": agent_name,
                    "status": agent_run.status.value,
                    "milestones": agent_run.milestones,
                    "stats": agent_run.stats,
                    "created_at": agent_run.created_at.isoformat(),
                }

                zipf.writestr(
                    f"{agent_name}/agent_info.json", json.dumps(agent_info, indent=2)
                )

                # Add artifact files
                for artifact_name, artifact_path in agent_run.artifacts.items():
                    file_path = Path(artifact_path)
                    if file_path.exists() and file_path.is_file():
                        try:
                            # Add file to zip with agent-specific path
                            zip_path = f"{agent_name}/{artifact_name}{file_path.suffix}"
                            zipf.write(str(file_path), zip_path)
                            logger.debug(f"Added {file_path} as {zip_path}")
                        except Exception as e:
                            logger.warning(f"Failed to add {file_path} to bundle: {e}")
                    else:
                        logger.warning(f"Artifact file not found: {artifact_path}")

        # Return the zip file
        bundle_filename = f"task_{task_id}_bundle.zip"

        return FileResponse(
            path=temp_zip_path,
            media_type="application/zip",
            filename=bundle_filename,
            headers={"Cache-Control": "no-cache"},
            background=_cleanup_temp_file(temp_zip_path),  # Cleanup after sending
        )

    except Exception as e:
        logger.error(f"Failed to create bundle for task {task_id}: {e}")
        # Cleanup temp file on error
        if "temp_zip_path" in locals() and os.path.exists(temp_zip_path):
            try:
                os.unlink(temp_zip_path)
            except:
                pass
        raise HTTPException(status_code=500, detail="Failed to create bundle")


@router.get("/{task_id}/list")
async def list_artifacts(
    task_id: UUID,
    db: DatabaseManager = Depends(get_db_manager),
) -> dict[str, Any]:
    """List all available artifacts for a task."""

    # Verify task exists
    task_db = db.get_task(task_id)
    if not task_db:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get agent runs
    agent_runs = db.get_agent_runs_for_task(task_id)

    artifacts = {}
    total_size = 0

    for agent_run in agent_runs:
        # Handle both string and enum types
        agent_name = (
            agent_run.agent.value
            if hasattr(agent_run.agent, "value")
            else agent_run.agent
        )
        agent_artifacts = {}

        for artifact_name, artifact_path in agent_run.artifacts.items():
            file_path = Path(artifact_path)

            artifact_info = {
                "name": artifact_name,
                "path": str(file_path),
                "exists": file_path.exists(),
                "download_url": f"/api/v1/artifacts/{task_id}/{agent_name}/{artifact_name}",
            }

            if file_path.exists():
                try:
                    stat = file_path.stat()
                    artifact_info.update(
                        {
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "readable": os.access(file_path, os.R_OK),
                        }
                    )
                    total_size += stat.st_size
                except Exception as e:
                    logger.warning(f"Failed to get stats for {file_path}: {e}")
                    artifact_info["error"] = str(e)

            agent_artifacts[artifact_name] = artifact_info

        artifacts[agent_name] = agent_artifacts

    return {
        "task_id": str(task_id),
        "artifacts": artifacts,
        "total_size": total_size,
        "bundle_url": f"/api/v1/artifacts/{task_id}/bundle",
    }


def _get_media_type(file_path: Path) -> str:
    """Get media type based on file extension."""
    suffix = file_path.suffix.lower()

    media_types = {
        ".txt": "text/plain",
        ".log": "text/plain",
        ".json": "application/json",
        ".zip": "application/zip",
        ".csv": "text/csv",
        ".html": "text/html",
        ".xml": "application/xml",
        ".pdf": "application/pdf",
    }

    return media_types.get(suffix, "application/octet-stream")


def _cleanup_temp_file(file_path: str):
    """Background task to cleanup temporary files."""

    def cleanup():
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

    return cleanup
