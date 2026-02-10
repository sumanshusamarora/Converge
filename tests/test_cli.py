"""Tests for CLI."""

from pathlib import Path

from click.testing import CliRunner

from converge.cli.main import cli


def test_cli_help() -> None:
    """Test CLI help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Converge: Multi-repository coordination" in result.output


def test_cli_version() -> None:
    """Test CLI version output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_coordinate_command_help() -> None:
    """Test coordinate command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["coordinate", "--help"])

    assert result.exit_code == 0
    assert "Coordinate changes across multiple repositories" in result.output
    assert "--goal" in result.output
    assert "--repos" in result.output


def test_coordinate_command_missing_goal() -> None:
    """Test coordinate command without goal."""
    runner = CliRunner()
    result = runner.invoke(cli, ["coordinate", "--repos", "api"])

    assert result.exit_code != 0
    assert "Missing option '--goal'" in result.output


def test_coordinate_command_missing_repos() -> None:
    """Test coordinate command without repos."""
    runner = CliRunner()
    result = runner.invoke(cli, ["coordinate", "--goal", "Test goal"])

    assert result.exit_code != 0
    assert "Missing option '--repos'" in result.output


def test_coordinate_command_basic(tmp_path: Path) -> None:
    """Test basic coordinate command execution."""
    runner = CliRunner()
    output_dir = tmp_path

    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Add discount code support",
            "--repos",
            "api",
            "--repos",
            "web",
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",  # Suppress logs in test
        ],
    )

    assert result.exit_code in [0, 2]  # 0 = converged, 2 = escalated


def test_coordinate_command_single_repo(tmp_path: Path) -> None:
    """Test coordinate with single repository."""
    runner = CliRunner()
    output_dir = tmp_path

    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Update API",
            "--repos",
            "backend",
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",
        ],
    )

    assert result.exit_code in [0, 2]


def test_coordinate_command_custom_max_rounds(tmp_path: Path) -> None:
    """Test coordinate with custom max rounds."""
    runner = CliRunner()
    output_dir = tmp_path

    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Feature X",
            "--repos",
            "api",
            "--max-rounds",
            "3",
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",
        ],
    )

    assert result.exit_code in [0, 2]


def test_coordinate_command_invalid_config() -> None:
    """Test coordinate with invalid configuration."""
    runner = CliRunner()

    # Empty goal should fail
    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "",
            "--repos",
            "api",
            "--log-level",
            "ERROR",
        ],
    )

    assert result.exit_code == 1
