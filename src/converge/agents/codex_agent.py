"""Codex CLI agent adapter for Converge.

This adapter uses OpenAI Codex (via OPENAI_API_KEY) to generate
planning proposals. Execution via Codex CLI is disabled by default
and requires explicit opt-in via CONVERGE_CODEX_ENABLED and execution policy.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

from converge.agents.base import AgentProvider, AgentResult, AgentTask, CodingAgent
from converge.agents.policy import ExecutionMode

logger = logging.getLogger(__name__)


class CodexAgent(CodingAgent):
    """Codex-based planning agent.

    By default, CodexAgent produces planning prompts and heuristic
    proposals without executing Codex CLI. Set CONVERGE_CODEX_ENABLED=true
    to enable Codex CLI execution (requires OPENAI_API_KEY).
    """

    def __init__(self) -> None:
        """Initialize CodexAgent."""
        self._codex_enabled = os.getenv("CONVERGE_CODEX_ENABLED", "false").lower() == "true"
        logger.info("CodexAgent initialized (codex_enabled=%s)", self._codex_enabled)

    @property
    def provider(self) -> AgentProvider:
        """Return CODEX provider identifier."""
        return AgentProvider.CODEX

    def supports_execution(self) -> bool:
        """Return True (Codex can execute tools when enabled)."""
        return True

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute changes for the given task.

        This method enforces the execution policy and performs safety checks:
        - Verify policy allows execution
        - Check repository exists and has .git directory
        - If create_branch: create new branch with prefix
        - If require_git_clean: ensure working directory is clean
        - Only execute allowlisted commands

        Args:
            task: The task to execute

        Returns:
            AgentResult with execution outcome
        """
        # Check if we have an execution policy
        if task.execution_policy is None:
            return AgentResult(
                provider=self.provider,
                status="FAILED",
                summary="No execution policy provided",
                proposed_changes=[],
                questions_for_hitl=["Task requires execution_policy to execute"],
                raw={"error": "no_execution_policy"},
            )

        policy = task.execution_policy

        # Check if execution is allowed by policy
        if policy.mode != ExecutionMode.EXECUTE_ALLOWED:
            return AgentResult(
                provider=self.provider,
                status="HITL_REQUIRED",
                summary="Execution not allowed by policy",
                proposed_changes=[],
                questions_for_hitl=[
                    f"Execution policy mode is {policy.mode.value}",
                    "To enable execution: set CONVERGE_CODEX_ENABLED=true and --allow-exec flag",
                ],
                raw={"policy_mode": policy.mode.value},
            )

        # Perform repository safety checks
        repo_path = Path(task.repo.path)
        if not repo_path.exists():
            return AgentResult(
                provider=self.provider,
                status="FAILED",
                summary=f"Repository path does not exist: {repo_path}",
                proposed_changes=[],
                questions_for_hitl=[f"Repository not found at {repo_path}"],
                raw={"error": "repo_not_found", "path": str(repo_path)},
            )

        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return AgentResult(
                provider=self.provider,
                status="FAILED",
                summary=f"Not a git repository: {repo_path}",
                proposed_changes=[],
                questions_for_hitl=[f"No .git directory found at {repo_path}"],
                raw={"error": "not_git_repo", "path": str(repo_path)},
            )

        # Check if working directory is clean (if required)
        if policy.require_git_clean:
            clean_check = self._check_git_clean(repo_path)
            if not clean_check["clean"]:
                return AgentResult(
                    provider=self.provider,
                    status="FAILED",
                    summary="Working directory is not clean",
                    proposed_changes=[],
                    questions_for_hitl=[
                        "Policy requires clean git working directory",
                        f"Uncommitted changes: {clean_check.get('details', 'unknown')}",
                    ],
                    raw={"error": "git_not_clean", "details": clean_check},
                )

        # Create new branch if requested
        branch_created = None
        if policy.create_branch:
            branch_result = self._create_branch(repo_path, policy.branch_prefix)
            if not branch_result["success"]:
                return AgentResult(
                    provider=self.provider,
                    status="FAILED",
                    summary="Failed to create branch",
                    proposed_changes=[],
                    questions_for_hitl=[
                        f"Could not create branch: {branch_result.get('error', 'unknown')}"
                    ],
                    raw={"error": "branch_creation_failed", "details": branch_result},
                )
            branch_created = branch_result["branch_name"]
            logger.info("Created branch: %s", branch_created)

        # At this point, we would execute Codex CLI or run commands
        # For now, return a placeholder indicating execution is not yet implemented
        logger.warning("Codex CLI execution not yet fully implemented")

        return AgentResult(
            provider=self.provider,
            status="HITL_REQUIRED",
            summary="Execution passed safety checks but Codex CLI not yet implemented",
            proposed_changes=[
                "Safety checks passed",
                f"Repository verified at {repo_path}",
                f"Branch created: {branch_created}" if branch_created else "No branch created",
            ],
            questions_for_hitl=[
                "Codex CLI execution interface not yet implemented",
                "Future iterations will invoke Codex CLI with tool use",
            ],
            raw={
                "safety_checks_passed": True,
                "repo_path": str(repo_path),
                "branch_created": branch_created,
                "policy": {
                    "mode": policy.mode.value,
                    "create_branch": policy.create_branch,
                    "require_git_clean": policy.require_git_clean,
                },
            },
        )

    def _check_git_clean(self, repo_path: Path) -> dict[str, object]:
        """Check if git working directory is clean.

        Args:
            repo_path: Path to repository

        Returns:
            Dict with 'clean' boolean and optional 'details'
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout.strip()
            return {
                "clean": len(output) == 0,
                "details": output if output else None,
            }
        except subprocess.CalledProcessError as e:
            logger.error("Failed to check git status: %s", e)
            return {"clean": False, "details": f"Error: {e}"}

    def _create_branch(self, repo_path: Path, branch_prefix: str) -> dict[str, object]:
        """Create a new git branch with timestamp.

        Args:
            repo_path: Path to repository
            branch_prefix: Prefix for branch name

        Returns:
            Dict with 'success' boolean, 'branch_name', and optional 'error'
        """
        try:
            # Generate branch name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"{branch_prefix}{timestamp}"

            # Create and checkout new branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            return {"success": True, "branch_name": branch_name}
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create branch: %s", e)
            return {
                "success": False,
                "error": str(e),
                "stderr": e.stderr if hasattr(e, "stderr") else None,
            }

    def plan(self, task: AgentTask) -> AgentResult:
        """Generate a plan using Codex prompt or heuristic.

        If CONVERGE_CODEX_ENABLED=true, this would call Codex CLI
        in SUGGEST-only mode. For Iteration 4, we produce a heuristic
        plan and save the prompt artifact.

        Args:
            task: The planning task with goal, repo, and instructions

        Returns:
            AgentResult with status, summary, and proposed changes
        """
        prompt = self._build_codex_prompt(task)
        prompt_metadata = {
            "prompt_length": len(prompt),
            "repo_path": str(task.repo.path),
            "repo_kind": task.repo.kind,
            "signals": task.repo.signals,
        }

        logger.info(
            "codex_plan_built: prompt_length=%d, repo=%s",
            prompt_metadata["prompt_length"],
            task.repo.path,
        )

        if self._codex_enabled:
            # In future iterations, call Codex CLI executor here
            # For now: log that execution is not yet implemented
            logger.warning("Codex CLI execution not yet implemented; using heuristic plan")
            return self._heuristic_plan(task, prompt, prompt_metadata)
        else:
            return self._heuristic_plan(task, prompt, prompt_metadata)

    def _build_codex_prompt(self, task: AgentTask) -> str:
        """Build a structured prompt for Codex CLI.

        Args:
            task: The planning task

        Returns:
            Formatted prompt string
        """
        readme_section = ""
        if task.repo.readme_excerpt:
            readme_section = f"\n## Repository Context\n{task.repo.readme_excerpt}\n"

        signals_section = ""
        if task.repo.signals:
            signals_section = f"\n## Detected Signals\n{', '.join(task.repo.signals)}\n"

        prompt = f"""# Codex Planning Task

