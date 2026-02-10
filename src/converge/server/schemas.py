"""Pydantic schemas for webhook ingestion endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
