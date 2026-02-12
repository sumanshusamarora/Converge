"""Tests for CLI."""

import json
import subprocess
from pathlib import Path

import pytest
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
    assert "--coding-agent-model" in result.output
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


def test_coordinate_command_interrupt_mode_missing_repo_exit_code(
    tmp_path: Path,
) -> None:
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


def test_worker_command_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["worker", "--help"])

    assert result.exit_code == 0
    assert "--once" in result.output
    assert "--poll-interval" in result.output


def test_server_command_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["server", "--help"])

    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output


def test_install_codex_cli_prints_script() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["install-codex-cli", "--package-manager", "npm"])

    assert result.exit_code == 0
    assert "npm install -g @openai/codex" in result.output


def test_install_codex_cli_run_executes_script(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr("converge.cli.main.shutil.which", lambda _: "/usr/bin/npm")
    monkeypatch.setattr(
        "converge.cli.main.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr=""),
    )

    result = runner.invoke(cli, ["install-codex-cli", "--run"])

    assert result.exit_code == 0
    assert "ok" in result.output


def test_doctor_command_text_output(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        "converge.cli.main.CodexAgent.plan_diagnostics",
        lambda _: {
            "planning_mode": "heuristic",
            "should_attempt_codex_plan": False,
            "codex_path": "codex",
            "codex_binary": None,
            "codex_model_configured": None,
            "codex_model_selected": None,
            "codex_model_candidates": ["gpt-5.3-codex", "gpt-5"],
            "fallback_reasons": [
                "Codex CLI not found on PATH for CONVERGE_CODING_AGENT_PATH=codex"
            ],
            "codex_login_status": {
                "checked": False,
                "authenticated": None,
                "reason": "codex_cli_not_found",
            },
        },
    )

    result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "WARN: Codex planning mode = heuristic" in result.output
    assert "codex_binary: not found" in result.output
    assert "codex_model_configured: auto" in result.output
    assert "fallback_reasons:" in result.output


def test_doctor_command_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    diagnostics = {
        "planning_mode": "codex_cli",
        "should_attempt_codex_plan": True,
        "codex_path": "codex",
        "codex_binary": "/usr/bin/codex",
        "codex_model_configured": None,
        "codex_model_selected": "gpt-5",
        "codex_model_candidates": ["gpt-5", "gpt-5-mini"],
        "fallback_reasons": [],
        "codex_login_status": {"checked": True, "authenticated": True, "exit_code": 0},
    }

    monkeypatch.setattr(
        "converge.cli.main.CodexAgent.plan_diagnostics",
        lambda _: diagnostics,
    )

    result = runner.invoke(cli, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == diagnostics


def test_doctor_command_text_output_includes_recommendations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        "converge.cli.main.CodexAgent.plan_diagnostics",
        lambda _: {
            "planning_mode": "heuristic",
            "should_attempt_codex_plan": False,
            "codex_path": "codex",
            "codex_binary": "/usr/bin/codex",
            "codex_model_configured": "gpt-5",
            "codex_model_selected": "gpt-5",
            "codex_model_candidates": ["gpt-5"],
            "fallback_reasons": [
                "Coding agent planning disabled by CONVERGE_CODING_AGENT_PLAN_MODE=disable"
            ],
            "recommendations": [
                "Set CONVERGE_CODING_AGENT_PLAN_MODE=auto to re-enable Codex planning"
            ],
            "codex_login_status": {
                "checked": True,
                "authenticated": True,
                "exit_code": 0,
            },
        },
    )

    result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "recommendations:" in result.output
    assert "CONVERGE_CODING_AGENT_PLAN_MODE" in result.output
