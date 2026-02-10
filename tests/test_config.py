"""Tests for core configuration."""

import pytest

from converge.core.config import ConvergeConfig


def test_converge_config_valid() -> None:
    config = ConvergeConfig(
        goal="Add discount code support",
        repos=["api", "web"],
    )
    assert config.goal == "Add discount code support"
    assert config.repos == ["api", "web"]
    assert config.max_rounds == 2
    assert config.output_dir == ".converge"
    assert config.log_level == "INFO"
    assert config.model is None
    assert config.no_llm is False
    assert config.hil_mode == "conditional"


def test_converge_config_custom_params() -> None:
    config = ConvergeConfig(
        goal="Refactor authentication",
        repos=["backend", "frontend", "mobile"],
        max_rounds=3,
        output_dir="/tmp/output",
        log_level="DEBUG",
        model="gpt-4o-mini",
        no_llm=True,
        hil_mode="interrupt",
    )
    assert config.max_rounds == 3
    assert config.output_dir == "/tmp/output"
    assert config.log_level == "DEBUG"
    assert config.model == "gpt-4o-mini"
    assert config.no_llm is True
    assert config.hil_mode == "interrupt"


def test_converge_config_empty_goal() -> None:
    with pytest.raises(ValueError, match="Goal cannot be empty"):
        ConvergeConfig(goal="", repos=["api"])


def test_converge_config_no_repos() -> None:
    with pytest.raises(ValueError, match="At least one repository must be specified"):
        ConvergeConfig(goal="Some goal", repos=[])


def test_converge_config_invalid_hil_mode() -> None:
    with pytest.raises(ValueError, match="hil_mode must be either 'conditional' or 'interrupt'"):
        ConvergeConfig(goal="Some goal", repos=["api"], hil_mode="invalid")  # type: ignore[arg-type]
