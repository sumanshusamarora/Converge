"""Coordination orchestration logic."""

import logging
from pathlib import Path

from converge.core.config import ConvergeConfig
from converge.orchestration.state import (
    CoordinationState,
    CoordinationStatus,
    RepositoryConstraints,
    ResponsibilitySplit,
)

logger = logging.getLogger(__name__)


class Coordinator:
    """Orchestrates multi-repository coordination.

    The Coordinator implements bounded convergence:
    1. Collect constraints from each repository
    2. Propose responsibility split
    3. Converge on decisions (bounded rounds)
    4. Escalate to human if needed
    """

    def __init__(self, config: ConvergeConfig) -> None:
        """Initialize the coordinator.

        Args:
            config: Configuration for the coordination session
        """
        self.config = config
        self.state = CoordinationState(
            goal=config.goal,
            repos=config.repos,
            max_rounds=config.max_rounds,
        )
        logger.info("Coordinator initialized for goal: %s", config.goal)

    def coordinate(self) -> CoordinationState:
        """Execute the full coordination workflow.

        Returns:
            Final coordination state
        """
        logger.info("Starting coordination workflow")

        # Step 1: Collect constraints
        self._collect_constraints()

        # Step 2: Propose responsibility split
        self._propose_split()

        # Step 3: Bounded convergence
        self._converge()

        # Step 4: Generate artifacts
        self._generate_artifacts()

        logger.info("Coordination complete with status: %s", self.state.status)
        return self.state

    def _collect_constraints(self) -> None:
        """Collect constraints from each repository (stubbed for MVP)."""
        logger.info("Collecting constraints from %d repositories", len(self.config.repos))
        self.state.update_status(CoordinationStatus.COLLECTING_CONSTRAINTS)

        for repo in self.config.repos:
            # Stub: In real implementation, this would query the repository
            # for constraints like tech stack, ownership, existing APIs, etc.
            constraints = RepositoryConstraints(
                repo=repo,
                constraints=[
                    f"Repository {repo} is ready for coordination",
                    f"No blocking constraints identified in {repo}",
                ],
                metadata={"stub": True},
            )
            self.state.constraints[repo] = constraints
            logger.info("Collected constraints for repo: %s", repo)

    def _propose_split(self) -> None:
        """Propose a responsibility split across repositories."""
        logger.info("Proposing responsibility split")
        self.state.update_status(CoordinationStatus.PROPOSING_SPLIT)

        # Stub: In real implementation, this would use AI/logic to determine
        # optimal split based on constraints, architecture, and best practices
        assignments: dict[str, list[str]] = {}
        for repo in self.config.repos:
            assignments[repo] = [
                f"Handle {repo}-specific implementation of: {self.config.goal}",
            ]

        self.state.proposed_split = ResponsibilitySplit(
            assignments=assignments,
            rationale=(
                f"Split based on repository boundaries for goal: {self.config.goal}. "
                "Each repository handles its own domain-specific implementation."
            ),
            risks=[
                "Cross-repository contract changes may require coordination",
                "Shared data structures need careful versioning",
            ],
        )
        logger.info("Responsibility split proposed")

    def _converge(self) -> None:
        """Execute bounded convergence rounds."""
        logger.info("Starting convergence rounds (max: %d)", self.config.max_rounds)
        self.state.update_status(CoordinationStatus.CONVERGING)

        while self.state.round_number < self.config.max_rounds:
            self.state.increment_round()
            logger.info("Executing convergence round %d", self.state.round_number)

            # Stub: In real implementation, this would:
            # - Validate the proposed split
            # - Get feedback from each repository
            # - Adjust the split based on feedback
            # - Check for agreement
            decision = (
                f"Round {self.state.round_number}: "
                f"Validated split for {len(self.config.repos)} repositories"
            )
            self.state.add_decision(decision)

            # Check if we should converge or escalate
            if self._check_convergence():
                self.state.update_status(CoordinationStatus.CONVERGED)
                logger.info("Convergence achieved in round %d", self.state.round_number)
                return

        # Max rounds reached - escalate
        self._escalate("Maximum convergence rounds reached without full agreement")

    def _check_convergence(self) -> bool:
        """Check if convergence criteria are met.

        Returns:
            True if converged, False otherwise
        """
        # Stub: In real implementation, this would check:
        # - All repositories accept the proposed split
        # - No blocking constraints remain
        # - Contracts are well-defined
        # For MVP, we converge after first round
        return self.state.round_number >= 1

    def _escalate(self, reason: str) -> None:
        """Escalate to human decision-maker.

        Args:
            reason: Reason for escalation
        """
        logger.warning("Escalating coordination: %s", reason)
        self.state.escalation_reason = reason
        self.state.update_status(CoordinationStatus.ESCALATED)

    def _generate_artifacts(self) -> None:
        """Generate human-readable artifacts."""
        logger.info("Generating coordination artifacts")
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate summary file
        summary_path = output_dir / "coordination-summary.md"
        summary = self._build_summary()
        summary_path.write_text(summary)
        logger.info("Summary written to: %s", summary_path)

        # Generate responsibility matrix
        matrix_path = output_dir / "responsibility-matrix.md"
        matrix = self._build_responsibility_matrix()
        matrix_path.write_text(matrix)
        logger.info("Responsibility matrix written to: %s", matrix_path)

    def _build_summary(self) -> str:
        """Build coordination summary document.

        Returns:
            Markdown-formatted summary
        """
        lines = [
            "# Coordination Summary",
            "",
            f"**Goal:** {self.state.goal}",
            f"**Status:** {self.state.status.value}",
            f"**Repositories:** {', '.join(self.state.repos)}",
            f"**Rounds:** {self.state.round_number} / {self.state.max_rounds}",
            "",
            "## Constraints Collected",
            "",
        ]

        for repo, constraints in self.state.constraints.items():
            lines.append(f"### {repo}")
            for constraint in constraints.constraints:
                lines.append(f"- {constraint}")
            lines.append("")

        if self.state.proposed_split:
            lines.extend(
                [
                    "## Proposed Responsibility Split",
                    "",
                    f"**Rationale:** {self.state.proposed_split.rationale}",
                    "",
                ]
            )

            if self.state.proposed_split.risks:
                lines.append("**Risks:**")
                for risk in self.state.proposed_split.risks:
                    lines.append(f"- {risk}")
                lines.append("")

        if self.state.decisions:
            lines.extend(["## Decisions", ""])
            for decision in self.state.decisions:
                lines.append(f"- {decision}")
            lines.append("")

        if self.state.escalation_reason:
            lines.extend(
                [
                    "## Escalation",
                    "",
                    f"**Reason:** {self.state.escalation_reason}",
                    "",
                    "**Action Required:** Human review and decision needed.",
                    "",
                ]
            )

        return "\n".join(lines)

    def _build_responsibility_matrix(self) -> str:
        """Build responsibility matrix document.

        Returns:
            Markdown-formatted responsibility matrix
        """
        lines = [
            "# Responsibility Matrix",
            "",
            f"**Goal:** {self.state.goal}",
            "",
        ]

        if self.state.proposed_split:
            for repo, responsibilities in self.state.proposed_split.assignments.items():
                lines.append(f"## {repo}")
                lines.append("")
                for resp in responsibilities:
                    lines.append(f"- {resp}")
                lines.append("")

        return "\n".join(lines)
