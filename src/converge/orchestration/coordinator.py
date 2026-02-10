"""Coordination orchestration entrypoint."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from converge.core.config import ConvergeConfig
from converge.orchestration.graph import (
    build_coordinate_graph_conditional,
    build_coordinate_graph_interrupt,
)
from converge.orchestration.state import OrchestrationState

logger = logging.getLogger(__name__)


class Coordinator:
    """Orchestrates multi-repository coordination using LangGraph."""

    def __init__(self, config: ConvergeConfig) -> None:
        self.config = config
        self.run_dir = self._build_run_directory(config.output_dir)

    def coordinate(self) -> OrchestrationState:
        """Execute the coordination workflow."""
        app = self._build_graph_app()
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
        }
        final_state = cast(OrchestrationState, app.invoke(initial_state))
        logger.info("Coordination complete with status: %s", final_state["status"])
        return final_state

    def _build_graph_app(self) -> Any:
        if self.config.hil_mode == "interrupt":
            return build_coordinate_graph_interrupt()
        return build_coordinate_graph_conditional()

    def _build_run_directory(self, base_output_dir: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = Path(base_output_dir) / "runs" / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
