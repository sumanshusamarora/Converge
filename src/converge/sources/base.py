"""Base abstractions for external task sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from converge.queue.schemas import TaskRequest


class TaskSource(ABC):
    """Base class for push and pull oriented task sources."""

    name: str

    @abstractmethod
    def ingest(self, event: dict[str, Any]) -> TaskRequest:
        """Ingest a push event and convert it into a task request."""

    @abstractmethod
    def poll(self) -> list[TaskRequest]:
        """Poll source for tasks in pull mode."""
