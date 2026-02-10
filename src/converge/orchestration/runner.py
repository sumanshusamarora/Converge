"""Reusable runner for Converge coordination workflows."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, Field

from converge.core.config import ConvergeConfig
from converge.orchestration.coordinator import Coordinator

RunStatus = Literal["CONVERGED", "HITL_REQUIRED", "FAILED"]


class RunOutcome(BaseModel):
    """Final outcome for a single coordinate workflow invocation."""

    status: RunStatus
    summary: str
    artifacts_dir: str
    hitl_questions: list[str] = Field(default_factory=list)


def run_coordinate(
    goal: str,
    repos: list[str],
    max_rounds: int,
    agent_provider: str | None,
    base_output_dir: Path | None,
) -> RunOutcome:
    """Execute the coordinate workflow and return a normalized outcome."""
    final_agent_provider = agent_provider or os.getenv("CONVERGE_AGENT_PROVIDER", "codex")
    no_llm = os.getenv("CONVERGE_NO_LLM", "false").lower() == "true"
    hil_mode = cast(
        Literal["conditional", "interrupt"],
        os.getenv("CONVERGE_HIL_MODE", "conditional").lower(),
    )
    enable_codex_exec = os.getenv("CONVERGE_CODEX_ENABLED", "false").lower() == "true"

    config = ConvergeConfig(
        goal=goal,
        repos=repos,
        max_rounds=max_rounds,
        output_dir=str(base_output_dir) if base_output_dir else ".converge",
        log_level=os.getenv("CONVERGE_LOG_LEVEL", "INFO"),
        model=os.getenv("CONVERGE_OPENAI_MODEL") or None,
        no_llm=no_llm,
        hil_mode=hil_mode,
        agent_provider=cast(str, final_agent_provider),
        enable_codex_exec=enable_codex_exec,
    )

    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    hitl_questions: list[str] = []
    for repo_plan in final_state.get("repo_plans", []):
        hitl_questions.extend(repo_plan.get("questions_for_hitl", []))

    summary = (
        f"Goal '{goal}' finished with status {final_state['status']} "
        f"after {final_state['round']} rounds"
    )

    return RunOutcome(
        status=final_state["status"],
        summary=summary,
        artifacts_dir=str(coordinator.run_dir),
        hitl_questions=hitl_questions,
    )
