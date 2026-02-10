"""Configuration management for Converge."""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConvergeConfig:
    """Configuration for a Converge coordination session.

    Attributes:
        goal: The high-level goal to achieve across repositories
        repos: List of repository identifiers to coordinate
        max_rounds: Maximum number of convergence rounds (default: 2)
        output_dir: Directory for output artifacts (default: ./converge-output)
        log_level: Logging level (default: INFO)
    """

    goal: str
    repos: list[str]
    max_rounds: int = 2
    output_dir: str = "./converge-output"
    log_level: str = "INFO"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.goal.strip():
            raise ValueError("Goal cannot be empty")
        if not self.repos:
            raise ValueError("At least one repository must be specified")
        if len(self.repos) != len(set(self.repos)):
            raise ValueError("Repository list contains duplicates")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        logger.info("Config initialized: goal=%s, repos=%s", self.goal, self.repos)
