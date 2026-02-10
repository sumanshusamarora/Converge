"""Abstract task queue interface for Converge."""

from __future__ import annotations

from abc import ABC, abstractmethod

from converge.queue.schemas import TaskRecord, TaskRequest, TaskResult


class TaskQueue(ABC):
    """Contract that all queue backends must implement."""

    @abstractmethod
    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a new task request."""

    @abstractmethod
    def enqueue_with_dedupe(
        self, request: TaskRequest, source: str | None, idempotency_key: str | None
    ) -> TaskRecord:
        """Enqueue a task using source-aware idempotency when provided."""

    @abstractmethod
    def find_by_source_idempotency(
        self, source: str | None, idempotency_key: str | None
    ) -> TaskRecord | None:
        """Find a task by source/idempotency key pair."""

    @abstractmethod
    def poll_and_claim(self, limit: int) -> list[TaskRecord]:
        """Poll pending tasks and atomically claim up to ``limit`` tasks."""

    @abstractmethod
    def mark_running(self, task_id: str) -> None:
        """Mark a claimed task as actively running."""

    @abstractmethod
    def complete(self, task_id: str, result: TaskResult) -> None:
        """Mark task as complete with a final result."""

    @abstractmethod
    def fail(self, task_id: str, error: str, retryable: bool) -> None:
        """Mark task failure and optionally retry based on backend policy."""

    @abstractmethod
    def get(self, task_id: str) -> TaskRecord:
        """Return latest task record by id."""
