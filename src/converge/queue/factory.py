"""Task queue factory utilities."""

from __future__ import annotations

from converge.core.config import load_queue_settings
from converge.queue.base import TaskQueue
from converge.queue.db import DatabaseTaskQueue
from converge.queue.redis_queue import RedisTaskQueue
from converge.queue.sqs_queue import SQSTaskQueue


def create_queue() -> TaskQueue:
    """Create configured queue backend from environment variables."""
    settings = load_queue_settings()
    if settings.backend == "db":
        if not settings.sqlalchemy_database_uri:
            raise ValueError(
                "SQLALCHEMY_DATABASE_URI is required when CONVERGE_QUEUE_BACKEND=db"
            )
        return DatabaseTaskQueue(settings.sqlalchemy_database_uri)
    if settings.backend == "redis":
        return RedisTaskQueue()
    if settings.backend == "sqs":
        return SQSTaskQueue()
    raise ValueError(f"Unsupported queue backend: {settings.backend}")
