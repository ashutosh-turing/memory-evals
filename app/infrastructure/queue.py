"""Redis and RQ task queue configuration."""

import logging
from typing import Any

import redis
from rq import Queue, Retry, Worker
from rq.job import Job

from app.config import settings

logger = logging.getLogger(__name__)

# Redis connection with proper encoding handling
redis_client = redis.from_url(
    settings.redis_url_str,
    decode_responses=False,  # Handle encoding manually to prevent UTF-8 errors
    health_check_interval=30,
    encoding="utf-8",
    encoding_errors="strict",
)

# Task queues with different priorities
high_priority_queue = Queue("high", connection=redis_client)
default_queue = Queue("default", connection=redis_client)
low_priority_queue = Queue("low", connection=redis_client)

# Queue mappings
QUEUE_MAPPING = {
    "high": high_priority_queue,
    "default": default_queue,
    "low": low_priority_queue,
}


class QueueManager:
    """Manages task queue operations."""

    def __init__(self):
        self.redis = redis_client
        self.queues = QUEUE_MAPPING

    def enqueue_task(
        self,
        func: str,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        queue_name: str = "default",
        job_timeout: int = 3600,
        job_id: str | None = None,
    ) -> Job:
        """Enqueue a task for background processing."""
        queue = self.queues.get(queue_name, default_queue)
        kwargs = kwargs or {}

        try:
            job = queue.enqueue(
                func,
                *args,
                **kwargs,
                timeout=job_timeout,
                job_id=job_id,
                retry=Retry(max=3),  # Retry failed jobs up to 3 times
            )
            logger.info(f"Enqueued job {job.id} in queue {queue_name}")
            return job
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise

    def get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        try:
            return Job.fetch(job_id, connection=self.redis)
        except Exception as e:
            logger.error(f"Failed to fetch job {job_id}: {e}")
            return None

    def get_job_status(self, job_id: str) -> str | None:
        """Get job status."""
        job = self.get_job(job_id)
        return job.get_status() if job else None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        try:
            job = self.get_job(job_id)
            if job:
                job.cancel()
                logger.info(f"Cancelled job {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def get_queue_length(self, queue_name: str = "default") -> int:
        """Get queue length."""
        queue = self.queues.get(queue_name, default_queue)
        return len(queue)

    def clear_queue(self, queue_name: str = "default") -> int:
        """Clear all jobs from queue."""
        queue = self.queues.get(queue_name, default_queue)
        cleared_count = queue.empty()
        logger.info(f"Cleared {cleared_count} jobs from queue {queue_name}")
        return cleared_count

    def get_failed_jobs(self, queue_name: str = "default") -> list:
        """Get failed jobs from queue."""
        queue = self.queues.get(queue_name, default_queue)
        return queue.failed_job_registry.get_job_ids()

    def requeue_failed_job(self, job_id: str) -> bool:
        """Requeue a failed job."""
        try:
            job = self.get_job(job_id)
            if job and job.is_failed:
                job.requeue()
                logger.info(f"Requeued failed job {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to requeue job {job_id}: {e}")
            return False


class WorkerManager:
    """Manages RQ workers."""

    def __init__(self, queue_names: list = None):
        self.queue_names = queue_names or ["high", "default", "low"]
        self.queues = [QUEUE_MAPPING[name] for name in self.queue_names]

    def start_worker(self, worker_name: str | None = None) -> Worker:
        """Start a worker process."""
        worker = Worker(
            self.queues,
            connection=redis_client,
            name=worker_name,
        )

        logger.info(f"Starting worker {worker.name} for queues {self.queue_names}")
        return worker

    def get_active_workers(self) -> list:
        """Get list of active workers."""
        return Worker.all(connection=redis_client)

    def get_worker_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        workers = self.get_active_workers()
        return {
            "total_workers": len(workers),
            "active_workers": len([w for w in workers if w.state == "busy"]),
            "idle_workers": len([w for w in workers if w.state == "idle"]),
            "queue_lengths": {
                name: queue.count for name, queue in QUEUE_MAPPING.items()
            },
        }


# Global instances
queue_manager = QueueManager()
worker_manager = WorkerManager()


def get_queue_manager() -> QueueManager:
    """Dependency injection for queue manager."""
    return queue_manager


def get_worker_manager() -> WorkerManager:
    """Dependency injection for worker manager."""
    return worker_manager


# Health check functions
def check_redis_connection() -> bool:
    """Check if Redis connection is healthy."""
    try:
        redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


def check_queue_health() -> dict[str, Any]:
    """Check overall queue system health."""
    health_data = {
        "redis_connected": check_redis_connection(),
        "queue_stats": {},
        "worker_stats": worker_manager.get_worker_stats(),
    }

    # Get queue statistics
    for queue_name, queue in QUEUE_MAPPING.items():
        try:
            health_data["queue_stats"][queue_name] = {
                "length": len(queue),
                "failed_count": len(queue.failed_job_registry),
                "started_count": len(queue.started_job_registry),
                "finished_count": len(queue.finished_job_registry),
            }
        except Exception as e:
            logger.error(f"Failed to get stats for queue {queue_name}: {e}")
            health_data["queue_stats"][queue_name] = {"error": str(e)}

    return health_data
