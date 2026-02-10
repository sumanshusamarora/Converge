"""Pydantic task queue schemas shared by queue backends."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task lifecycle states used across queue implementations."""

    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    HITL_REQUIRED = "HITL_REQUIRED"
    CANCELLED = "CANCELLED"


class TaskRequest(BaseModel):
    """Task request payload submitted by clients."""

    goal: str
    repos: list[str]
    max_rounds: int = 2
    agent_provider: str | None = None
    metadata: dict[str, object] = cast(dict[str, object], Field(default_factory=dict))


class TaskRecord(BaseModel):
    """Task record persisted by queue backends."""

    id: str = cast(str, Field(default_factory=lambda: str(uuid4())))
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    attempts: int
    request: TaskRequest
    last_error: str | None = None
    artifacts_dir: str | None = None


class TaskResult(BaseModel):
    """Outcome payload written by workers after task execution."""

    status: TaskStatus
    summary: str
    artifacts_dir: str | None = None
    hitl_questions: list[str] = cast(list[str], Field(default_factory=list))
    details: dict[str, Any] = cast(dict[str, Any], Field(default_factory=dict))
