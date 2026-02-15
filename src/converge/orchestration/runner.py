"""Reusable runner for Converge coordination workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, cast

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
    hitl_resolution: dict[str, Any] | None = None,
    thread_id: str | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    project_preferences: dict[str, Any] | None = None,
    project_instructions: str | None = None,
    custom_instructions: str | None = None,
    execute_immediately: bool = False,
) -> RunOutcome:
    """Execute the coordinate workflow and return a normalized outcome."""
    final_agent_provider = agent_provider or os.getenv("CONVERGE_CODING_AGENT", "codex")
    no_llm = os.getenv("CONVERGE_NO_LLM", "false").lower() == "true"
    hil_mode = cast(
        Literal["conditional", "interrupt"],
        os.getenv("CONVERGE_HIL_MODE", "conditional").lower(),
    )
    enable_agent_exec = (
        os.getenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", "false").lower() == "true"
    )

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
        enable_agent_exec=enable_agent_exec,
        project_id=project_id,
        project_name=project_name,
        project_preferences=project_preferences or {},
        project_instructions=project_instructions,
        custom_instructions=custom_instructions,
        execute_immediately=execute_immediately,
    )

    coordinator = Coordinator(
        config, hitl_resolution=hitl_resolution, thread_id=thread_id
    )
    final_state = coordinator.coordinate()

    hitl_questions: list[str] = []
    for repo_plan in final_state.get("repo_plans", []):
        hitl_questions.extend(repo_plan.get("questions_for_hitl", []))

    interrupts = cast(list[Any], final_state.get("__interrupt__", []))
    for interrupt in interrupts:
        payload = getattr(interrupt, "value", interrupt)
        if isinstance(payload, dict):
            hitl_questions.append(json.dumps(payload, sort_keys=True))
        else:
            hitl_questions.append(str(payload))

    final_status = cast(RunStatus, final_state["status"])
    if interrupts and final_status != "FAILED":
        final_status = "HITL_REQUIRED"

    summary = (
        f"Goal '{goal}' finished with status {final_status} "
        f"after {final_state['round']} rounds"
    )
    artifacts_dir = str(final_state.get("artifacts_dir", coordinator.run_dir))

    return RunOutcome(
        status=final_status,
        summary=summary,
        artifacts_dir=artifacts_dir,
        hitl_questions=hitl_questions,
    )
