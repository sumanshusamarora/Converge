"""Tests for core configuration."""

import pytest

from converge.core.config import ConvergeConfig


def test_converge_config_valid() -> None:
    """Test creating a valid ConvergeConfig."""
    config = ConvergeConfig(
        goal="Add discount code support",
        repos=["api", "web"],
    )
    assert config.goal == "Add discount code support"
    assert config.repos == ["api", "web"]
    assert config.max_rounds == 2
    assert config.output_dir == "./converge-output"
    assert config.log_level == "INFO"


def test_converge_config_custom_params() -> None:
    """Test ConvergeConfig with custom parameters."""
    config = ConvergeConfig(
        goal="Refactor authentication",
        repos=["backend", "frontend", "mobile"],
        max_rounds=3,
        output_dir="/tmp/output",
        log_level="DEBUG",
    )
    assert config.max_rounds == 3
    assert config.output_dir == "/tmp/output"
    assert config.log_level == "DEBUG"


def test_converge_config_empty_goal() -> None:
    """Test that empty goal raises ValueError."""
    with pytest.raises(ValueError, match="Goal cannot be empty"):
        ConvergeConfig(goal="", repos=["api"])


def test_converge_config_empty_goal_whitespace() -> None:
    """Test that whitespace-only goal raises ValueError."""
    with pytest.raises(ValueError, match="Goal cannot be empty"):
        ConvergeConfig(goal="   ", repos=["api"])


def test_converge_config_no_repos() -> None:
    """Test that empty repos list raises ValueError."""
    with pytest.raises(ValueError, match="At least one repository must be specified"):
        ConvergeConfig(goal="Some goal", repos=[])


def test_converge_config_duplicate_repos() -> None:
    """Test that duplicate repos raise ValueError."""
    with pytest.raises(ValueError, match="Repository list contains duplicates"):
        ConvergeConfig(goal="Some goal", repos=["api", "web", "api"])


def test_converge_config_invalid_max_rounds() -> None:
    """Test that invalid max_rounds raises ValueError."""
    with pytest.raises(ValueError, match="max_rounds must be at least 1"):
        ConvergeConfig(goal="Some goal", repos=["api"], max_rounds=0)


def test_converge_config_metadata() -> None:
    """Test that metadata can be added."""
    config = ConvergeConfig(
        goal="Test goal",
        repos=["api"],
        metadata={"user": "test", "session_id": "123"},
    )
    assert config.metadata["user"] == "test"
    assert config.metadata["session_id"] == "123"
