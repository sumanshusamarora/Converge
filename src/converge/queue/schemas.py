"""Pydantic task queue schemas shared by queue backends."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


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
    project_id: str | None = None
    custom_instructions: str | None = None
    execute_immediately: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class ProjectPreferences(BaseModel):
    """Project-level defaults that shape planning and HITL behavior."""

    planning_strategy: Literal["extend_existing", "best_practice_first"] = (
        "extend_existing"
    )
    hitl_trigger_mode: Literal["blockers_only", "strict"] = "blockers_only"
    max_hitl_questions: int = 2
    execution_flow: Literal["plan_then_execute", "plan_and_execute"] = (
        "plan_then_execute"
    )
    allow_custom_instructions_after_plan: bool = True
    enforce_existing_patterns: bool = True
    prefer_minimal_changes: bool = True
    require_best_practice_alignment: bool = False
    prompt_preamble: str | None = None

    @field_validator("max_hitl_questions")
    @classmethod
    def _validate_max_hitl_questions(cls, value: int) -> int:
        if value < 0 or value > 10:
            raise ValueError("max_hitl_questions must be between 0 and 10")
        return value


class ProjectRecord(BaseModel):
    """Project record persisted by queue backends."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    default_repos: list[str] = Field(default_factory=list)
    default_instructions: str | None = None
    preferences: ProjectPreferences = Field(default_factory=ProjectPreferences)


class ProjectCreateRequest(BaseModel):
    """Create-project payload."""

    name: str
    description: str | None = None
    default_repos: list[str] = Field(default_factory=list)
    default_instructions: str | None = None
    preferences: ProjectPreferences = Field(default_factory=ProjectPreferences)


class ProjectUpdateRequest(BaseModel):
    """Partial project update payload."""

    name: str | None = None
    description: str | None = None
    default_repos: list[str] | None = None
    default_instructions: str | None = None
    preferences: ProjectPreferences | None = None


class TaskRecord(BaseModel):
    """Task record persisted by queue backends."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    attempts: int
    request: TaskRequest
    last_error: str | None = None
    artifacts_dir: str | None = None
    source: str | None = None
    idempotency_key: str | None = None
    hitl_questions: list[str] = Field(default_factory=list)
    status_reason: str | None = None
    resolution_json: str | None = None


class TaskResult(BaseModel):
    """Outcome payload written by workers after task execution."""

    status: TaskStatus
    summary: str
    artifacts_dir: str | None = None
    hitl_questions: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    status_reason: str | None = None
