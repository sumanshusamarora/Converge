"""Coordination orchestration entrypoint."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from converge.core.config import ConvergeConfig
from converge.observability.opik_client import track_langgraph_app
from converge.orchestration.checkpointing import CheckpointerHandle, create_db_checkpointer
from converge.orchestration.graph import (
    build_coordinate_graph_conditional,
    build_coordinate_graph_interrupt,
)
from converge.orchestration.state import OrchestrationState

logger = logging.getLogger(__name__)


class Coordinator:
    """Orchestrates multi-repository coordination using LangGraph."""

    def __init__(
        self,
        config: ConvergeConfig,
        hitl_resolution: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> None:
        self.config = config
        self.run_dir = self._build_run_directory(config.output_dir)
        self.hitl_resolution = hitl_resolution
        self.thread_id = thread_id

        # Set CONVERGE_CODING_AGENT_EXEC_ENABLED if enable_agent_exec is True
        if config.enable_agent_exec:
            os.environ["CONVERGE_CODING_AGENT_EXEC_ENABLED"] = "true"

    def coordinate(self) -> OrchestrationState:
        """Execute the coordination workflow."""
        app, checkpointer_handle = self._build_graph_app()
        initial_state: OrchestrationState = {
            "goal": self.config.goal,
            "repos": [
                {
                    "path": repo,
                    "exists": False,
                    "repo_type": "unknown",
                    "signals": [],
                    "constraints": [],
                }
                for repo in self.config.repos
            ],
            "round": 0,
            "max_rounds": self.config.max_rounds,
            "events": [],
            "status": "FAILED",
            "proposal": {},
            "artifacts_dir": self.run_dir,
            "output_dir": self.config.output_dir,
            "model": self.config.model,
            "no_llm": self.config.no_llm,
            "human_decision": None,
            "hil_mode": self.config.hil_mode,
            "repo_plans": [],
            "contract_analysis": {},
            "agent_provider": self.config.agent_provider,
            "hitl_resolution": self.hitl_resolution,
        }
        try:
            final_state = self._invoke_graph(
                app=app,
                initial_state=initial_state,
                checkpointer_enabled=checkpointer_handle is not None,
            )
        finally:
            if checkpointer_handle is not None:
                checkpointer_handle.close()
        logger.info("Coordination complete with status: %s", final_state["status"])
        return final_state

    def _invoke_graph(
        self,
        app: Any,
        initial_state: OrchestrationState,
        checkpointer_enabled: bool,
    ) -> OrchestrationState:
        invoke_kwargs: dict[str, Any] = {}
        if checkpointer_enabled and self.thread_id:
            invoke_kwargs["config"] = {"configurable": {"thread_id": self.thread_id}}

        if self.hitl_resolution and self.config.hil_mode == "interrupt":
            if checkpointer_enabled:
                command = self._build_resume_command(self.hitl_resolution)
                if command is not None:
                    return cast(OrchestrationState, app.invoke(command, **invoke_kwargs))
            logger.warning(
                "HITL resolution provided but no checkpoint resume available; starting a fresh run"
            )

        return cast(OrchestrationState, app.invoke(initial_state, **invoke_kwargs))

    def _build_graph_app(self) -> tuple[Any, CheckpointerHandle | None]:
        checkpointer_handle: CheckpointerHandle | None = None
        if self.thread_id:
            checkpointer_handle = create_db_checkpointer(os.getenv("SQLALCHEMY_DATABASE_URI"))
            if checkpointer_handle is None and self.hitl_resolution:
                logger.warning(
                    "No DB checkpointer available for thread_id=%s; resume will be best-effort",
                    self.thread_id,
                )

        checkpointer = checkpointer_handle.checkpointer if checkpointer_handle else None
        if self.config.hil_mode == "interrupt":
            app = build_coordinate_graph_interrupt(checkpointer=checkpointer)
        else:
            app = build_coordinate_graph_conditional(checkpointer=checkpointer)
        return track_langgraph_app(app), checkpointer_handle

    @staticmethod
    def _build_resume_command(hitl_resolution: dict[str, Any]) -> Any | None:
        try:
            from langgraph.types import Command

            return Command(resume=hitl_resolution)
        except Exception:
            logger.warning(
                "LangGraph Command import failed; cannot resume from persisted checkpoint"
            )
            return None

    def _build_run_directory(self, base_output_dir: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = Path(base_output_dir) / "runs" / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
