#!/usr/bin/env python3
"""Worker process for handling background tasks."""

import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.infrastructure.queue import worker_manager
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("worker.log") if not settings.debug else logging.StreamHandler()
    ],
)

logger = logging.getLogger(__name__)


def main():
    """Start the worker process."""
    
    logger.info("Starting Memory-Break Orchestrator worker...")
    logger.info(f"Redis URL: {settings.redis_url}")
    logger.info(f"Run root: {settings.run_root}")
    
    try:
        # Initialize database for worker
        from app.infrastructure.database import create_tables
        create_tables()
        logger.info("Database tables initialized")
        
        # Start worker (Redis URL is already configured in queue manager)
        worker = worker_manager.start_worker(
            worker_name="memory-break-worker"
        )
        
        logger.info("Worker started, listening for jobs...")
        
        # This will block and process jobs
        worker.work()
        
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        logger.error("Make sure Redis server is running and accessible")
        sys.exit(1)


if __name__ == "__main__":
    main()
