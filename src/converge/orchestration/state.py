"""Typed state for LangGraph orchestration."""

from pathlib import Path
from typing import Any, Literal, TypedDict


class EventRecord(TypedDict):
    """Machine-readable event produced during a coordination run."""

    node: str
    message: str


class RepositorySignal(TypedDict):
    """Discovered repository signals and constraints."""

    path: str
    exists: bool
    repo_type: str
    signals: list[str]
    constraints: list[str]


class RepoPlan(TypedDict):
    """Agent plan result for a single repository."""

    repo_path: str
    provider: str
    status: str
    summary: str
    proposed_changes: list[str]
    questions_for_hitl: list[str]
    raw: dict[str, Any]


Status = Literal["CONVERGED", "HITL_REQUIRED", "FAILED"]
HILMode = Literal["conditional", "interrupt"]


class OrchestrationState(TypedDict, total=False):
    """State container shared by LangGraph nodes."""

    goal: str
    repos: list[RepositorySignal]
    round: int
    max_rounds: int
    events: list[EventRecord]
    status: Status
    proposal: dict[str, Any]
    artifacts_dir: Path
    output_dir: str
    model: str | None
    no_llm: bool
    human_decision: dict[str, Any] | None
    hil_mode: HILMode
    repo_plans: list[RepoPlan]
    contract_analysis: dict[str, Any]
    agent_provider: str
    hitl_resolution: dict[str, Any] | None
