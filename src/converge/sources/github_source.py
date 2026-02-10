"""GitHub task source placeholder."""

from __future__ import annotations

from typing import Any

from converge.queue.schemas import TaskRequest
from converge.sources.base import TaskSource


class GitHubTaskSource(TaskSource):
    """Placeholder for future GitHub webhook and polling support."""

    name = "github"

    def ingest(self, event: dict[str, Any]) -> TaskRequest:
        """Convert a GitHub event payload into a task request."""
        raise NotImplementedError("TODO: implement GitHub webhook mapper")

    def poll(self) -> list[TaskRequest]:
        """Poll GitHub source for tasks."""
        raise NotImplementedError("TODO: implement GitHub polling source")
