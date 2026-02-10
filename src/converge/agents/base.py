"""Base abstractions for coding agents in Converge.

Converge is a coordination-first tool that helps peer repositories
collaborate safely. This module defines a provider-agnostic interface
for coding agents to produce plans and proposals without directly
modifying code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class AgentProvider(str, Enum):
    """Supported agent providers for Converge coordination."""

    CODEX = "codex"
    COPILOT = "copilot"


@dataclass
class RepoContext:
    """Repository context passed to agent for planning.

    Attributes:
        path: Absolute or relative path to repository
        kind: Optional repository classification (e.g., "backend", "frontend", "service", "docs")
        signals: Discovered technology signals (e.g., ["pyproject.toml", "package.json"])
        readme_excerpt: Optional excerpt from repository README for context
    """

    path: Path
    kind: str | None = None
    signals: list[str] = field(default_factory=list)
    readme_excerpt: str | None = None


@dataclass
class AgentTask:
    """Task specification for agent planning.

    Attributes:
        goal: High-level goal to achieve in this repository
        repo: Repository context with signals and metadata
        instructions: Project-specific rules or constraints from AGENTS.md
        max_steps: Maximum planning iterations (default: 5)
    """

    goal: str
    repo: RepoContext
    instructions: str
    max_steps: int = 5


@dataclass
class AgentResult:
    """Result from agent planning or execution.

    This is the primary contract between agents and Converge's coordinator.
    Agents produce proposals, not patches, by default.

    Attributes:
        provider: Which agent provider produced this result
        status: Overall outcome status
        summary: Human-readable summary of what the agent proposes
        proposed_changes: High-level bullet points describing changes (no diffs required)
        questions_for_hitl: Questions that require human judgment
        raw: Provider-specific metadata (safe to store; no secrets)
    """

    provider: AgentProvider
    status: Literal["OK", "HITL_REQUIRED", "FAILED"]
    summary: str
    proposed_changes: list[str]
    questions_for_hitl: list[str]
    raw: dict[str, object]


class CodingAgent(ABC):
    """Abstract base class for coding agents.

    Converge uses coding agents to produce plans and proposals for
    repository changes. Agents are coordination-first: they do not
    automatically modify code unless explicitly enabled.
    """

    @property
    @abstractmethod
    def provider(self) -> AgentProvider:
        """Return the agent provider identifier."""

    @abstractmethod
    def plan(self, task: AgentTask) -> AgentResult:
        """Produce a plan or proposal for achieving the task goal.

        This method is safe and non-destructive by default. It analyzes
        the repository, considers constraints, and produces a structured
        plan without making changes.

        Args:
            task: The task specification with goal, repo context, and instructions

        Returns:
            AgentResult with status, summary, and proposed changes
        """

    @abstractmethod
    def supports_execution(self) -> bool:
        """Return True if this agent can execute changes (with permission).

        Codex CLI-based agents may support execution via tool use.
        Prompt-pack generators (e.g., Copilot adapter) return False.
        """
