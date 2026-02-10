"""Configuration management for Converge."""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConvergeConfig:
    """Configuration for a Converge coordination session."""

    goal: str
    repos: list[str]
    max_rounds: int = 2
    output_dir: str = ".converge"
    log_level: str = "INFO"
    model: str | None = None
    no_llm: bool = False
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
