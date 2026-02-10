"""Agent abstraction layer for Converge coordination."""

from converge.agents.base import (
    AgentProvider,
    AgentResult,
    AgentTask,
    CodingAgent,
    RepoContext,
)
from converge.agents.factory import create_agent

__all__ = [
    "AgentProvider",
    "AgentResult",
    "AgentTask",
    "CodingAgent",
    "RepoContext",
    "create_agent",
]
