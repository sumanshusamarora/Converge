"""Tests for Copilot CLI executor."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from converge.execution.copilot_cli import (
    CmdResult,
    CopilotCliExecutor,
    check_copilot_available,
    check_gh_available,
    is_tty,
)


def test_is_tty_both_true() -> None:
    """Test is_tty returns True when both stdin and stdout are TTY."""
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdout.isatty", return_value=True),
    ):
        assert is_tty() is True


def test_is_tty_stdin_false() -> None:
    """Test is_tty returns False when stdin is not a TTY."""
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("sys.stdout.isatty", return_value=True),
    ):
        assert is_tty() is False


def test_is_tty_stdout_false() -> None:
    """Test is_tty returns False when stdout is not a TTY."""
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdout.isatty", return_value=False),
    ):
        assert is_tty() is False


def test_is_tty_both_false() -> None:
    """Test is_tty returns False when neither stdin nor stdout is a TTY."""
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("sys.stdout.isatty", return_value=False),
    ):
        assert is_tty() is False


def test_check_gh_available_found() -> None:
    """Test check_gh_available returns True when gh is found."""
    with patch("shutil.which", return_value="/usr/bin/gh"):
        assert check_gh_available() is True


def test_check_gh_available_not_found() -> None:
    """Test check_gh_available returns False when gh is not found."""
    with patch("shutil.which", return_value=None):
        assert check_gh_available() is False


def test_check_copilot_available_success() -> None:
    """Test check_copilot_available returns True when gh copilot is available."""
    mock_result = Mock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        assert check_copilot_available() is True
        mock_run.assert_called_once_with(
            ["gh", "copilot", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )


def test_check_copilot_available_not_installed() -> None:
    """Test check_copilot_available returns False when gh copilot not installed."""
    mock_result = Mock()
    mock_result.returncode = 1

    with patch("subprocess.run", return_value=mock_result):
        assert check_copilot_available() is False


def test_check_copilot_available_subprocess_error() -> None:
    """Test check_copilot_available returns False on subprocess error."""
    with patch("subprocess.run", side_effect=subprocess.SubprocessError):
        assert check_copilot_available() is False


def test_check_copilot_available_file_not_found() -> None:
    """Test check_copilot_available returns False when gh command not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert check_copilot_available() is False


def test_cmd_result_dataclass() -> None:
    """Test CmdResult dataclass creation."""
    result = CmdResult(
        ok=True,
        exit_code=0,
        stdout_path=Path("/tmp/stdout.txt"),
        stderr_path=Path("/tmp/stderr.txt"),
        message="Success",
    )

    assert result.ok is True
    assert result.exit_code == 0
    assert result.stdout_path == Path("/tmp/stdout.txt")
    assert result.stderr_path == Path("/tmp/stderr.txt")
    assert result.message == "Success"


def test_cmd_result_optional_fields() -> None:
    """Test CmdResult with optional fields as None."""
    result = CmdResult(ok=False, exit_code=1)

    assert result.ok is False
    assert result.exit_code == 1
    assert result.stdout_path is None
    assert result.stderr_path is None
    assert result.message is None


def test_run_plan_no_tty(tmp_path: Path) -> None:
    """Test run_plan fails when TTY is not available."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    with patch("converge.execution.copilot_cli.is_tty", return_value=False):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 2
    assert "TTY" in result.message
    assert "interactive" in result.message.lower()


def test_run_plan_gh_not_available(tmp_path: Path) -> None:
    """Test run_plan fails when GitHub CLI is not available."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=False),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 2
    assert "gh" in result.message.lower()
    assert "install" in result.message.lower()


def test_run_plan_copilot_not_available(tmp_path: Path) -> None:
    """Test run_plan fails when Copilot CLI extension is not available."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=False),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 2
    assert "copilot" in result.message.lower()
    assert "extension" in result.message.lower()


def test_run_plan_prompt_read_error(tmp_path: Path) -> None:
    """Test run_plan fails when prompt file cannot be read."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    prompt_path = tmp_path / "nonexistent.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=True),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 1
    assert "prompt file" in result.message.lower()


def test_run_plan_success(tmp_path: Path) -> None:
    """Test run_plan succeeds when all checks pass."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Fix the bug in main.py")

    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=True),
        patch("subprocess.run", return_value=mock_process) as mock_run,
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is True
    assert result.exit_code == 0
    assert result.message == "Copilot CLI suggestion completed successfully"

    # Verify subprocess was called correctly
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["gh", "copilot", "suggest", "-t", "shell", "Fix the bug in main.py"]
    assert call_args[1]["cwd"] == repo_path


def test_run_plan_failure(tmp_path: Path) -> None:
    """Test run_plan handles command failure."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")

    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 1

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=True),
        patch("subprocess.run", return_value=mock_process),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 1
    assert "exited with code 1" in result.message


def test_run_plan_timeout(tmp_path: Path) -> None:
    """Test run_plan handles timeout."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")

    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=True),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 300)),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 124
    assert "timed out" in result.message.lower()


def test_run_plan_exception(tmp_path: Path) -> None:
    """Test run_plan handles unexpected exceptions."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")

    artifacts_dir = tmp_path / "artifacts"

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=True),
        patch("subprocess.run", side_effect=Exception("Unexpected error")),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is False
    assert result.exit_code == 1
    assert "execution failed" in result.message.lower()
    assert "Unexpected error" in result.message


def test_run_plan_creates_artifacts_directory(tmp_path: Path) -> None:
    """Test run_plan creates artifacts/executions directory."""
    executor = CopilotCliExecutor()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")

    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch("converge.execution.copilot_cli.is_tty", return_value=True),
        patch("converge.execution.copilot_cli.check_gh_available", return_value=True),
        patch("converge.execution.copilot_cli.check_copilot_available", return_value=True),
        patch("subprocess.run", return_value=mock_process),
    ):
        result = executor.run_plan(repo_path, prompt_path, artifacts_dir, "owner/repo")

    assert result.ok is True
    assert (artifacts_dir / "executions").exists()
