"""Tests for coordinator and dual graph workflows."""

import json
from pathlib import Path

import pytest

from converge.core.config import ConvergeConfig
from converge.orchestration.coordinator import Coordinator
from converge.orchestration.graph import (
    build_coordinate_graph_conditional,
    build_coordinate_graph_interrupt,
)
from converge.orchestration.state import OrchestrationState


@pytest.fixture
def repo_paths(tmp_path: Path) -> tuple[Path, Path]:
    api_dir = tmp_path / "api"
    web_dir = tmp_path / "web"
    api_dir.mkdir()
    web_dir.mkdir()
    (api_dir / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")
    (web_dir / "package.json").write_text('{"name": "web"}', encoding="utf-8")
    return api_dir, web_dir


def test_conditional_graph_converges_and_writes_artifacts(
    repo_paths: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    api_dir, web_dir = repo_paths
    config = ConvergeConfig(
        goal="Add discount code support",
        repos=[str(api_dir), str(web_dir)],
        max_rounds=2,
        output_dir=str(tmp_path / ".converge"),
        no_llm=True,
        hil_mode="conditional",
    )

    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    assert final_state["status"] == "CONVERGED"
    assert final_state["round"] == 1
    run_dir = coordinator.run_dir
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "responsibility-matrix.md").exists()
    assert (run_dir / "constraints.json").exists()
    assert (run_dir / "run.json").exists()


def test_conditional_graph_loops_until_max_rounds_and_hits_hitl(tmp_path: Path) -> None:
    existing_repo = tmp_path / "existing"
    existing_repo.mkdir()
    artifacts_dir = tmp_path / "artifacts"

    app = build_coordinate_graph_conditional()
    initial_state: OrchestrationState = {
        "goal": "Handle missing repo",
        "repos": [
            {
                "path": str(existing_repo),
                "exists": False,
                "repo_type": "unknown",
                "signals": [],
                "constraints": [],
            },
            {
                "path": str(tmp_path / "missing"),
                "exists": False,
                "repo_type": "unknown",
                "signals": [],
                "constraints": [],
            },
        ],
        "round": 0,
        "max_rounds": 3,
        "events": [],
        "status": "FAILED",
        "proposal": {},
        "artifacts_dir": artifacts_dir,
        "output_dir": str(tmp_path),
        "model": None,
        "no_llm": True,
        "human_decision": None,
        "hil_mode": "conditional",
    }

    final_state = app.invoke(initial_state)

    assert final_state["status"] == "HITL_REQUIRED"
    assert final_state["round"] == 3
    propose_events = [e for e in final_state["events"] if e["node"] == "propose_split_node"]
    decide_events = [e for e in final_state["events"] if e["node"] == "decide_node"]
    assert len(propose_events) == 3
    assert len(decide_events) == 3
    run_payload = json.loads((artifacts_dir / "run.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "HITL_REQUIRED"


def test_interrupt_graph_hitl_path_records_human_decision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    existing_repo = tmp_path / "existing"
    existing_repo.mkdir()
    artifacts_dir = tmp_path / "artifacts"

    from converge.orchestration import graph as graph_module

    monkeypatch.setattr(
        graph_module,
        "interrupt",
        lambda payload: {
            "human_decision": {"action": "request_changes", "payload": payload["goal"]}
        },
    )

    app = build_coordinate_graph_interrupt()
    initial_state: OrchestrationState = {
        "goal": "Needs HITL",
        "repos": [
            {
                "path": str(existing_repo),
                "exists": False,
                "repo_type": "unknown",
                "signals": [],
                "constraints": [],
            },
            {
                "path": str(tmp_path / "missing"),
                "exists": False,
                "repo_type": "unknown",
                "signals": [],
                "constraints": [],
            },
        ],
        "round": 0,
        "max_rounds": 2,
        "events": [],
        "status": "FAILED",
        "proposal": {},
        "artifacts_dir": artifacts_dir,
        "output_dir": str(tmp_path),
        "model": None,
        "no_llm": True,
        "human_decision": None,
        "hil_mode": "interrupt",
    }

    final_state = app.invoke(initial_state)
    assert final_state["status"] == "HITL_REQUIRED"
    assert final_state["human_decision"] == {
        "action": "request_changes",
        "payload": "Needs HITL",
    }
    event_nodes = [event["node"] for event in final_state["events"]]
    assert "hitl_interrupt_node" in event_nodes
    assert "hitl_decision_received" in event_nodes
    assert (artifacts_dir / "run.json").exists()


def test_interrupt_graph_converged_skips_hitl_node(
    repo_paths: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    api_dir, web_dir = repo_paths
    config = ConvergeConfig(
        goal="Converged path",
        repos=[str(api_dir), str(web_dir)],
        output_dir=str(tmp_path / ".converge"),
        no_llm=True,
        hil_mode="interrupt",
    )

    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    assert final_state["status"] == "CONVERGED"
    event_nodes = [event["node"] for event in final_state["events"]]
    assert "hitl_interrupt_node" not in event_nodes


def test_handoff_pack_structure_created(
    repo_paths: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Test that handoff pack artifacts are created in repo-plans/ directory."""
    api_dir, web_dir = repo_paths
    config = ConvergeConfig(
        goal="Add discount code support",
        repos=[str(api_dir), str(web_dir)],
        output_dir=str(tmp_path / ".converge"),
        no_llm=True,
        hil_mode="conditional",
        agent_provider="copilot",
    )

    coordinator = Coordinator(config)
    _ = coordinator.coordinate()

    run_dir = coordinator.run_dir
    repo_plans_dir = run_dir / "repo-plans"

    # Check repo-plans directory exists
    assert repo_plans_dir.exists()

    # Check per-repo directories exist
    api_plan_dir = repo_plans_dir / "api"
    web_plan_dir = repo_plans_dir / "web"
    assert api_plan_dir.exists()
    assert web_plan_dir.exists()

    # Check required files exist in each repo plan
    for plan_dir in [api_plan_dir, web_plan_dir]:
        assert (plan_dir / "plan.md").exists()
        assert (plan_dir / "copilot-prompt.txt").exists()
        assert (plan_dir / "commands.sh").exists()

    # Verify content of plan.md
    api_plan_md = (api_plan_dir / "plan.md").read_text()
    assert "Add discount code support" in api_plan_md
    assert "copilot" in api_plan_md.lower()

    # Verify copilot-prompt.txt has content
    api_prompt = (api_plan_dir / "copilot-prompt.txt").read_text()
    assert len(api_prompt) > 0
    assert "Add discount code support" in api_prompt or "Copilot" in api_prompt

    # Verify commands.sh has shell commands
    api_commands = (api_plan_dir / "commands.sh").read_text()
    assert "#!/bin/bash" in api_commands
    assert "pytest" in api_commands or "npm" in api_commands  # Python or Node commands
