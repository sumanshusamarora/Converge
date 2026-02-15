"""Pydantic schemas for webhook ingestion endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from converge.queue.schemas import (
    ProjectCreateRequest,
    ProjectRecord,
    ProjectUpdateRequest,
    TaskRecord,
)


class WebhookTaskIngestRequest(BaseModel):
    """Generic webhook payload that directly maps to an internal task request."""

    goal: str
    repos: list[str]
    max_rounds: int = 2
    agent_provider: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = None
    source: str = "webhook"


class WebhookIngestResponse(BaseModel):
    """Response payload for webhook ingestion endpoints."""

    task_id: str
    status: str
    deduped: bool
    task_url: str | None


class JiraWebhookPayload(BaseModel):
    """Minimal permissive Jira webhook payload model."""

    model_config = ConfigDict(extra="allow")

    issue: dict[str, Any]
    webhookEvent: str | None = None


class TaskEventPayload(BaseModel):
    """Stable event shape used by timeline UI clients."""

    id: str
    ts: str
    type: Literal[
        "TASK_CREATED",
        "TASK_CLAIMED",
        "PLANNING_STARTED",
        "PROPOSAL_GENERATED",
        "ROUND_STARTED",
        "HITL_REQUIRED",
        "HITL_RESOLVED",
        "EXECUTION_STARTED",
        "EXECUTION_FINISHED",
        "ARTIFACTS_WRITTEN",
        "TASK_SUCCEEDED",
        "TASK_FAILED",
    ]
    title: str
    status: Literal["info", "success", "warning", "error"]
    details: dict[str, Any] = Field(default_factory=dict)


class PaginatedTasksResponse(BaseModel):
    """Paginated task list response."""

    items: list[TaskRecord]
    total: int
    page: int
    page_size: int
    offset: int
    has_next: bool
    has_prev: bool


class FollowupTaskRequest(BaseModel):
    """Create a follow-up task from an existing planned task."""

    instruction: str = Field(min_length=1)
    execute_immediately: bool = False


class ProjectListResponse(BaseModel):
    """Project listing response payload."""

    items: list[ProjectRecord]


class ProjectCreatePayload(ProjectCreateRequest):
    """Public create-project payload alias."""


class ProjectUpdatePayload(ProjectUpdateRequest):
    """Public update-project payload alias."""
