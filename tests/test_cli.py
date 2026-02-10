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
    """Test basic coordinate command execution with run artifacts."""
    runner = CliRunner()
    output_dir = tmp_path / "out"

    api_dir = tmp_path / "api"
    web_dir = tmp_path / "web"
    api_dir.mkdir()
    web_dir.mkdir()
    (api_dir / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")
    (web_dir / "package.json").write_text('{"name":"web"}', encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Add discount code support",
            "--repos",
            str(api_dir),
            "--repos",
            str(web_dir),
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",
        ],
    )

    assert result.exit_code == 0
    run_dirs = sorted((output_dir / "runs").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "summary.md").exists()
    assert (run_dirs[0] / "responsibility-matrix.md").exists()
    assert (run_dirs[0] / "run.json").exists()


def test_coordinate_command_missing_repo_exit_code(tmp_path: Path) -> None:
    """Test missing repository path returns escalation exit code 2."""
    runner = CliRunner()
    output_dir = tmp_path / "out"

    existing_repo = tmp_path / "backend"
    existing_repo.mkdir()

    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Feature X",
            "--repos",
            str(existing_repo),
            "--repos",
            str(tmp_path / "missing-repo"),
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",
        ],
    )

    assert result.exit_code == 2


def test_coordinate_command_invalid_config() -> None:
    """Test coordinate with invalid configuration."""
    runner = CliRunner()

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
