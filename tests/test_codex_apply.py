"""Tests for Codex apply executor."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from converge.execution.codex_apply import CodexApplyExecutor, ExecResult
from converge.execution.git_utils import GitError


def test_exec_result_dataclass() -> None:
    """Test ExecResult dataclass creation."""
    result = ExecResult(
        ok=True,
        exit_code=0,
        message="Success",
        logs={"stdout": "/tmp/out.txt"},
        changed_files=["file1.txt", "file2.py"],
        diff_stat="2 files changed, 10 insertions(+), 5 deletions(-)",
    )

    assert result.ok is True
    assert result.exit_code == 0
    assert result.message == "Success"
    assert result.logs == {"stdout": "/tmp/out.txt"}
    assert result.changed_files == ["file1.txt", "file2.py"]
    assert result.diff_stat == "2 files changed, 10 insertions(+), 5 deletions(-)"


def test_exec_result_defaults() -> None:
    """Test ExecResult with default values."""
    result = ExecResult(ok=False, exit_code=1, message="Failed")

    assert result.ok is False
    assert result.exit_code == 1
    assert result.message == "Failed"
    assert result.logs == {}
    assert result.changed_files == []
    assert result.diff_stat == ""


def test_check_codex_available_found() -> None:
    """Test check_codex_available returns True when codex is found."""
    executor = CodexApplyExecutor()

    with patch("shutil.which", return_value="/usr/local/bin/codex"):
        assert executor.check_codex_available() is True


def test_check_codex_available_not_found() -> None:
    """Test check_codex_available returns False when codex is not found."""
    executor = CodexApplyExecutor()

    with patch("shutil.which", return_value=None):
        assert executor.check_codex_available() is False


def test_check_codex_available_custom_path() -> None:
    """Test check_codex_available uses custom codex path."""
    executor = CodexApplyExecutor(codex_path="custom-codex")

    with patch("shutil.which", return_value="/opt/codex/custom-codex") as mock_which:
        assert executor.check_codex_available() is True
        mock_which.assert_called_once_with("custom-codex")


def test_apply_execution_mode_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when execution mode is 'plan'."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "plan")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 2
    assert "refused" in result.message.lower()
    assert "plan" in result.message


def test_apply_codex_apply_not_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when CONVERGE_CODEX_APPLY is not true."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 2
    assert "CONVERGE_CODEX_APPLY" in result.message


def test_apply_repo_path_not_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when repository path does not exist."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "nonexistent"
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 2
    assert "does not exist" in result.message


def test_apply_no_git_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when .git directory is missing."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 2
    assert "Not a git repository" in result.message


def test_apply_working_tree_not_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when working tree is not clean and ALLOW_DIRTY is false."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_ALLOW_DIRTY", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=False
        ),
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["file1.txt", "file2.py"],
        ),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 2
    assert "not clean" in result.message.lower()
    assert "2 uncommitted changes" in result.message


def test_apply_working_tree_dirty_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply proceeds when working tree is dirty but ALLOW_DIRTY is true."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_ALLOW_DIRTY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=False
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch("converge.execution.codex_apply.get_changed_files", return_value=[]),
        patch(
            "converge.execution.codex_apply.get_diff_stat", return_value="No changes"
        ),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    # Should proceed despite dirty working tree
    assert result.ok is True
    assert result.exit_code == 0


def test_apply_codex_not_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when Codex CLI is not available."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value=None),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 2
    assert "not found" in result.message.lower()


def test_apply_creates_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test apply creates a new branch when CONVERGE_CREATE_BRANCH is true."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "true")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch(
            "converge.execution.codex_apply.current_branch", return_value="main"
        ) as mock_current,
        patch("converge.execution.codex_apply.create_branch") as mock_create,
        patch("subprocess.run", return_value=mock_process),
        patch("converge.execution.codex_apply.get_changed_files", return_value=[]),
        patch(
            "converge.execution.codex_apply.get_diff_stat", return_value="No changes"
        ),
    ):
        result = executor.apply(
            repo_path, prompt_path, artifacts_dir, "converge/test-branch"
        )

    assert result.ok is True
    mock_current.assert_called_once_with(repo_path)
    mock_create.assert_called_once_with(repo_path, "converge/test-branch")
    assert "branch_created" in result.logs


def test_apply_branch_creation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails gracefully when branch creation fails."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "true")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("converge.execution.codex_apply.current_branch", return_value="main"),
        patch(
            "converge.execution.codex_apply.create_branch",
            side_effect=GitError("Branch already exists"),
        ),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 1
    assert "Failed to create branch" in result.message


def test_apply_prompt_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply fails when prompt file cannot be read."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "nonexistent.txt"
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 1
    assert "prompt file" in result.message.lower()


def test_apply_codex_execution_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test successful Codex apply execution."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Fix the bug in main.py")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process) as mock_run,
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["main.py"],
        ),
        patch(
            "converge.execution.codex_apply.get_diff_stat",
            return_value="1 file changed, 5 insertions(+), 2 deletions(-)",
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(5, 2),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=256,
        ),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is True
    assert result.exit_code == 0
    assert "successfully" in result.message.lower()
    assert result.changed_files == ["main.py"]
    assert result.diff_added == 5
    assert result.diff_deleted == 2
    assert result.diff_bytes == 256
    assert result.threshold_exceeded is False
    assert "codex_stdout" in result.logs
    assert "codex_stderr" in result.logs

    # Verify Codex was called with correct arguments
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["codex", "apply", "--prompt", "Fix the bug in main.py"]
    assert call_args[1]["cwd"] == repo_path


def test_apply_codex_execution_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply handles Codex execution failure."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 1

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 1
    assert "failed" in result.message.lower()


def test_apply_codex_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test apply handles Codex execution timeout."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 600)),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is False
    assert result.exit_code == 124
    assert "timed out" in result.message.lower()


def test_apply_commits_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test apply commits changes when CONVERGE_GIT_COMMIT is true."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "true")
    monkeypatch.setenv("CONVERGE_GIT_AUTHOR_NAME", "Test Bot")
    monkeypatch.setenv("CONVERGE_GIT_AUTHOR_EMAIL", "bot@test.com")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["file1.txt"],
        ),
        patch(
            "converge.execution.codex_apply.get_diff_stat",
            return_value="1 file changed, 3 insertions(+)",
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(3, 0),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=128,
        ),
        patch("converge.execution.codex_apply.commit_all") as mock_commit,
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is True
    assert "committed" in result.logs
    mock_commit.assert_called_once_with(
        repo_path,
        "Converge: Apply Codex changes\n\n1 file changed, 3 insertions(+)",
        "Test Bot",
        "bot@test.com",
    )


def test_apply_skips_commit_when_no_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply skips commit when there are no changes."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "true")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch("converge.execution.codex_apply.get_changed_files", return_value=[]),
        patch(
            "converge.execution.codex_apply.get_diff_stat", return_value="No changes"
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(0, 0),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=0,
        ),
        patch("converge.execution.codex_apply.commit_all") as mock_commit,
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    assert result.ok is True
    # commit_all should not be called when there are no changes
    mock_commit.assert_not_called()
    assert "committed" not in result.logs


def test_apply_runs_verification_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply runs verification commands."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "false")

    executor = CodexApplyExecutor(allowlisted_commands=["pytest", "ruff"])
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    verification_cmds = ["pytest tests/", "ruff check ."]

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process) as mock_run,
        patch("converge.execution.codex_apply.get_changed_files", return_value=[]),
        patch(
            "converge.execution.codex_apply.get_diff_stat", return_value="No changes"
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(0, 0),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=0,
        ),
    ):
        result = executor.apply(
            repo_path,
            prompt_path,
            artifacts_dir,
            "converge/test",
            verification_cmds=verification_cmds,
        )

    assert result.ok is True
    # Should have called: codex apply, pytest, ruff
    assert mock_run.call_count == 3
    assert "verify_0_stdout" in result.logs
    assert "verify_1_stdout" in result.logs


def test_apply_skips_non_allowlisted_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply skips non-allowlisted verification commands."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "false")

    executor = CodexApplyExecutor(allowlisted_commands=["pytest"])
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    verification_cmds = ["pytest tests/", "rm -rf /"]  # Second command not allowlisted

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process) as mock_run,
        patch("converge.execution.codex_apply.get_changed_files", return_value=[]),
        patch(
            "converge.execution.codex_apply.get_diff_stat", return_value="No changes"
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(0, 0),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=0,
        ),
    ):
        result = executor.apply(
            repo_path,
            prompt_path,
            artifacts_dir,
            "converge/test",
            verification_cmds=verification_cmds,
        )

    assert result.ok is True
    # Should have called: codex apply, pytest (but NOT rm)
    assert mock_run.call_count == 2


def test_apply_interactive_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test apply works with CONVERGE_EXECUTION_MODE=interactive."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "interactive")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "false")

    executor = CodexApplyExecutor()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch("converge.execution.codex_apply.get_changed_files", return_value=[]),
        patch(
            "converge.execution.codex_apply.get_diff_stat", return_value="No changes"
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(0, 0),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=0,
        ),
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    # Should succeed with interactive mode
    assert result.ok is True
    assert result.exit_code == 0


def test_apply_threshold_max_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test threshold enforcement for max changed files."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "true")

    executor = CodexApplyExecutor(max_changed_files=2)
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["file1.txt", "file2.py", "file3.js"],
        ),
        patch(
            "converge.execution.codex_apply.get_diff_stat",
            return_value="3 files changed",
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(10, 5),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=500,
        ),
        patch("converge.execution.codex_apply.commit_all") as mock_commit,
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    # Should succeed but mark as HITL_REQUIRED
    assert result.ok is True
    assert result.exit_code == 0
    assert result.threshold_exceeded is True
    assert "HITL_REQUIRED" in result.message
    assert "3 exceeds limit of 2" in result.message
    # Commit should NOT have been called
    mock_commit.assert_not_called()


def test_apply_threshold_max_diff_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test threshold enforcement for max diff lines."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "true")

    executor = CodexApplyExecutor(max_diff_lines=100)
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["file1.txt"],
        ),
        patch(
            "converge.execution.codex_apply.get_diff_stat",
            return_value="1 file changed, 80 insertions(+), 50 deletions(-)",
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(80, 50),  # Total 130 > 100
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=5000,
        ),
        patch("converge.execution.codex_apply.commit_all") as mock_commit,
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    # Should succeed but mark as HITL_REQUIRED
    assert result.ok is True
    assert result.exit_code == 0
    assert result.threshold_exceeded is True
    assert "HITL_REQUIRED" in result.message
    assert "130 exceeds limit of 100" in result.message
    # Commit should NOT have been called
    mock_commit.assert_not_called()


def test_apply_threshold_max_diff_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test threshold enforcement for max diff bytes."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "true")

    executor = CodexApplyExecutor(max_diff_bytes=1000)
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["file1.txt"],
        ),
        patch(
            "converge.execution.codex_apply.get_diff_stat",
            return_value="1 file changed",
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(10, 5),
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=2000,  # > 1000
        ),
        patch("converge.execution.codex_apply.commit_all") as mock_commit,
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    # Should succeed but mark as HITL_REQUIRED
    assert result.ok is True
    assert result.exit_code == 0
    assert result.threshold_exceeded is True
    assert "HITL_REQUIRED" in result.message
    assert "2000 bytes exceeds limit of 1000" in result.message
    # Commit should NOT have been called
    mock_commit.assert_not_called()


def test_apply_within_thresholds_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that changes within thresholds are committed normally."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")
    monkeypatch.setenv("CONVERGE_CODEX_APPLY", "true")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_GIT_COMMIT", "true")

    executor = CodexApplyExecutor(
        max_changed_files=10, max_diff_lines=100, max_diff_bytes=5000
    )
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test instruction")
    artifacts_dir = tmp_path / "artifacts"

    mock_process = Mock()
    mock_process.returncode = 0

    with (
        patch(
            "converge.execution.codex_apply.is_working_tree_clean", return_value=True
        ),
        patch("shutil.which", return_value="/usr/bin/codex"),
        patch("subprocess.run", return_value=mock_process),
        patch(
            "converge.execution.codex_apply.get_changed_files",
            return_value=["file1.txt", "file2.py"],  # 2 < 10
        ),
        patch(
            "converge.execution.codex_apply.get_diff_stat",
            return_value="2 files changed, 30 insertions(+), 10 deletions(-)",
        ),
        patch(
            "converge.execution.codex_apply.get_diff_line_counts",
            return_value=(30, 10),  # Total 40 < 100
        ),
        patch(
            "converge.execution.codex_apply.get_diff_bytes",
            return_value=1500,  # < 5000
        ),
        patch("converge.execution.codex_apply.commit_all") as mock_commit,
    ):
        result = executor.apply(repo_path, prompt_path, artifacts_dir, "converge/test")

    # Should succeed and commit
    assert result.ok is True
    assert result.exit_code == 0
    assert result.threshold_exceeded is False
    assert "HITL_REQUIRED" not in result.message
    # Commit SHOULD have been called
    mock_commit.assert_called_once()