## Goal
{task.goal}

## Repository
Path: {task.repo.path}
Kind: {task.repo.kind or "unknown"}
{signals_section}{readme_section}
## Instructions
{task.instructions}

## Task
Analyze the repository and propose a plan to achieve the goal.
List high-level changes needed (no code diffs required).
Identify any risks or questions requiring human judgment.
"""
        return prompt

    def _heuristic_plan(
        self, task: AgentTask, prompt: str, prompt_metadata: dict[str, object]
    ) -> AgentResult:
        """Generate a heuristic plan when Codex execution is disabled.

        Args:
            task: The planning task
            prompt: The built Codex prompt
            prompt_metadata: Metadata about the prompt

        Returns:
            AgentResult with heuristic proposal
        """
        # Heuristic logic based on repo signals
        proposed_changes = []
        questions = []

        if "pyproject.toml" in task.repo.signals or "requirements.txt" in task.repo.signals:
            proposed_changes.append("Update Python dependencies if needed for goal")
            proposed_changes.append("Add or modify Python modules to implement feature")
            proposed_changes.append("Update tests for new/modified functionality")
        elif "package.json" in task.repo.signals:
            proposed_changes.append("Update Node.js dependencies if needed")
            proposed_changes.append("Add or modify JavaScript/TypeScript modules")
            proposed_changes.append("Update tests for new/modified functionality")
        else:
            proposed_changes.append("Review repository structure and add necessary files")
            # Only mark as question if we truly can't determine type
            if not task.repo.signals:
                questions.append("Repository type unclear; manual analysis required")

        if not Path(task.repo.path).exists():
            questions.append(f"Repository path {task.repo.path} not found; cannot analyze")

        # README missing is informational, not a blocker for heuristic planning
        # (only mark as HITL_REQUIRED if we have real blockers)
        status: Literal["OK", "HITL_REQUIRED", "FAILED"] = "HITL_REQUIRED" if questions else "OK"

        summary = f"Heuristic plan for {task.repo.kind or 'unknown'} repository at {task.repo.path}"

        raw_data: dict[str, object] = {
            "codex_prompt": prompt,
            "prompt_metadata": prompt_metadata,
            "execution_mode": "heuristic",
            "codex_enabled": self._codex_enabled,
            "signals": task.repo.signals,
        }

        return AgentResult(
            provider=self.provider,
            status=status,
            summary=summary,
            proposed_changes=proposed_changes,
            questions_for_hitl=questions,
            raw=raw_data,
        )
