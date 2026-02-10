"""Agent factory for creating coding agents by provider name."""

import logging
import os

from converge.agents.base import CodingAgent
from converge.agents.codex_agent import CodexAgent
from converge.agents.copilot_agent import GitHubCopilotAgent

logger = logging.getLogger(__name__)


def create_agent(name: str | None = None) -> CodingAgent:
    """Create a coding agent by provider name.

    Args:
        name: Agent provider name ("codex" or "copilot").
              If None, uses CONVERGE_AGENT_PROVIDER env var (default: "codex")

    Returns:
        CodingAgent instance

    Raises:
        ValueError: If provider name is unknown
    """
    if name is None:
        name = os.getenv("CONVERGE_AGENT_PROVIDER", "codex")

    name_lower = name.lower()

    if name_lower == "codex":
        logger.info("Creating CodexAgent")
        return CodexAgent()
    elif name_lower == "copilot":
        logger.info("Creating GitHubCopilotAgent")
        return GitHubCopilotAgent()
    else:
        raise ValueError(f"Unknown agent provider: {name}. Supported providers: codex, copilot")
