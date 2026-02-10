"""Tests for coordination state."""

from converge.orchestration.state import (
    CoordinationState,
    CoordinationStatus,
    RepositoryConstraints,
    ResponsibilitySplit,
)


def test_coordination_state_initialization() -> None:
    """Test basic CoordinationState initialization."""
    state = CoordinationState(
        goal="Add feature X",
        repos=["api", "web"],
    )
    assert state.goal == "Add feature X"
    assert state.repos == ["api", "web"]
    assert state.status == CoordinationStatus.INITIALIZED
    assert state.round_number == 0
    assert state.max_rounds == 2
    assert len(state.constraints) == 0
    assert state.proposed_split is None
    assert len(state.decisions) == 0
    assert state.escalation_reason is None
    assert state.events == []


def test_coordination_state_update_status() -> None:
    """Test status updates."""
    state = CoordinationState(goal="Test", repos=["api"])
    original_time = state.updated_at

    state.update_status(CoordinationStatus.COLLECTING_CONSTRAINTS)

    assert state.status == CoordinationStatus.COLLECTING_CONSTRAINTS
    assert state.updated_at > original_time


def test_coordination_state_increment_round() -> None:
    """Test round incrementing."""
    state = CoordinationState(goal="Test", repos=["api"])
    assert state.round_number == 0

    state.increment_round()
    assert state.round_number == 1

    state.increment_round()
    assert state.round_number == 2


def test_coordination_state_should_escalate() -> None:
    """Test escalation logic."""
    state = CoordinationState(goal="Test", repos=["api"], max_rounds=2)

    assert not state.should_escalate()  # round 0

    state.increment_round()
    assert not state.should_escalate()  # round 1

    state.increment_round()
    assert state.should_escalate()  # round 2 (>= max_rounds)


def test_coordination_state_add_decision() -> None:
    """Test adding decisions."""
    state = CoordinationState(goal="Test", repos=["api"])

    state.add_decision("Decision 1")
    assert len(state.decisions) == 1
    assert state.decisions[0] == "Decision 1"

    state.add_decision("Decision 2")
    assert len(state.decisions) == 2


def test_repository_constraints() -> None:
    """Test RepositoryConstraints dataclass."""
    constraints = RepositoryConstraints(
        repo="api",
        constraints=["Python 3.10+", "FastAPI framework"],
        metadata={"owner": "backend-team"},
    )

    assert constraints.repo == "api"
    assert len(constraints.constraints) == 2
    assert constraints.metadata["owner"] == "backend-team"


def test_responsibility_split() -> None:
    """Test ResponsibilitySplit dataclass."""
    split = ResponsibilitySplit(
        assignments={"api": ["Handle validation"], "web": ["Display UI"]},
        rationale="Split by layer",
        risks=["Contract changes needed"],
    )

    assert len(split.assignments) == 2
    assert split.assignments["api"] == ["Handle validation"]
    assert split.rationale == "Split by layer"
    assert len(split.risks) == 1
