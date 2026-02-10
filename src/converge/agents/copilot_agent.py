"""GitHub Copilot agent adapter for Converge.

This adapter generates structured prompt packs for GitHub Copilot.
It does not integrate with any Copilot API (no stable API exists).
Instead, it produces human-readable prompts and proposals.
"""

import logging
from pathlib import Path

from converge.agents.base import AgentProvider, AgentResult, AgentTask, CodingAgent

logger = logging.getLogger(__name__)


class GitHubCopilotAgent(CodingAgent):
    """GitHub Copilot prompt pack generator.

    This adapter produces structured prompts and proposals
    for GitHub Copilot without requiring API integration.
    """

    @property
    def provider(self) -> AgentProvider:
        """Return COPILOT provider identifier."""
        return AgentProvider.COPILOT

    def supports_execution(self) -> bool:
        """Return False (Copilot adapter is planning-only for now)."""
        return False

    def plan(self, task: AgentTask) -> AgentResult:
        """Generate a Copilot prompt pack and planning proposal.

        Args:
            task: The planning task with goal, repo, and instructions

        Returns:
            AgentResult with Copilot prompt and proposed changes
        """
        prompt = self._build_copilot_prompt(task)
        proposed_changes = self._generate_proposed_changes(task)
        questions = self._generate_questions(task)

        summary = (
            f"Copilot prompt pack for {task.repo.kind or 'repository'} "
            f"at {task.repo.path}: {task.goal}"
        )

        # If we have questions, mark as HITL_REQUIRED
        status: AgentResult["status"] = "HITL_REQUIRED" if questions else "OK"

        raw_data: dict[str, object] = {
            "copilot_prompt": prompt,
            "prompt_length": len(prompt),
            "repo_path": str(task.repo.path),
            "repo_kind": task.repo.kind,
        }

        logger.info(
            "copilot_prompt_built: length=%d, repo=%s",
            len(prompt),
            task.repo.path,
        )

        return AgentResult(
            provider=self.provider,
            status=status,
            summary=summary,
            proposed_changes=proposed_changes,
            questions_for_hitl=questions,
            raw=raw_data,
        )

    def _build_copilot_prompt(self, task: AgentTask) -> str:
        """Build a structured prompt for GitHub Copilot.

        Args:
            task: The planning task

        Returns:
            Formatted Copilot prompt string
        """
        readme_section = ""
        if task.repo.readme_excerpt:
            readme_section = f"\n## Repository Context\n{task.repo.readme_excerpt}\n"

        signals_section = ""
        if task.repo.signals:
            signals_list = "\n".join(f"- {signal}" for signal in task.repo.signals)
            signals_section = f"\n## Technology Signals\n{signals_list}\n"

        prompt = f"""# GitHub Copilot Task

## Goal
{task.goal}

## Repository Information
- Path: {task.repo.path}
- Type: {task.repo.kind or "unknown"}
{signals_section}{readme_section}
## Project Rules and Constraints
{task.instructions}

## Task Description
Please analyze this repository and propose changes to achieve the goal.
Focus on:
1. Identifying the files that need to be modified or created
2. Listing high-level changes (no full implementations required)
3. Highlighting any risks or architectural decisions
4. Raising questions that require human judgment

Keep proposals minimal and surgical. Prefer existing patterns.
"""
        return prompt

    def _generate_proposed_changes(self, task: AgentTask) -> list[str]:
        """Generate proposed changes based on repository signals.

        Args:
            task: The planning task

        Returns:
            List of proposed change descriptions
        """
        changes = []

        # Heuristic based on signals
        if "pyproject.toml" in task.repo.signals or "requirements.txt" in task.repo.signals:
            changes.append("Review and update Python modules as needed")
            changes.append("Add tests for new Python functionality")
        elif "package.json" in task.repo.signals:
            changes.append("Review and update TypeScript/JavaScript modules")
            changes.append("Add tests for new features")
        else:
            changes.append("Analyze repository structure and identify change locations")

        # Generic changes
        changes.append("Update documentation if interfaces change")

        return changes

    def _generate_questions(self, task: AgentTask) -> list[str]:
        """Generate HITL questions based on task analysis.

        Args:
            task: The planning task

        Returns:
            List of questions requiring human judgment
        """
        questions = []

        if not Path(task.repo.path).exists():
            questions.append(f"Repository at {task.repo.path} does not exist")

        if not task.repo.signals:
            questions.append("No technology signals detected; manual inspection needed")

        if not task.repo.kind:
            questions.append("Repository type unknown; classify as backend/frontend/service/docs")

        return questions
