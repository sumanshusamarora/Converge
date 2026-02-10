"""Tests for CLI."""

from pathlib import Path

from click.testing import CliRunner

from converge.cli.main import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Converge: Multi-repository coordination" in result.output


def test_coordinate_command_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["coordinate", "--help"])

    assert result.exit_code == 0
    assert "--model" in result.output
    assert "--no-llm" in result.output
    assert "--no-tracing" in result.output
    assert "--hil-mode" in result.output


def test_coordinate_command_conditional_mode(tmp_path: Path) -> None:
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
            "--no-llm",
            "--no-tracing",
            "--hil-mode",
            "conditional",
        ],
    )

    assert result.exit_code == 0


def test_coordinate_command_interrupt_mode_missing_repo_exit_code(tmp_path: Path) -> None:
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
            "--no-llm",
            "--no-tracing",
            "--hil-mode",
            "interrupt",
        ],
    )

    assert result.exit_code == 2
