"""Coordination orchestration logic."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from converge.core.config import ConvergeConfig
from converge.orchestration.state import (
    CoordinationState,
    CoordinationStatus,
    EventRecord,
    RepositoryConstraints,
    ResponsibilitySplit,
)

logger = logging.getLogger(__name__)

README_LINE_LIMIT = 40
README_CHAR_LIMIT = 2000


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
        self.run_dir = self._build_run_directory(config.output_dir)
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

    def _build_run_directory(self, base_output_dir: str) -> Path:
        """Build and create a run-scoped output directory.

        Args:
            base_output_dir: Base output directory provided by configuration

        Returns:
            Created run directory path
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = Path(base_output_dir) / "runs" / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _record_event(
        self, action: str, repo: str | None = None, details: dict[str, Any] | None = None
    ) -> None:
        """Record a machine-readable event for the run."""
        event: EventRecord = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "repo": repo,
            "details": details or {},
        }
        self.state.events.append(event)

    def _collect_constraints(self) -> None:
        """Collect lightweight, grounded constraints from each repository path."""
        logger.info("Collecting constraints from %d repositories", len(self.config.repos))
        self.state.update_status(CoordinationStatus.COLLECTING_CONSTRAINTS)

        for repo in self.config.repos:
            repo_path = Path(repo)
            constraints: list[str] = []
            metadata: dict[str, Any] = {"exists": repo_path.exists()}

            if not repo_path.exists():
                constraints.append("repo path not found")
                metadata["repo_type"] = "unknown"
                self.state.constraints[repo] = RepositoryConstraints(
                    repo=repo,
                    constraints=constraints,
                    metadata=metadata,
                )
                self._record_event(
                    action="collect_constraints",
                    repo=repo,
                    details={"exists": False, "constraint_count": len(constraints)},
                )
                logger.warning("Repository path does not exist: %s", repo)
                continue

            signals = self._discover_signals(repo_path)
            repo_type = self._detect_repo_type(signals)
            metadata["repo_type"] = repo_type
            metadata["signals"] = signals

            readme_excerpt = self._read_readme_excerpt(repo_path)
            if readme_excerpt:
                metadata["readme_excerpt"] = readme_excerpt

            constraints.extend(self._constraints_from_signals(repo_type, signals))
            if not constraints:
                constraints.append("No obvious project-type constraints detected")

            self.state.constraints[repo] = RepositoryConstraints(
                repo=repo,
                constraints=constraints,
                metadata=metadata,
            )
            self._record_event(
                action="collect_constraints",
                repo=repo,
                details={
                    "exists": True,
                    "repo_type": repo_type,
                    "signals": signals,
                    "constraint_count": len(constraints),
                },
            )
            logger.info("Collected constraints for repo: %s", repo)

    def _discover_signals(self, repo_path: Path) -> list[str]:
        """Discover project-type signals from known files."""
        signal_files = ["pyproject.toml", "requirements.txt", "package.json", "README.md"]
        return [signal for signal in signal_files if (repo_path / signal).exists()]

    def _detect_repo_type(self, signals: list[str]) -> str:
        """Detect repository type from discovered signals."""
        if "pyproject.toml" in signals or "requirements.txt" in signals:
            return "python"
        if "package.json" in signals:
            return "node"
        return "unknown"

    def _read_readme_excerpt(self, repo_path: Path) -> str:
        """Read a short and safe README excerpt for context."""
        readme_path = repo_path / "README.md"
        if not readme_path.exists():
            return ""

        lines = readme_path.read_text(encoding="utf-8", errors="replace").splitlines()
        excerpt = "\n".join(lines[:README_LINE_LIMIT]).strip()
        if len(excerpt) > README_CHAR_LIMIT:
            return f"{excerpt[:README_CHAR_LIMIT].rstrip()}..."
        return excerpt

    def _constraints_from_signals(self, repo_type: str, signals: list[str]) -> list[str]:
        """Generate lightweight constraints from discovered repo signals."""
        constraints: list[str] = []
        if repo_type == "python":
            constraints.append("Python project detected (pyproject.toml/requirements.txt)")
        elif repo_type == "node":
            constraints.append("Node project detected (package.json)")

        if "README.md" in signals:
            constraints.append("Repository documentation found (README.md)")
        return constraints

    def _propose_split(self) -> None:
        """Propose a responsibility split across repositories."""
        logger.info("Proposing responsibility split")
        self.state.update_status(CoordinationStatus.PROPOSING_SPLIT)

        assignments: dict[str, list[str]] = {}
        rationale_parts: list[str] = []
        for repo in self.config.repos:
            repo_constraints = self.state.constraints.get(repo)
            repo_type = "unknown"
            signals: list[str] = []
            if repo_constraints:
                repo_type = str(repo_constraints.metadata.get("repo_type", "unknown"))
                raw_signals = repo_constraints.metadata.get("signals", [])
                signals = [str(signal) for signal in raw_signals if isinstance(signal, str)]

            assignments[repo] = self._assignment_for_repo(repo, repo_type)
            signals_text = ", ".join(signals) if signals else "none"
            rationale_parts.append(f"{repo}: repo_type={repo_type}, signals={signals_text}")

        self.state.proposed_split = ResponsibilitySplit(
            assignments=assignments,
            rationale=(
                "Proposed split for goal "
                f"'{self.config.goal}' based on detected repository metadata. "
                + " | ".join(rationale_parts)
            ),
            risks=[
                "Cross-repository contract changes may require coordination",
                "Shared data structures need careful versioning",
            ],
        )
        self._record_event(
            action="propose_split",
            details={"repos": list(self.config.repos), "assignment_count": len(assignments)},
        )
        logger.info("Responsibility split proposed")

    def _assignment_for_repo(self, repo: str, repo_type: str) -> list[str]:
        """Build responsibility assignment using repo type and naming hints."""
        repo_name = repo.lower()
        if repo_type == "python" or any(
            hint in repo_name for hint in ["backend", "service", "api"]
        ):
            return [
                f"Implement validation rules for {self.config.goal}",
                "Own business logic changes",
                "Handle storage and persistence updates",
            ]
        if repo_type == "node" or any(hint in repo_name for hint in ["frontend", "web", "ui"]):
            return [
                f"Implement UX updates for {self.config.goal}",
                "Own client-side state changes",
                "Handle presentation-layer updates",
            ]
        return [
            f"Implement {self.config.goal} in its owned domain",
            "Coordinate interfaces with peer repositories",
        ]

    def _converge(self) -> None:
        """Execute bounded convergence rounds."""
        logger.info("Starting convergence rounds (max: %d)", self.config.max_rounds)
        self.state.update_status(CoordinationStatus.CONVERGING)

        while self.state.round_number < self.config.max_rounds:
            self.state.increment_round()
            logger.info("Executing convergence round %d", self.state.round_number)

            decision = (
                f"Round {self.state.round_number}: "
                f"Validated split for {len(self.config.repos)} repositories"
            )
            self.state.add_decision(decision)
            self._record_event(
                action="round",
                details={"round_number": self.state.round_number, "decision": decision},
            )

            if self._check_convergence():
                self.state.update_status(CoordinationStatus.CONVERGED)
                logger.info("Convergence achieved in round %d", self.state.round_number)
                return

        self._escalate("Maximum convergence rounds reached without full agreement")

    def _check_convergence(self) -> bool:
        """Check if convergence criteria are met.

        Returns:
            True if converged, False otherwise
        """
        has_missing_repo = any(
            "repo path not found" in repo_constraints.constraints
            for repo_constraints in self.state.constraints.values()
        )
        has_split = self.state.proposed_split is not None and bool(
            self.state.proposed_split.assignments
        )
        return (not has_missing_repo) and has_split and self.state.round_number >= 1

    def _escalate(self, reason: str) -> None:
        """Escalate to human decision-maker.

        Args:
            reason: Reason for escalation
        """
        logger.warning("Escalating coordination: %s", reason)
        self.state.escalation_reason = reason
        self.state.update_status(CoordinationStatus.ESCALATED)
        self._record_event(action="escalate", details={"reason": reason})

    def _generate_artifacts(self) -> None:
        """Generate run-scoped human-readable and machine artifacts."""
        logger.info("Generating coordination artifacts")

        summary_path = self.run_dir / "summary.md"
        summary = self._build_summary()
        summary_path.write_text(summary, encoding="utf-8")
        self._record_event(
            action="write_artifact",
            details={"artifact": "summary.md", "path": str(summary_path)},
        )
        logger.info("Summary written to: %s", summary_path)

        matrix_path = self.run_dir / "responsibility-matrix.md"
        matrix = self._build_responsibility_matrix()
        matrix_path.write_text(matrix, encoding="utf-8")
        self._record_event(
            action="write_artifact",
            details={"artifact": "responsibility-matrix.md", "path": str(matrix_path)},
        )
        logger.info("Responsibility matrix written to: %s", matrix_path)

        constraints_path = self.run_dir / "constraints.json"
        constraints_payload = self._build_constraints_payload()
        constraints_path.write_text(json.dumps(constraints_payload, indent=2), encoding="utf-8")
        self._record_event(
            action="write_artifact",
            details={"artifact": "constraints.json", "path": str(constraints_path)},
        )
        logger.info("Constraints written to: %s", constraints_path)

        run_path = self.run_dir / "run.json"
        run_payload = self._build_run_payload()
        run_path.write_text(json.dumps(run_payload, indent=2), encoding="utf-8")
        logger.info("Run log written to: %s", run_path)

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
            f"**Run Directory:** {self.run_dir}",
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

    def _build_constraints_payload(self) -> dict[str, Any]:
        """Build machine-readable constraints payload."""
        repos: list[dict[str, Any]] = []
        for repo_name, repo_constraints in self.state.constraints.items():
            repos.append(
                {
                    "repo": repo_name,
                    "constraints": repo_constraints.constraints,
                    "metadata": repo_constraints.metadata,
                }
            )

        return {
            "goal": self.state.goal,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repos": repos,
        }

    def _build_run_payload(self) -> dict[str, Any]:
        """Build machine-readable run audit payload."""
        return {
            "goal": self.state.goal,
            "status": self.state.status.value,
            "round_number": self.state.round_number,
            "max_rounds": self.state.max_rounds,
            "escalation_reason": self.state.escalation_reason,
            "events": self.state.events,
        }
