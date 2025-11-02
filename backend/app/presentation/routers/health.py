"""Health check endpoints."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.infrastructure.database import get_session
from app.infrastructure.queue import check_queue_health
from app.agents.registry import get_agent_registry

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "Memory-Break Orchestrator",
        "timestamp": "2025-10-31T12:10:00Z"
    }


@router.get("/detailed")
async def detailed_health_check(
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Detailed health check with all system components."""
    
    health_data = {
        "status": "healthy",
        "service": "Memory-Break Orchestrator",
        "components": {}
    }
    
    # Database health
    try:
        # Simple query to test database connection
        from sqlmodel import text
        session.exec(text("SELECT 1"))
        health_data["components"]["database"] = {
            "status": "healthy",
            "details": "Connection successful"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_data["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "degraded"
    
    # Queue system health
    try:
        queue_health = check_queue_health()
        if queue_health.get("redis_connected", False):
            health_data["components"]["queue"] = {
                "status": "healthy",
                "details": queue_health
            }
        else:
            health_data["components"]["queue"] = {
                "status": "unhealthy",
                "details": queue_health
            }
            health_data["status"] = "degraded"
    except Exception as e:
        logger.error(f"Queue health check failed: {e}")
        health_data["components"]["queue"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "degraded"
    
    # Agent registry health
    try:
        registry = get_agent_registry()
        agent_health = registry.health_check()
        
        healthy_agents = sum(
            1 for agent_data in agent_health.values()
            if agent_data.get("available", False)
        )
        total_agents = len(agent_health)
        
        if healthy_agents > 0:
            health_data["components"]["agents"] = {
                "status": "healthy" if healthy_agents == total_agents else "degraded",
                "healthy_count": healthy_agents,
                "total_count": total_agents,
                "details": agent_health
            }
        else:
            health_data["components"]["agents"] = {
                "status": "unhealthy",
                "healthy_count": 0,
                "total_count": total_agents,
                "details": agent_health
            }
            health_data["status"] = "degraded"
            
    except Exception as e:
        logger.error(f"Agent health check failed: {e}")
        health_data["components"]["agents"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_data["status"] = "degraded"
    
    return health_data


@router.get("/readiness")
async def readiness_check(
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Readiness probe for container orchestration."""
    
    # Check critical components for readiness
    ready = True
    checks = {}
    
    # Database readiness
    try:
        from sqlmodel import text
        session.exec(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
        ready = False
    
    # Queue system readiness
    try:
        queue_health = check_queue_health()
        checks["queue"] = queue_health.get("redis_connected", False)
        if not checks["queue"]:
            ready = False
    except Exception:
        checks["queue"] = False
        ready = False
    
    # At least one agent available
    try:
        registry = get_agent_registry()
        available_agents = registry.get_available_agents()
        checks["agents"] = len(available_agents) > 0
        if not checks["agents"]:
            ready = False
    except Exception:
        checks["agents"] = False
        ready = False
    
    return {
        "ready": ready,
        "checks": checks
    }


@router.get("/liveness")
async def liveness_check() -> Dict[str, Any]:
    """Liveness probe for container orchestration."""
    # Simple liveness check - if we can respond, we're alive
    return {
        "alive": True,
        "timestamp": "2025-10-31T12:10:00Z"
    }


@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """Basic metrics endpoint."""
    try:
        # Queue metrics
        queue_health = check_queue_health()
        
        # Agent metrics
        registry = get_agent_registry()
        agent_health = registry.health_check()
        available_agents = len([
            agent for agent, data in agent_health.items()
            if data.get("available", False)
        ])
        
        return {
            "queue_metrics": queue_health.get("queue_stats", {}),
            "worker_metrics": queue_health.get("worker_stats", {}),
            "agent_metrics": {
                "total_agents": len(agent_health),
                "available_agents": available_agents,
                "agents": agent_health
            }
        }
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {
            "error": "Metrics collection failed",
            "details": str(e)
        }
