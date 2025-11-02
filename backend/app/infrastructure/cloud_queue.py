"""Google Cloud Tasks and Pub/Sub integration for async task processing."""

import logging
import json
from typing import Optional, Dict, Any
from uuid import UUID

from google.cloud import tasks_v2
from google.cloud import pubsub_v1
from google.protobuf import timestamp_pb2
import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class CloudTasksManager:
    """Manages Google Cloud Tasks for async task processing."""
    
    def __init__(self):
        self.client = None
        self.parent = None
        
        if settings.google_cloud_project and settings.queue_enabled:
            try:
                self.client = tasks_v2.CloudTasksClient()
                self.parent = self.client.queue_path(
                    settings.google_cloud_project,
                    settings.cloud_tasks_location,
                    settings.cloud_tasks_queue
                )
                logger.info(f"Cloud Tasks initialized: {self.parent}")
            except Exception as e:
                logger.warning(f"Cloud Tasks initialization failed: {e}")
                self.client = None
    
    def enqueue_task(
        self,
        task_id: str,
        delay_seconds: int = 0,
        task_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Enqueue a task to Cloud Tasks.
        
        Args:
            task_id: The task UUID
            delay_seconds: Delay before task execution
            task_data: Additional task metadata
            
        Returns:
            Task name if successful, None otherwise
        """
        if not self.client:
            logger.warning("Cloud Tasks not initialized, skipping enqueue")
            return None
        
        try:
            # Build the task handler URL
            handler_url = self._create_task_handler_url(task_id)
            
            # Prepare task payload
            payload = {
                "task_id": task_id,
                "metadata": task_data or {}
            }
            
            # Create the task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": handler_url,
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": json.dumps(payload).encode(),
                }
            }
            
            # Add delay if specified
            if delay_seconds > 0:
                d = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(d)
                task["schedule_time"] = timestamp
            
            # Enqueue the task
            response = self.client.create_task(
                request={"parent": self.parent, "task": task}
            )
            
            logger.info(f"Cloud Task created for task {task_id}: {response.name}")
            return response.name
            
        except Exception as e:
            logger.error(f"Failed to enqueue Cloud Task for {task_id}: {e}")
            return None
    
    def _create_task_handler_url(self, task_id: str) -> str:
        """Build the internal task handler URL."""
        base_url = settings.cloud_tasks_service_url.rstrip('/')
        return f"{base_url}/internal/tasks/{task_id}/process"
    
    def delete_task(self, task_name: str) -> bool:
        """Delete a Cloud Task by name."""
        if not self.client:
            return False
        
        try:
            self.client.delete_task(name=task_name)
            logger.info(f"Deleted Cloud Task: {task_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Cloud Task {task_name}: {e}")
            return False


class PubSubManager:
    """Manages Google Cloud Pub/Sub for task distribution."""
    
    def __init__(self):
        self.publisher = None
        self.subscriber = None
        self.topic_path = None
        self.subscription_path = None
        
        if settings.google_cloud_project and settings.queue_enabled:
            try:
                # Initialize publisher
                self.publisher = pubsub_v1.PublisherClient()
                self.topic_path = self.publisher.topic_path(
                    settings.google_cloud_project,
                    settings.pubsub_topic
                )
                
                # Initialize subscriber
                self.subscriber = pubsub_v1.SubscriberClient()
                self.subscription_path = self.subscriber.subscription_path(
                    settings.google_cloud_project,
                    settings.pubsub_subscription
                )
                
                logger.info(f"Pub/Sub initialized - Topic: {self.topic_path}")
                logger.info(f"Pub/Sub subscription: {self.subscription_path}")
                
            except Exception as e:
                logger.warning(f"Pub/Sub initialization failed: {e}")
                self.publisher = None
                self.subscriber = None
    
    def publish_task(
        self,
        task_id: str,
        task_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Publish a task to Pub/Sub topic.
        
        Args:
            task_id: The task UUID
            task_data: Task metadata
            
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.publisher:
            logger.warning("Pub/Sub publisher not initialized, skipping publish")
            return None
        
        try:
            # Prepare message
            message_data = {
                "task_id": task_id,
                "metadata": task_data or {},
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            
            # Publish message
            data = json.dumps(message_data).encode("utf-8")
            future = self.publisher.publish(
                self.topic_path,
                data,
                task_id=task_id  # Add as attribute for filtering
            )
            
            message_id = future.result()
            logger.info(f"Published task {task_id} to Pub/Sub: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to publish task {task_id} to Pub/Sub: {e}")
            return None
    
    def subscribe_to_tasks(self, callback):
        """
        Subscribe to task messages from Pub/Sub.
        
        Args:
            callback: Function to call when message received
        """
        if not self.subscriber:
            logger.error("Pub/Sub subscriber not initialized")
            return None
        
        try:
            streaming_pull_future = self.subscriber.subscribe(
                self.subscription_path,
                callback=callback
            )
            
            logger.info(f"Listening for messages on {self.subscription_path}")
            return streaming_pull_future
            
        except Exception as e:
            logger.error(f"Failed to subscribe to Pub/Sub: {e}")
            return None
    
    def acknowledge_message(self, ack_id: str):
        """Acknowledge a Pub/Sub message."""
        if not self.subscriber:
            return
        
        try:
            self.subscriber.acknowledge(
                subscription=self.subscription_path,
                ack_ids=[ack_id]
            )
        except Exception as e:
            logger.error(f"Failed to acknowledge message: {e}")


# Global instances
cloud_tasks_manager = CloudTasksManager()
pubsub_manager = PubSubManager()


def get_cloud_tasks_manager() -> CloudTasksManager:
    """Dependency injection for Cloud Tasks manager."""
    return cloud_tasks_manager


def get_pubsub_manager() -> PubSubManager:
    """Dependency injection for Pub/Sub manager."""
    return pubsub_manager

