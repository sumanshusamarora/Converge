"""Tests for environment loading."""

from pathlib import Path

from converge.core.env import load_environment


def test_load_environment_missing_file_is_safe(tmp_path: Path) -> None:
    missing_env = tmp_path / ".env.missing"
    load_environment(str(missing_env))
    assert not missing_env.exists()
