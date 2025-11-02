#!/usr/bin/env python3
"""
Cloud worker for processing tasks from Pub/Sub.

This worker:
1. Subscribes to Pub/Sub topic using pull subscription
2. Receives task messages
3. Processes tasks using existing simple_worker logic
4. Acknowledges messages on success
5. Auto-scales based on queue depth

Uses Application Default Credentials (ADC) - no explicit credential management.
"""

import logging
import sys
import json
import signal
from pathlib import Path
from typing import Dict, Any
from concurrent.futures import TimeoutError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.infrastructure.cloud_queue import get_pubsub_manager
from app.infrastructure.database import create_tables, engine, DatabaseManager
from workers.simple_worker import process_task_simple
from sqlmodel import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cloud_worker.log") if not settings.debug else logging.StreamHandler()
    ],
)

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True


def process_message(message):
    """
    Process a single Pub/Sub message.
    
    Args:
        message: Pub/Sub message object
    """
    try:
        # Parse message data
        data = json.loads(message.data.decode("utf-8"))
        task_id = data.get("task_id")
        metadata = data.get("metadata", {})
        
        logger.info(f"Processing task {task_id} from Pub/Sub")
        logger.info(f"Message ID: {message.message_id}, Publish time: {message.publish_time}")
        
        if not task_id:
            logger.error("Message missing task_id, skipping")
            message.ack()
            return
        
        # Verify task exists and is in correct state
        with Session(engine) as session:
            db = DatabaseManager(session)
            task_db = db.get_task(task_id)
            
            if not task_db:
                logger.error(f"Task {task_id} not found in database")
                message.ack()  # Ack to prevent redelivery
                return
            
            if task_db.status not in ["queued", "running"]:
                logger.warning(
                    f"Task {task_id} already processed (status: {task_db.status}), skipping"
                )
                message.ack()
                return
        
        # Process the task using existing worker logic
        try:
            result = process_task_simple(task_id)
            logger.info(f"Task {task_id} processed successfully: {result}")
            
            # Acknowledge message on success
            message.ack()
            logger.info(f"Message {message.message_id} acknowledged")
            
        except Exception as e:
            logger.error(f"Failed to process task {task_id}: {e}")
            # Nack the message to retry (Pub/Sub will redeliver)
            message.nack()
            logger.warning(f"Message {message.message_id} nacked for retry")
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse message data: {e}")
        message.ack()  # Ack malformed messages to prevent infinite retries
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        message.nack()


def main():
    """Start the cloud worker."""
    
    logger.info("=" * 80)
    logger.info("Starting Cloud Worker for Memory-Break Orchestrator")
    logger.info("=" * 80)
    logger.info(f"Google Cloud Project: {settings.google_cloud_project}")
    logger.info(f"Pub/Sub Topic: {settings.pubsub_topic}")
    logger.info(f"Pub/Sub Subscription: {settings.pubsub_subscription}")
    logger.info(f"Using Application Default Credentials (ADC)")
    logger.info("=" * 80)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        create_tables()
        logger.info("Database initialized")
        
        # Get Pub/Sub manager (uses ADC automatically)
        pubsub_manager = get_pubsub_manager()
        
        if not pubsub_manager.subscriber:
            logger.error("Pub/Sub subscriber not initialized. Check configuration and ADC setup.")
            logger.error("Make sure GOOGLE_CLOUD_PROJECT is set and you're authenticated:")
            logger.error("  gcloud auth application-default login")
            sys.exit(1)
        
        logger.info("Subscribing to Pub/Sub messages...")
        logger.info("Worker is ready and listening for tasks...")
        logger.info("Press Ctrl+C to stop")
        
        # Subscribe to messages with callback
        streaming_pull_future = pubsub_manager.subscribe_to_tasks(
            callback=process_message
        )
        
        # Keep the worker running
        try:
            # Wait for shutdown signal
            while not shutdown_flag:
                streaming_pull_future.result(timeout=5.0)
        except TimeoutError:
            # Timeout is expected, just check shutdown flag and continue
            pass
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        
        # Graceful shutdown
        logger.info("Shutting down worker...")
        streaming_pull_future.cancel()
        streaming_pull_future.result()  # Wait for cancellation to complete
        logger.info("Worker stopped gracefully")
        
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        logger.error("=" * 80)
        logger.error("Troubleshooting:")
        logger.error("1. Ensure Google Cloud credentials are set up:")
        logger.error("   gcloud auth application-default login")
        logger.error("2. Verify environment variables:")
        logger.error(f"   GOOGLE_CLOUD_PROJECT={settings.google_cloud_project}")
        logger.error(f"   PUBSUB_TOPIC={settings.pubsub_topic}")
        logger.error(f"   PUBSUB_SUBSCRIPTION={settings.pubsub_subscription}")
        logger.error("3. Ensure Pub/Sub subscription exists:")
        logger.error(f"   gcloud pubsub subscriptions describe {settings.pubsub_subscription}")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

