"""Abstract task queue interface for Converge."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from converge.queue.schemas import (
    ProjectCreateRequest,
    ProjectRecord,
    ProjectUpdateRequest,
    TaskRecord,
    TaskRequest,
    TaskResult,
)


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

    @abstractmethod
    def get_hitl_questions(self, task_id: str) -> list[str]:
        """Get HITL questions for a task in HITL_REQUIRED status.

        Args:
            task_id: The task ID

        Returns:
            List of questions that require human judgment
        """

    @abstractmethod
    def get_hitl_resolution(self, task_id: str) -> dict[str, Any] | None:
        """Get HITL resolution if it exists.

        Args:
            task_id: The task ID

        Returns:
            Resolution data if available, None otherwise
        """

    @abstractmethod
    def resolve_hitl(self, task_id: str, resolution: dict[str, Any]) -> None:
        """Resolve HITL questions and transition task back to PENDING.

        Args:
            task_id: The task ID
            resolution: Human decision/resolution data

        Raises:
            ValueError: If task is not in HITL_REQUIRED status
        """

    @abstractmethod
    def create_project(self, request: ProjectCreateRequest) -> ProjectRecord:
        """Create a project with default planning preferences."""

    @abstractmethod
    def list_projects(self) -> list[ProjectRecord]:
        """List all projects sorted by creation/update time."""

    @abstractmethod
    def get_project(self, project_id: str) -> ProjectRecord:
        """Get a project by id."""

    @abstractmethod
    def update_project(
        self, project_id: str, request: ProjectUpdateRequest
    ) -> ProjectRecord:
        """Update a project by id."""

    @abstractmethod
    def get_default_project(self) -> ProjectRecord:
        """Return the default project used when project_id is omitted."""
