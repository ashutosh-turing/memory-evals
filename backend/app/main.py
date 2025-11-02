"""FastAPI application factory and main entry point."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.config import settings
from app.infrastructure.database import create_tables, engine
from app.infrastructure.queue import check_queue_health
from app.agents.registry import initialize_agent_registry
from app.presentation.routers import tasks, artifacts, health, logs, internal
from app.presentation.middleware import LoggingMiddleware, SecurityMiddleware, SSOAuthMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Memory-Break Orchestrator...")
    logger.info(f"Redis URL: {settings.redis_url}")
    logger.info(f"Database URL: {settings.database_url}")
    
    # Initialize database
    logger.info("Creating database tables...")
    create_tables()
    
    # Initialize agent registry
    logger.info("Initializing agent registry...")
    initialize_agent_registry()
    
    # Health checks
    logger.info("Performing startup health checks...")
    queue_health = check_queue_health()
    if not queue_health.get("redis_connected", False):
        logger.error("Redis connection failed - worker operations will not work!")
        logger.error(f"Check Redis server at: {settings.redis_url}")
    else:
        logger.info("Redis connection successful")
    
    # Note: Container management is now handled by workers
    logger.info("Using worker-managed container architecture for agent isolation")
    
    logger.info("Application startup complete!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Memory-Break Orchestrator...")
    
    # Container management is handled by workers - no cleanup needed at API level
    
    # Close database connections
    logger.info("Closing database connections...")
    engine.dispose()
    
    logger.info("Application shutdown complete!")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.app_name,
        description="Memory-Break Orchestrator for AI agent evaluation following VIBE architecture",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Add middleware
    configure_middleware(app)
    
    # Add routers
    configure_routes(app)
    
    # Add exception handlers
    configure_exception_handlers(app)
    
    return app


def configure_middleware(app: FastAPI) -> None:
    """Configure application middleware."""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Trusted hosts (in production)
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", settings.host],
        )
    
    # Custom middleware (order matters - SSO auth should be early in the chain)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(SSOAuthMiddleware)  # SSO authentication
    app.add_middleware(SecurityMiddleware)


def configure_routes(app: FastAPI) -> None:
    """Configure application routes."""
    
    # Health endpoint (no /api/v1 prefix)
    app.include_router(
        health.router,
        prefix="/health",
        tags=["health"],
    )
    
    # Internal endpoints (not behind SSO, for Cloud Tasks/Pub/Sub)
    # These are called by Google Cloud services, not end users
    app.include_router(
        internal.router,
        prefix="/internal",
        tags=["internal"],
    )
    
    # API routes (all under /api/v1)
    app.include_router(
        tasks.router,
        prefix="/api/v1/tasks",
        tags=["tasks"],
    )
    
    app.include_router(
        artifacts.router,
        prefix="/api/v1/artifacts",
        tags=["artifacts"],
    )
    
    app.include_router(
        logs.router,
        prefix="/api/v1/logs",
        tags=["logs"],
    )
    
    # Static files (for web dashboard)
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        app.mount("/", StaticFiles(directory="static", html=True), name="dashboard")
    except RuntimeError:
        logger.warning("Static files directory not found, skipping web dashboard")


def configure_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers."""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions."""
        logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.url}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path),
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error" if not settings.debug else str(exc),
                "status_code": 500,
                "path": str(request.url.path),
            },
        )


# Create app instance
app = create_app()


# API info endpoint
@app.get("/api/v1/info")
async def api_info() -> Dict[str, Any]:
    """API information endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
        "endpoints": {
            "health": "/health",
            "tasks": "/api/v1/tasks",
            "artifacts": "/api/v1/artifacts",
            "logs": "/api/v1/logs",
        },
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
