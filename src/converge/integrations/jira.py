"""Jira webhook mapping helpers."""

from __future__ import annotations

import json
from typing import Any

from converge.queue.schemas import TaskRequest
from converge.server.schemas import JiraWebhookPayload

_MAX_DESCRIPTION_EXCERPT = 500


def jira_payload_to_task(
    payload: JiraWebhookPayload,
    default_repos: list[str] | None = None,
) -> tuple[TaskRequest, str]:
    """Convert a Jira webhook payload into an internal task and idempotency key."""
    issue = payload.issue
    issue_key = _as_string(issue.get("key"), fallback="UNKNOWN")
    fields = cast_dict(issue.get("fields"))
    summary = _as_string(fields.get("summary"), fallback="(no summary)")
    description_excerpt = _extract_description_excerpt(fields.get("description"))

    goal = f"Jira {issue_key}: {summary}\n\n{description_excerpt}".strip()
    dedupe_event_name = payload.webhookEvent or "event"
    idempotency_key = f"{issue_key}:{dedupe_event_name}"

    return (
        TaskRequest(
            goal=goal,
            repos=list(default_repos or []),
            max_rounds=2,
            agent_provider=None,
            metadata={"jira_issue_key": issue_key, "jira_event": dedupe_event_name},
        ),
        idempotency_key,
    )


def cast_dict(value: Any) -> dict[str, Any]:
    """Safely cast unknown payload values to dictionary values."""
    if isinstance(value, dict):
        return value
    return {}


def _extract_description_excerpt(description_value: Any) -> str:
    """Extract a robust string excerpt from Jira description values."""
    if isinstance(description_value, str):
        return description_value[:_MAX_DESCRIPTION_EXCERPT]
    if isinstance(description_value, dict):
        serialized = json.dumps(description_value, ensure_ascii=False)
        return serialized[:_MAX_DESCRIPTION_EXCERPT]
    if description_value is None:
        return ""
    return str(description_value)[:_MAX_DESCRIPTION_EXCERPT]


def _as_string(value: Any, fallback: str) -> str:
    """Convert unknown values to string with fallback."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback
