"""Tests for git utilities."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from converge.execution.git_utils import (
    GitError,
    commit_all,
    create_branch,
    current_branch,
    ensure_git_repo,
    get_changed_files,
    get_diff_bytes,
    get_diff_line_counts,
    get_diff_numstat,
    get_diff_stat,
    is_working_tree_clean,
)


def test_ensure_git_repo_success(tmp_path: Path) -> None:
    """Test ensure_git_repo succeeds with valid git repository."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    # Should not raise
    ensure_git_repo(repo_path)


def test_ensure_git_repo_path_not_exists() -> None:
    """Test ensure_git_repo fails when path does not exist."""
    with pytest.raises(GitError, match="does not exist"):
        ensure_git_repo(Path("/nonexistent/path"))


def test_ensure_git_repo_no_git_dir(tmp_path: Path) -> None:
    """Test ensure_git_repo fails when .git directory is missing."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    with pytest.raises(GitError, match="Not a git repository"):
        ensure_git_repo(repo_path)


def test_is_working_tree_clean_success(tmp_path: Path) -> None:
    """Test is_working_tree_clean returns True when tree is clean."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = is_working_tree_clean(tmp_path)

    assert result is True
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "status", "--porcelain"]
    assert call_args[1]["cwd"] == tmp_path


def test_is_working_tree_clean_has_changes(tmp_path: Path) -> None:
    """Test is_working_tree_clean returns False when there are changes."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "M  file1.txt\n?? file2.txt\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = is_working_tree_clean(tmp_path)

    assert result is False


def test_is_working_tree_clean_git_error(tmp_path: Path) -> None:
    """Test is_working_tree_clean raises GitError when git command fails."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git status failed"):
            is_working_tree_clean(tmp_path)


def test_is_working_tree_clean_timeout(tmp_path: Path) -> None:
    """Test is_working_tree_clean raises GitError on timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
        with pytest.raises(GitError, match="timed out"):
            is_working_tree_clean(tmp_path)


def test_current_branch_success(tmp_path: Path) -> None:
    """Test current_branch returns the branch name."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "main\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        branch = current_branch(tmp_path)

    assert branch == "main"
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    assert call_args[1]["cwd"] == tmp_path


def test_current_branch_git_error(tmp_path: Path) -> None:
    """Test current_branch raises GitError when git command fails."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git rev-parse failed"):
            current_branch(tmp_path)


def test_current_branch_timeout(tmp_path: Path) -> None:
    """Test current_branch raises GitError on timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
        with pytest.raises(GitError, match="timed out"):
            current_branch(tmp_path)


def test_create_branch_success(tmp_path: Path) -> None:
    """Test create_branch creates and checks out a new branch."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "Switched to a new branch 'feature/test'"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        create_branch(tmp_path, "feature/test")

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "checkout", "-b", "feature/test"]
    assert call_args[1]["cwd"] == tmp_path


def test_create_branch_already_exists(tmp_path: Path) -> None:
    """Test create_branch raises GitError when branch already exists."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: A branch named 'feature/test' already exists"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git checkout -b failed"):
            create_branch(tmp_path, "feature/test")


def test_create_branch_timeout(tmp_path: Path) -> None:
    """Test create_branch raises GitError on timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
        with pytest.raises(GitError, match="timed out"):
            create_branch(tmp_path, "feature/test")


def test_commit_all_success(tmp_path: Path) -> None:
    """Test commit_all stages and commits all changes."""
    add_result = Mock()
    add_result.returncode = 0

    commit_result = Mock()
    commit_result.returncode = 0
    commit_result.stdout = "[main abc123] Test commit"
    commit_result.stderr = ""

    with patch("subprocess.run", side_effect=[add_result, commit_result]) as mock_run:
        commit_all(tmp_path, "Test commit", "Test User", "test@example.com")

    assert mock_run.call_count == 2

    # Check git add call
    add_call = mock_run.call_args_list[0]
    assert add_call[0][0] == ["git", "add", "-A"]
    assert add_call[1]["cwd"] == tmp_path

    # Check git commit call
    commit_call = mock_run.call_args_list[1]
    assert commit_call[0][0] == [
        "git",
        "commit",
        "-m",
        "Test commit",
        "--author",
        "Test User <test@example.com>",
    ]
    assert commit_call[1]["cwd"] == tmp_path


def test_commit_all_nothing_to_commit(tmp_path: Path) -> None:
    """Test commit_all handles 'nothing to commit' gracefully."""
    add_result = Mock()
    add_result.returncode = 0

    commit_result = Mock()
    commit_result.returncode = 1
    commit_result.stdout = "nothing to commit, working tree clean"
    commit_result.stderr = ""

    with patch("subprocess.run", side_effect=[add_result, commit_result]):
        # Should not raise
        commit_all(tmp_path, "Test commit", "Test User", "test@example.com")


def test_commit_all_add_fails(tmp_path: Path) -> None:
    """Test commit_all raises GitError when git add fails."""
    add_result = Mock()
    add_result.returncode = 1
    add_result.stderr = "fatal: pathspec error"

    with patch("subprocess.run", return_value=add_result):
        with pytest.raises(GitError, match="git add failed"):
            commit_all(tmp_path, "Test commit", "Test User", "test@example.com")


def test_commit_all_commit_fails(tmp_path: Path) -> None:
    """Test commit_all raises GitError when git commit fails."""
    add_result = Mock()
    add_result.returncode = 0

    commit_result = Mock()
    commit_result.returncode = 1
    commit_result.stdout = "error: commit failed"
    commit_result.stderr = "fatal: unable to create commit"

    with patch("subprocess.run", side_effect=[add_result, commit_result]):
        with pytest.raises(GitError, match="git commit failed"):
            commit_all(tmp_path, "Test commit", "Test User", "test@example.com")


def test_commit_all_timeout(tmp_path: Path) -> None:
    """Test commit_all raises GitError on timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
        with pytest.raises(GitError, match="timed out"):
            commit_all(tmp_path, "Test commit", "Test User", "test@example.com")


