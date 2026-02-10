"""State models for orchestration workflows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrchestrationState:
    """Represents mutable workflow state during orchestration."""

    status: str = "idle"
    events: list[str] = field(default_factory=list)
