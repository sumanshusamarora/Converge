"""Tests for coordinator and LangGraph workflow."""

import json
from pathlib import Path

import pytest

from converge.core.config import ConvergeConfig
from converge.orchestration.coordinator import Coordinator


@pytest.fixture
def basic_config(tmp_path: Path) -> ConvergeConfig:
    api_dir = tmp_path / "api"
    web_dir = tmp_path / "web"
    api_dir.mkdir()
    web_dir.mkdir()
    (api_dir / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")
    (web_dir / "package.json").write_text('{"name": "web"}', encoding="utf-8")

    return ConvergeConfig(
        goal="Add discount code support",
        repos=[str(api_dir), str(web_dir)],
        max_rounds=2,
        output_dir=str(tmp_path / ".converge"),
        no_llm=True,
    )


def test_coordinator_coordinate_flow_generates_artifacts(basic_config: ConvergeConfig) -> None:
    coordinator = Coordinator(basic_config)
    final_state = coordinator.coordinate()

    assert final_state["status"] == "CONVERGED"
    assert final_state["round"] == 1
    assert any(event["node"] == "collect_constraints_node" for event in final_state["events"])

    run_dir = coordinator.run_dir
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "responsibility-matrix.md").exists()
    assert (run_dir / "constraints.json").exists()
    assert (run_dir / "run.json").exists()

    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "CONVERGED"


def test_coordinator_missing_repo_path_requires_hitl(tmp_path: Path) -> None:
    existing_repo = tmp_path / "existing"
    existing_repo.mkdir()

    config = ConvergeConfig(
        goal="Handle missing repo",
        repos=[str(existing_repo), str(tmp_path / "missing")],
        output_dir=str(tmp_path / ".converge"),
        no_llm=True,
    )

    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    assert final_state["status"] == "HITL_REQUIRED"
