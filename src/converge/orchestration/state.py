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


Status = Literal["CONVERGED", "HITL_REQUIRED", "FAILED"]


class OrchestrationState(TypedDict):
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
