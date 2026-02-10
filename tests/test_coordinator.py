"""Tests for coordinator."""

from pathlib import Path

import pytest

from converge.core.config import ConvergeConfig
from converge.orchestration.coordinator import Coordinator
from converge.orchestration.state import CoordinationStatus


@pytest.fixture
def basic_config() -> ConvergeConfig:
    """Provide a basic valid configuration."""
    return ConvergeConfig(
        goal="Add discount code support",
        repos=["api", "web"],
        max_rounds=2,
        output_dir="/tmp/converge-test-output",
    )


def test_coordinator_initialization(basic_config: ConvergeConfig) -> None:
    """Test coordinator initialization."""
    coordinator = Coordinator(basic_config)

    assert coordinator.config == basic_config
    assert coordinator.state.goal == basic_config.goal
    assert coordinator.state.repos == basic_config.repos
    assert coordinator.state.status == CoordinationStatus.INITIALIZED


def test_coordinator_coordinate_flow(basic_config: ConvergeConfig) -> None:
    """Test full coordination workflow."""
    coordinator = Coordinator(basic_config)
    final_state = coordinator.coordinate()

    # Verify constraints were collected
    assert len(final_state.constraints) == 2
    assert "api" in final_state.constraints
    assert "web" in final_state.constraints

    # Verify split was proposed
    assert final_state.proposed_split is not None
    assert len(final_state.proposed_split.assignments) == 2

    # Verify convergence happened
    assert final_state.round_number >= 1
    assert len(final_state.decisions) > 0

    # Verify final status
    assert final_state.status in [
        CoordinationStatus.CONVERGED,
        CoordinationStatus.ESCALATED,
    ]


def test_coordinator_generates_artifacts(basic_config: ConvergeConfig, tmp_path: Path) -> None:
    """Test that artifacts are generated."""
    basic_config.output_dir = str(tmp_path)
    coordinator = Coordinator(basic_config)
    coordinator.coordinate()

    # Check that output directory was created
    assert tmp_path.exists()

    # Check that summary file was created
    summary_file = tmp_path / "coordination-summary.md"
    assert summary_file.exists()
    summary_content = summary_file.read_text()
    assert "Coordination Summary" in summary_content
    assert basic_config.goal in summary_content

    # Check that responsibility matrix was created
    matrix_file = tmp_path / "responsibility-matrix.md"
    assert matrix_file.exists()
    matrix_content = matrix_file.read_text()
    assert "Responsibility Matrix" in matrix_content


def test_coordinator_multiple_repos() -> None:
    """Test coordination with multiple repositories."""
    config = ConvergeConfig(
        goal="Refactor authentication",
        repos=["api", "web", "mobile", "admin"],
        output_dir="/tmp/converge-test-multi",
    )
    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    # All repos should have constraints
    assert len(final_state.constraints) == 4

    # All repos should have responsibility assignments
    assert final_state.proposed_split is not None
    assert len(final_state.proposed_split.assignments) == 4


def test_coordinator_build_summary(basic_config: ConvergeConfig) -> None:
    """Test summary building."""
    coordinator = Coordinator(basic_config)
    coordinator._collect_constraints()
    coordinator._propose_split()

    summary = coordinator._build_summary()

    assert "Coordination Summary" in summary
    assert basic_config.goal in summary
    assert "api" in summary
    assert "web" in summary
    assert "Constraints Collected" in summary
    assert "Proposed Responsibility Split" in summary


def test_coordinator_build_responsibility_matrix(basic_config: ConvergeConfig) -> None:
    """Test responsibility matrix building."""
    coordinator = Coordinator(basic_config)
    coordinator._propose_split()

    matrix = coordinator._build_responsibility_matrix()

    assert "Responsibility Matrix" in matrix
    assert basic_config.goal in matrix
    assert "api" in matrix
    assert "web" in matrix
