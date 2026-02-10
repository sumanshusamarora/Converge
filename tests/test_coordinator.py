"""Tests for coordinator."""

import json
from pathlib import Path

import pytest

from converge.core.config import ConvergeConfig
from converge.orchestration.coordinator import Coordinator
from converge.orchestration.state import CoordinationStatus


@pytest.fixture
def basic_config(tmp_path: Path) -> ConvergeConfig:
    """Provide a basic valid configuration."""
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
    )


def test_coordinator_initialization(basic_config: ConvergeConfig) -> None:
    """Test coordinator initialization."""
    coordinator = Coordinator(basic_config)

    assert coordinator.config == basic_config
    assert coordinator.state.goal == basic_config.goal
    assert coordinator.state.repos == basic_config.repos
    assert coordinator.state.status == CoordinationStatus.INITIALIZED
    assert coordinator.run_dir.parent.name == "runs"


def test_coordinator_coordinate_flow(basic_config: ConvergeConfig) -> None:
    """Test full coordination workflow."""
    coordinator = Coordinator(basic_config)
    final_state = coordinator.coordinate()

    assert len(final_state.constraints) == 2
    assert final_state.proposed_split is not None
    assert len(final_state.proposed_split.assignments) == 2
    assert final_state.round_number >= 1
    assert len(final_state.decisions) > 0
    assert final_state.status == CoordinationStatus.CONVERGED


def test_coordinator_generates_run_scoped_artifacts(basic_config: ConvergeConfig) -> None:
    """Test that run-scoped artifacts are generated under runs/<timestamp>."""
    coordinator = Coordinator(basic_config)
    coordinator.coordinate()

    run_dir = coordinator.run_dir
    assert run_dir.exists()
    assert run_dir.parent.name == "runs"
    assert run_dir.parent.parent == Path(basic_config.output_dir)

    summary_file = run_dir / "summary.md"
    assert summary_file.exists()
    assert "Coordination Summary" in summary_file.read_text(encoding="utf-8")

    matrix_file = run_dir / "responsibility-matrix.md"
    assert matrix_file.exists()
    assert "Responsibility Matrix" in matrix_file.read_text(encoding="utf-8")

    constraints_file = run_dir / "constraints.json"
    assert constraints_file.exists()

    run_file = run_dir / "run.json"
    assert run_file.exists()
    run_payload = json.loads(run_file.read_text(encoding="utf-8"))
    actions = [event["action"] for event in run_payload["events"]]
    assert "collect_constraints" in actions
    assert "propose_split" in actions
    assert "round" in actions
    assert "write_artifact" in actions


def test_coordinator_missing_repo_path_escalates(tmp_path: Path) -> None:
    """Test missing repository path triggers escalation."""
    existing_repo = tmp_path / "existing"
    existing_repo.mkdir()

    config = ConvergeConfig(
        goal="Handle missing repo",
        repos=[str(existing_repo), str(tmp_path / "missing")],
        output_dir=str(tmp_path / ".converge"),
    )

    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    assert final_state.status == CoordinationStatus.ESCALATED
    assert (
        final_state.escalation_reason == "Maximum convergence rounds reached without full agreement"
    )
    missing_constraints = final_state.constraints[str(tmp_path / "missing")].constraints
    assert "repo path not found" in missing_constraints


def test_coordinator_build_summary(basic_config: ConvergeConfig) -> None:
    """Test summary building."""
    coordinator = Coordinator(basic_config)
    coordinator._collect_constraints()
    coordinator._propose_split()

    summary = coordinator._build_summary()

    assert "Coordination Summary" in summary
    assert basic_config.goal in summary
    assert "Constraints Collected" in summary
    assert "Proposed Responsibility Split" in summary


def test_coordinator_build_responsibility_matrix(basic_config: ConvergeConfig) -> None:
    """Test responsibility matrix building."""
    coordinator = Coordinator(basic_config)
    coordinator._collect_constraints()
    coordinator._propose_split()

    matrix = coordinator._build_responsibility_matrix()

    assert "Responsibility Matrix" in matrix
    assert basic_config.goal in matrix
