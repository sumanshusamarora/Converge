"""State management for coordination sessions."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CoordinationStatus(str, Enum):
    """Status of a coordination session."""

    INITIALIZED = "initialized"
    COLLECTING_CONSTRAINTS = "collecting_constraints"
    PROPOSING_SPLIT = "proposing_split"
    CONVERGING = "converging"
    CONVERGED = "converged"
    ESCALATED = "escalated"
    FAILED = "failed"


@dataclass
class RepositoryConstraints:
    """Constraints collected from a single repository.

    Attributes:
        repo: Repository identifier
        constraints: List of constraint descriptions (stubbed for MVP)
        metadata: Additional metadata about the repository
    """

    repo: str
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponsibilitySplit:
    """Proposed split of responsibilities across repositories.

    Attributes:
        assignments: Mapping of repository to list of responsibilities
        rationale: Explanation for the proposed split
        risks: Identified risks or concerns
    """

    assignments: dict[str, list[str]] = field(default_factory=dict)
    rationale: str = ""
    risks: list[str] = field(default_factory=list)


@dataclass
class CoordinationState:
    """State tracking for a coordination session.

    Attributes:
        goal: The coordination goal
        repos: List of repositories involved
        status: Current status of the session
        round_number: Current convergence round (starts at 0)
        max_rounds: Maximum allowed rounds
        constraints: Collected constraints per repository
        proposed_split: Proposed responsibility split
        decisions: List of decisions made during convergence
        escalation_reason: Reason for escalation (if status is ESCALATED)
        created_at: Session creation timestamp
        updated_at: Last update timestamp
    """

    goal: str
    repos: list[str]
    status: CoordinationStatus = CoordinationStatus.INITIALIZED
    round_number: int = 0
    max_rounds: int = 2
    constraints: dict[str, RepositoryConstraints] = field(default_factory=dict)
    proposed_split: ResponsibilitySplit | None = None
    decisions: list[str] = field(default_factory=list)
    escalation_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_status(self, new_status: CoordinationStatus) -> None:
        """Update the coordination status.

        Args:
            new_status: The new status to transition to
        """
        logger.info("Status transition: %s -> %s", self.status, new_status)
        self.status = new_status
        self.updated_at = datetime.now()

    def increment_round(self) -> None:
        """Increment the convergence round counter."""
        self.round_number += 1
        self.updated_at = datetime.now()
        logger.info("Round incremented to %d", self.round_number)

    def should_escalate(self) -> bool:
        """Check if session should be escalated to human.

        Returns:
            True if escalation is needed
        """
        return self.round_number >= self.max_rounds

    def add_decision(self, decision: str) -> None:
        """Add a decision to the session.

        Args:
            decision: Description of the decision
        """
        self.decisions.append(decision)
        self.updated_at = datetime.now()
        logger.info("Decision added: %s", decision)
