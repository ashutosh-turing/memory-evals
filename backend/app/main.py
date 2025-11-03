"""FastAPI application factory and main entry point."""

import logging
import os
import asyncio
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from concurrent.futures import TimeoutError as FuturesTimeoutError

from app.config import settings
from app.infrastructure.database import create_tables, engine
from app.infrastructure.cloud_queue import get_pubsub_manager
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
    logger.info(f"Database URL: {settings.database_url}")
    
    # Initialize database
    logger.info("Creating database tables...")
    create_tables()
    
    # Initialize agent registry
    logger.info("Initializing agent registry...")
    initialize_agent_registry()
    
    # Health checks (lightweight)
    logger.info("Performing startup health checks...")

    # Start Pub/Sub worker if queue is enabled
    worker_future = None
    worker_thread = None
    if settings.queue_enabled and settings.google_cloud_project:
        logger.info("Starting Pub/Sub worker...")
        
        # Configure worker-specific logging BEFORE starting thread
        worker_logger = logging.getLogger('workers')
        worker_logger.setLevel(logging.INFO)
        worker_logger.propagate = False  # Do not duplicate logs into api.log
        
        # Add file handler for worker logs
        worker_log_path = Path('logs/worker.log')
        worker_log_path.parent.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(worker_log_path)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        worker_logger.addHandler(file_handler)
        
        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        worker_logger.addHandler(console_handler)
        
        try:
            from workers.cloud_worker import process_message
            
            pubsub_manager = get_pubsub_manager()
            if pubsub_manager.subscriber:
                # Start worker in background thread
                def run_worker():
                    nonlocal worker_future
                    worker_logger.info("Pub/Sub worker thread starting...")
                    try:
                        worker_future = pubsub_manager.subscribe_to_tasks(
                            callback=process_message
                        )
                        worker_logger.info("Pub/Sub worker subscribed successfully")
                        # Keep worker running; timeouts are expected as heartbeats
                        while True:
                            try:
                                worker_future.result(timeout=5.0)
                            except FuturesTimeoutError:
                                continue
                    except Exception:
                        worker_logger.error("Worker fatal error", exc_info=True)
                
                worker_thread = threading.Thread(target=run_worker, daemon=True)
                worker_thread.start()
                logger.info("Pub/Sub worker thread started")
            else:
                logger.warning("Pub/Sub subscriber not initialized - tasks will not be processed")
        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub worker: {e}")
    else:
        logger.info("Queue disabled or Google Cloud project not configured - Pub/Sub worker not started")
    
    logger.info("Application startup complete!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Memory-Break Orchestrator...")
    
    # Stop Pub/Sub worker
    if 'worker_future' in locals() and worker_future:
        logger.info("Stopping Pub/Sub worker...")
        try:
            worker_future.cancel()
            await asyncio.sleep(1)
            logger.info("Pub/Sub worker stopped")
        except Exception as e:
            logger.warning(f"Error stopping worker: {e}")
    
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
            allowed_hosts=["*"],
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
