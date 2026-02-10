"""Smoke tests for package sanity."""

import pytest

from converge import __version__
from converge.cli.main import main


def test_version_is_defined() -> None:
    """Package exposes a version string."""
    assert isinstance(__version__, str)
    assert __version__


def test_cli_help_returns_success() -> None:
    """CLI help path exits successfully."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
