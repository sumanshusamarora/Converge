"""Amazon SQS queue placeholder implementation."""

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


class SQSTaskQueue(TaskQueue):
    """SQS-backed queue placeholder for future implementation."""

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a task in SQS."""
        raise NotImplementedError("TODO: implement SQS enqueue")

    def enqueue_with_dedupe(
        self, request: TaskRequest, source: str | None, idempotency_key: str | None
    ) -> TaskRecord:
        """Enqueue a task in SQS with idempotency support."""
        raise NotImplementedError("TODO: implement SQS enqueue_with_dedupe")

    def find_by_source_idempotency(
        self, source: str | None, idempotency_key: str | None
    ) -> TaskRecord | None:
        """Find a task by source/idempotency key in SQS."""
        raise NotImplementedError("TODO: implement SQS find_by_source_idempotency")

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

    def get_hitl_questions(self, task_id: str) -> list[str]:
        """Get HITL questions from SQS."""
        raise NotImplementedError("TODO: implement SQS get_hitl_questions")

    def get_hitl_resolution(self, task_id: str) -> dict[str, Any] | None:
        """Get HITL resolution from SQS."""
        raise NotImplementedError("TODO: implement SQS get_hitl_resolution")

    def resolve_hitl(self, task_id: str, resolution: dict[str, Any]) -> None:
        """Resolve HITL in SQS."""
        raise NotImplementedError("TODO: implement SQS resolve_hitl")

    def create_project(self, request: ProjectCreateRequest) -> ProjectRecord:
        """Create project in SQS."""
        raise NotImplementedError("TODO: implement SQS create_project")

    def list_projects(self) -> list[ProjectRecord]:
        """List projects from SQS."""
        raise NotImplementedError("TODO: implement SQS list_projects")

    def get_project(self, project_id: str) -> ProjectRecord:
        """Get project from SQS."""
        raise NotImplementedError("TODO: implement SQS get_project")

    def update_project(
        self, project_id: str, request: ProjectUpdateRequest
    ) -> ProjectRecord:
        """Update project in SQS."""
        raise NotImplementedError("TODO: implement SQS update_project")

    def get_default_project(self) -> ProjectRecord:
        """Get default project from SQS."""
        raise NotImplementedError("TODO: implement SQS get_default_project")
