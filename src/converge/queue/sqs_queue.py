"""Amazon SQS queue placeholder implementation."""

from __future__ import annotations

from converge.queue.base import TaskQueue
from converge.queue.schemas import TaskRecord, TaskRequest, TaskResult


class SQSTaskQueue(TaskQueue):
    """SQS-backed queue placeholder for future implementation."""

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a task in SQS."""
        raise NotImplementedError("TODO: implement SQS enqueue")

    def poll_and_claim(self, limit: int) -> list[TaskRecord]:
        """Claim pending tasks from SQS."""
        raise NotImplementedError("TODO: implement SQS poll_and_claim")

    def mark_running(self, task_id: str) -> None:
        """Mark a task as running in SQS."""
        raise NotImplementedError("TODO: implement SQS mark_running")

    def complete(self, task_id: str, result: TaskResult) -> None:
        """Complete a task in SQS."""
        raise NotImplementedError("TODO: implement SQS complete")

    def fail(self, task_id: str, error: str, retryable: bool) -> None:
        """Fail a task in SQS."""
        raise NotImplementedError("TODO: implement SQS fail")

    def get(self, task_id: str) -> TaskRecord:
        """Get a task from SQS."""
        raise NotImplementedError("TODO: implement SQS get")
