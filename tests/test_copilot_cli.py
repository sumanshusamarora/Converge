"""Tests for Copilot CLI executor."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from converge.execution.copilot_cli import (
    CmdResult,
    CopilotCliExecutor,
    check_copilot_available,
    is_tty,
)


def test_is_tty_returns_true_when_both_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_tty returns True when both stdin and stdout are TTY."""
    mock_stdin = Mock()
    mock_stdin.isatty.return_value = True
    mock_stdout = Mock()
    mock_stdout.isatty.return_value = True

    monkeypatch.setattr(sys, "stdin", mock_stdin)
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    assert is_tty() is True


def test_is_tty_returns_false_when_stdin_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_tty returns False when stdin is not TTY."""
    mock_stdin = Mock()
    mock_stdin.isatty.return_value = False
    mock_stdout = Mock()
    mock_stdout.isatty.return_value = True

    monkeypatch.setattr(sys, "stdin", mock_stdin)
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    assert is_tty() is False


def test_is_tty_returns_false_when_stdout_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_tty returns False when stdout is not TTY."""
    mock_stdin = Mock()
    mock_stdin.isatty.return_value = True
    mock_stdout = Mock()
    mock_stdout.isatty.return_value = False

    monkeypatch.setattr(sys, "stdin", mock_stdin)
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    assert is_tty() is False