def test_get_changed_files_success(tmp_path: Path) -> None:
    """Test get_changed_files returns list of changed files."""
    mock_result = Mock()
    mock_result.returncode = 0
    # Git status --porcelain format: "XY filename" (no leading space)
    mock_result.stdout = " M file1.txt\n?? file2.txt\nA  dir/file3.py\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        files = get_changed_files(tmp_path)

    assert files == ["file1.txt", "file2.txt", "dir/file3.py"]
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "status", "--porcelain"]


def test_get_changed_files_empty(tmp_path: Path) -> None:
    """Test get_changed_files returns empty list when no changes."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        files = get_changed_files(tmp_path)

    assert files == []


def test_get_changed_files_git_error(tmp_path: Path) -> None:
    """Test get_changed_files raises GitError when git command fails."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git status failed"):
            get_changed_files(tmp_path)


def test_get_diff_stat_success(tmp_path: Path) -> None:
    """Test get_diff_stat returns diff statistics summary."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = (
        " file1.txt | 10 ++++++++--\n"
        " file2.py  |  5 ++---\n"
        " 2 files changed, 10 insertions(+), 5 deletions(-)\n"
    )
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        stat = get_diff_stat(tmp_path)

    assert stat == "2 files changed, 10 insertions(+), 5 deletions(-)"
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "diff", "--stat", "HEAD"]


def test_get_diff_stat_no_changes(tmp_path: Path) -> None:
    """Test get_diff_stat returns 'No changes' when there are no diffs."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        stat = get_diff_stat(tmp_path)

    assert stat == "No changes"


def test_get_diff_stat_git_error(tmp_path: Path) -> None:
    """Test get_diff_stat raises GitError when git command fails."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git diff --stat failed"):
            get_diff_stat(tmp_path)


def test_get_diff_stat_timeout(tmp_path: Path) -> None:
    """Test get_diff_stat raises GitError on timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
        with pytest.raises(GitError, match="timed out"):
            get_diff_stat(tmp_path)


def test_get_diff_numstat_success(tmp_path: Path) -> None:
    """Test get_diff_numstat returns per-file statistics."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "10\t5\tfile1.txt\n3\t7\tdir/file2.py\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        stats = get_diff_numstat(tmp_path)

    assert stats == [("file1.txt", 10, 5), ("dir/file2.py", 3, 7)]
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "diff", "--numstat", "HEAD"]


def test_get_diff_numstat_binary_files(tmp_path: Path) -> None:
    """Test get_diff_numstat handles binary files (marked with -)."""
    mock_result = Mock()
    mock_result.returncode = 0
    # Binary files are marked with '-' for added/deleted
    mock_result.stdout = "10\t5\tfile1.txt\n-\t-\timage.png\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        stats = get_diff_numstat(tmp_path)

    # Binary files should have 0 for both added and deleted
    assert stats == [("file1.txt", 10, 5), ("image.png", 0, 0)]


def test_get_diff_numstat_empty(tmp_path: Path) -> None:
    """Test get_diff_numstat returns empty list when no changes."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        stats = get_diff_numstat(tmp_path)

    assert stats == []


def test_get_diff_numstat_git_error(tmp_path: Path) -> None:
    """Test get_diff_numstat raises GitError when git command fails."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git diff --numstat failed"):
            get_diff_numstat(tmp_path)


def test_get_diff_line_counts_success(tmp_path: Path) -> None:
    """Test get_diff_line_counts returns total added and deleted lines."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "10\t5\tfile1.txt\n3\t7\tfile2.py\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        added, deleted = get_diff_line_counts(tmp_path)

    # 10+3=13 added, 5+7=12 deleted
    assert added == 13
    assert deleted == 12


def test_get_diff_line_counts_no_changes(tmp_path: Path) -> None:
    """Test get_diff_line_counts returns (0, 0) when no changes."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        added, deleted = get_diff_line_counts(tmp_path)

    assert added == 0
    assert deleted == 0


def test_get_diff_bytes_success(tmp_path: Path) -> None:
    """Test get_diff_bytes returns approximate diff size."""
    mock_result = Mock()
    mock_result.returncode = 0
    # Sample diff output
    mock_result.stdout = "diff --git a/file.txt b/file.txt\n+new line\n-old line\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        size = get_diff_bytes(tmp_path)

    # Size should match the byte length of the diff output
    expected_size = len(mock_result.stdout.encode("utf-8"))
    assert size == expected_size
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["git", "diff", "HEAD"]


def test_get_diff_bytes_no_changes(tmp_path: Path) -> None:
    """Test get_diff_bytes returns 0 when no changes."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        size = get_diff_bytes(tmp_path)

    assert size == 0


def test_get_diff_bytes_git_error(tmp_path: Path) -> None:
    """Test get_diff_bytes raises GitError when git command fails."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: not a git repository"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(GitError, match="git diff failed"):
            get_diff_bytes(tmp_path)
