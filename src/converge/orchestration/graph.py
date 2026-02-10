"""Graph primitives for orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrchestrationGraph:
    """Simple directed graph representation for orchestration steps."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
