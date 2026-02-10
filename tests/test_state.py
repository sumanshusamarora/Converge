"""Tests for typed orchestration state structures."""

from pathlib import Path

from converge.orchestration.state import OrchestrationState


def test_orchestration_state_shape() -> None:
    state: OrchestrationState = {
        "goal": "Add feature X",
        "repos": [
            {
                "path": "api",
                "exists": True,
                "repo_type": "python",
                "signals": ["pyproject.toml"],
                "constraints": ["Python project detected"],
            }
        ],
        "round": 0,
        "max_rounds": 2,
        "events": [],
        "status": "FAILED",
        "proposal": {},
        "artifacts_dir": Path(".converge/runs/test"),
        "output_dir": ".converge",
        "model": None,
        "no_llm": False,
    }

    assert state["goal"] == "Add feature X"
    assert state["repos"][0]["repo_type"] == "python"