def test_is_tty_returns_false_when_both_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_tty returns False when both stdin and stdout are not TTY."""
    mock_stdin = Mock()
    mock_stdin.isatty.return_value = False
    mock_stdout = Mock()
    mock_stdout.isatty.return_value = False

    monkeypatch.setattr(sys, "stdin", mock_stdin)
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    assert is_tty() is False


@patch("converge.execution.copilot_cli.shutil.which")
def test_check_copilot_available_returns_false_when_gh_not_found(
    mock_which: MagicMock,
) -> None:
    """Test check_copilot_available returns False when gh is not in PATH."""
    mock_which.return_value = None

    assert check_copilot_available() is False
    mock_which.assert_called_once_with("gh")


@patch("converge.execution.copilot_cli.subprocess.run")
@patch("converge.execution.copilot_cli.shutil.which")
def test_check_copilot_available_returns_true_when_available(
    mock_which: MagicMock,
    mock_run: MagicMock,
) -> None:
    """Test check_copilot_available returns True when gh copilot is available."""
    mock_which.return_value = "/usr/bin/gh"
    mock_result = Mock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    assert check_copilot_available() is True
    mock_which.assert_called_once_with("gh")
    mock_run.assert_called_once()


@patch("converge.execution.copilot_cli.subprocess.run")
@patch("converge.execution.copilot_cli.shutil.which")
def test_check_copilot_available_returns_false_when_command_fails(
    mock_which: MagicMock,
    mock_run: MagicMock,
) -> None:
    """Test check_copilot_available returns False when gh copilot command fails."""
    mock_which.return_value = "/usr/bin/gh"
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "extension not installed"
    mock_run.return_value = mock_result

    assert check_copilot_available() is False


@patch("converge.execution.copilot_cli.subprocess.run")
@patch("converge.execution.copilot_cli.shutil.which")
def test_check_copilot_available_handles_timeout(
    mock_which: MagicMock,
    mock_run: MagicMock,
) -> None:
    """Test check_copilot_available handles subprocess timeout."""
    mock_which.return_value = "/usr/bin/gh"
    mock_run.side_effect = TimeoutError("Command timed out")

    assert check_copilot_available() is False


def test_copilot_executor_run_plan_raises_when_no_tty(tmp_path: Path) -> None:
    """Test run_plan raises RuntimeError when TTY is not available."""
    executor = CopilotCliExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test prompt", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=False),
        pytest.raises(RuntimeError, match="requires TTY"),
    ):
        executor.run_plan(repo_path, prompt_path, artifacts_dir)


def test_copilot_executor_run_plan_raises_when_copilot_not_available(
    tmp_path: Path,
) -> None:
    """Test run_plan raises RuntimeError when Copilot CLI is not available."""
    executor = CopilotCliExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test prompt", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=False),
        pytest.raises(RuntimeError, match="not available"),
    ):
        executor.run_plan(repo_path, prompt_path, artifacts_dir)


@patch("converge.execution.copilot_cli.subprocess.run")
@patch("converge.execution.copilot_cli.check_copilot_available")
@patch("converge.execution.copilot_cli.is_tty")
def test_copilot_executor_run_plan_success(
    mock_is_tty: MagicMock,
    mock_check_available: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """Test run_plan executes successfully and saves artifacts."""
    mock_is_tty.return_value = True
    mock_check_available.return_value = True

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "Copilot output"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    executor = CopilotCliExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_content = "Test prompt for copilot"
    prompt_path.write_text(prompt_content, encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    result = executor.run_plan(repo_path, prompt_path, artifacts_dir)

    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == "Copilot output"
    assert result.stderr == ""
    assert len(result.artifacts_saved) == 3  # prompt, stdout, stderr

    # Verify artifacts were saved
    assert (artifacts_dir / "executions" / "copilot_prompt.txt").exists()
    assert (artifacts_dir / "executions" / "copilot_stdout.txt").exists()
    assert (artifacts_dir / "executions" / "copilot_stderr.txt").exists()

    # Verify subprocess was called correctly
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args.kwargs["cwd"] == repo_path
    assert "gh" in call_args.args[0]
    assert "copilot" in call_args.args[0]


@patch("converge.execution.copilot_cli.subprocess.run")
@patch("converge.execution.copilot_cli.check_copilot_available")
@patch("converge.execution.copilot_cli.is_tty")
def test_copilot_executor_run_plan_command_failure(
    mock_is_tty: MagicMock,
    mock_check_available: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """Test run_plan handles command failure gracefully."""
    mock_is_tty.return_value = True
    mock_check_available.return_value = True

    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error: command failed"
    mock_run.return_value = mock_result

    executor = CopilotCliExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test prompt", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    result = executor.run_plan(repo_path, prompt_path, artifacts_dir)

    assert result.success is False
    assert result.exit_code == 1
    assert result.stderr == "Error: command failed"


@patch("converge.execution.copilot_cli.subprocess.run")
@patch("converge.execution.copilot_cli.check_copilot_available")
@patch("converge.execution.copilot_cli.is_tty")
def test_copilot_executor_run_plan_timeout(
    mock_is_tty: MagicMock,
    mock_check_available: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """Test run_plan handles subprocess timeout."""
    import subprocess

    mock_is_tty.return_value = True
    mock_check_available.return_value = True
    mock_run.side_effect = subprocess.TimeoutExpired("gh", 60)

    executor = CopilotCliExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test prompt", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"

    result = executor.run_plan(repo_path, prompt_path, artifacts_dir)

    assert result.success is False
    assert result.exit_code == 124  # Timeout exit code
    assert "timed out" in result.stderr


@patch("converge.execution.copilot_cli.check_copilot_available")
@patch("converge.execution.copilot_cli.is_tty")
def test_copilot_executor_run_plan_invalid_prompt_file(
    mock_is_tty: MagicMock,
    mock_check_available: MagicMock,
    tmp_path: Path,
) -> None:
    """Test run_plan handles invalid prompt file gracefully."""
    mock_is_tty.return_value = True
    mock_check_available.return_value = True

    executor = CopilotCliExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "nonexistent.txt"  # File doesn't exist
    artifacts_dir = tmp_path / "artifacts"

    result = executor.run_plan(repo_path, prompt_path, artifacts_dir)

    assert result.success is False
    assert result.exit_code == 1
    assert "Failed to read prompt" in result.stderr


def test_cmd_result_dataclass() -> None:
    """Test CmdResult dataclass."""
    result = CmdResult(
        success=True,
        exit_code=0,
        stdout="output",
        stderr="",
        artifacts_saved=["/path/to/artifact"],
    )

    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == "output"
    assert result.stderr == ""
    assert result.artifacts_saved == ["/path/to/artifact"]
