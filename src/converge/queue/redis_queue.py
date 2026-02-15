"""Redis queue placeholder implementation."""

from __future__ import annotations

from typing import Any

from converge.queue.base import TaskQueue
from converge.queue.schemas import (
    ProjectCreateRequest,
    ProjectRecord,
    ProjectUpdateRequest,
    TaskRecord,
    TaskRequest,
    TaskResult,
)


class RedisTaskQueue(TaskQueue):
    """Redis-backed queue placeholder for future implementation."""

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a task in Redis."""
        raise NotImplementedError("TODO: implement Redis enqueue")

    def enqueue_with_dedupe(
        self, request: TaskRequest, source: str | None, idempotency_key: str | None
    ) -> TaskRecord:
        """Enqueue a task in Redis with idempotency support."""
        raise NotImplementedError("TODO: implement Redis enqueue_with_dedupe")

    def find_by_source_idempotency(
        self, source: str | None, idempotency_key: str | None
    ) -> TaskRecord | None:
        """Find a task by source/idempotency key in Redis."""
        raise NotImplementedError("TODO: implement Redis find_by_source_idempotency")

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

    def get_hitl_questions(self, task_id: str) -> list[str]:
        """Get HITL questions from Redis."""
        raise NotImplementedError("TODO: implement Redis get_hitl_questions")

    def get_hitl_resolution(self, task_id: str) -> dict[str, Any] | None:
        """Get HITL resolution from Redis."""
        raise NotImplementedError("TODO: implement Redis get_hitl_resolution")

    def resolve_hitl(self, task_id: str, resolution: dict[str, Any]) -> None:
        """Resolve HITL in Redis."""
        raise NotImplementedError("TODO: implement Redis resolve_hitl")

    def create_project(self, request: ProjectCreateRequest) -> ProjectRecord:
        """Create project in Redis."""
        raise NotImplementedError("TODO: implement Redis create_project")

    def list_projects(self) -> list[ProjectRecord]:
        """List projects from Redis."""
        raise NotImplementedError("TODO: implement Redis list_projects")

    def get_project(self, project_id: str) -> ProjectRecord:
        """Get project from Redis."""
        raise NotImplementedError("TODO: implement Redis get_project")

    def update_project(
        self, project_id: str, request: ProjectUpdateRequest
    ) -> ProjectRecord:
        """Update project in Redis."""
        raise NotImplementedError("TODO: implement Redis update_project")

    def get_default_project(self) -> ProjectRecord:
        """Get default project from Redis."""
        raise NotImplementedError("TODO: implement Redis get_default_project")
