"""Codex CLI agent adapter for Converge.

This adapter uses OpenAI Codex (via OPENAI_API_KEY) to generate
planning proposals. Execution via Codex CLI is disabled by default
and requires explicit opt-in via CONVERGE_CODEX_ENABLED.
"""

import logging
import os
from pathlib import Path
from typing import Literal

from converge.agents.base import AgentProvider, AgentResult, AgentTask, CodingAgent

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
        }

        return AgentResult(
            provider=self.provider,
            status=status,
            summary=summary,
            proposed_changes=proposed_changes,
            questions_for_hitl=questions,
            raw=raw_data,
        )
