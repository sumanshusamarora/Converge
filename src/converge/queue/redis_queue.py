"""Redis queue placeholder implementation."""

from __future__ import annotations

from converge.queue.base import TaskQueue
from converge.queue.schemas import TaskRecord, TaskRequest, TaskResult


class RedisTaskQueue(TaskQueue):
    """Redis-backed queue placeholder for future implementation."""

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a task in Redis."""
        raise NotImplementedError("TODO: implement Redis enqueue")

    def poll_and_claim(self, limit: int) -> list[TaskRecord]:
        """Claim pending tasks from Redis."""
        raise NotImplementedError("TODO: implement Redis poll_and_claim")

    def mark_running(self, task_id: str) -> None:
        """Mark a task as running in Redis."""
        raise NotImplementedError("TODO: implement Redis mark_running")

    def complete(self, task_id: str, result: TaskResult) -> None:
        """Complete a task in Redis."""
        raise NotImplementedError("TODO: implement Redis complete")

    def fail(self, task_id: str, error: str, retryable: bool) -> None:
        """Fail a task in Redis."""
        raise NotImplementedError("TODO: implement Redis fail")

    def get(self, task_id: str) -> TaskRecord:
        """Get a task from Redis."""
        raise NotImplementedError("TODO: implement Redis get")
