"""Jira task source adapter."""

from __future__ import annotations

from typing import Any

from converge.integrations.jira import jira_payload_to_task
from converge.queue.schemas import TaskRequest
from converge.server.schemas import JiraWebhookPayload
from converge.sources.base import TaskSource


class JiraTaskSource(TaskSource):
    """Task source that maps Jira webhook events into Converge tasks."""

    name = "jira"

    def __init__(self, default_repos: list[str] | None = None) -> None:
        self._default_repos = default_repos or []

    def ingest(self, event: dict[str, Any]) -> TaskRequest:
        """Convert a Jira event payload into a task request."""
        payload = JiraWebhookPayload.model_validate(event)
        task_request, _ = jira_payload_to_task(payload, default_repos=self._default_repos)
        return task_request

    def poll(self) -> list[TaskRequest]:
        """Polling is not implemented for Jira in this iteration."""
        return []
