"""Git utilities for safe repository operations.

This module provides git operations that are used by execution engines
to safely manage repository state, branches, and commits.
All commands are executed via subprocess with proper error handling.
"""

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails."""

    pass


def ensure_git_repo(repo_path: Path) -> None:
    """Ensure the path is a valid git repository.

    Args:
        repo_path: Path to check

    Raises:
        GitError: If path is not a git repository or .git directory is missing
    """
    if not repo_path.exists():
        raise GitError(f"Repository path does not exist: {repo_path}")

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise GitError(
            f"Not a git repository (no .git directory found): {repo_path}\n"
            f"Initialize a git repository first with: git init"
        )


def is_working_tree_clean(repo_path: Path) -> bool:
    """Check if the git working tree is clean (no uncommitted changes).

    Args:
        repo_path: Path to the git repository

    Returns:
        True if working tree is clean, False otherwise

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise GitError(f"git status failed: {result.stderr}")

        # Empty output means clean working tree
        return len(result.stdout.strip()) == 0

    except subprocess.TimeoutExpired as e:
        raise GitError(f"git status timed out: {e}") from e
    except Exception as e:
        raise GitError(f"Failed to check working tree status: {e}") from e


def current_branch(repo_path: Path) -> str:
    """Get the name of the current git branch.

    Args:
        repo_path: Path to the git repository

    Returns:
        Name of the current branch

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise GitError(f"git rev-parse failed: {result.stderr}")

        return result.stdout.strip()

    except subprocess.TimeoutExpired as e:
        raise GitError(f"git rev-parse timed out: {e}") from e
    except Exception as e:
        raise GitError(f"Failed to get current branch: {e}") from e


def create_branch(repo_path: Path, branch_name: str) -> None:
    """Create and checkout a new git branch.

    Args:
        repo_path: Path to the git repository
        branch_name: Name of the branch to create

    Raises:
        GitError: If git command fails
    """
    try:
        # Create and checkout the new branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise GitError(f"git checkout -b failed: {result.stderr}")

    except subprocess.TimeoutExpired as e:
        raise GitError(f"git checkout -b timed out: {e}") from e
    except Exception as e:
        raise GitError(f"Failed to create branch: {e}") from e


def commit_all(
    repo_path: Path, message: str, author_name: str, author_email: str
) -> None:
    """Stage all changes and create a commit.

    Args:
        repo_path: Path to the git repository
        message: Commit message
        author_name: Name of the commit author
        author_email: Email of the commit author

    Raises:
        GitError: If git command fails
    """
    try:
        # Stage all changes
        add_result = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if add_result.returncode != 0:
            raise GitError(f"git add failed: {add_result.stderr}")

        # Create commit with author information
        author = f"{author_name} <{author_email}>"
        commit_result = subprocess.run(
            ["git", "commit", "-m", message, "--author", author],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if commit_result.returncode != 0:
            # Exit code 1 with "nothing to commit" is not an error
            if "nothing to commit" in commit_result.stdout.lower():
                return
            raise GitError(f"git commit failed: {commit_result.stderr}")

    except subprocess.TimeoutExpired as e:
        raise GitError(f"git commit timed out: {e}") from e
    except Exception as e:
        raise GitError(f"Failed to commit changes: {e}") from e


def get_changed_files(repo_path: Path) -> list[str]:
    """Get list of files with uncommitted changes.

    Args:
        repo_path: Path to the git repository

    Returns:
        List of file paths with changes

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise GitError(f"git status failed: {result.stderr}")

        # Parse porcelain output (format: "XY filename")
        # X and Y are status characters, followed by a space, then filename
        changed_files = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and len(line) > 2:
                # Status format is "XY filename" where X and Y are single chars
                # So we skip first 2 chars (status) and any spaces after
                # Find the first non-space character after position 2
                filename = line[2:].lstrip()
                if filename:
                    changed_files.append(filename)

        return changed_files

    except subprocess.TimeoutExpired as e:
        raise GitError(f"git status timed out: {e}") from e
    except Exception as e:
        raise GitError(f"Failed to get changed files: {e}") from e


def get_diff_stat(repo_path: Path) -> str:
    """Get a short summary of changes (diff statistics).

    Args:
        repo_path: Path to the git repository

    Returns:
        Diff stat summary string (e.g., "3 files changed, 45 insertions(+), 12 deletions(-)")

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise GitError(f"git diff --stat failed: {result.stderr}")

        # Return the summary line (last line of output)
        lines = result.stdout.strip().split("\n")
        if lines and lines[-1].strip():
            return lines[-1].strip()
        return "No changes"

    except subprocess.TimeoutExpired as e:
        raise GitError(f"git diff --stat timed out: {e}") from e
    except Exception as e:
        raise GitError(f"Failed to get diff stat: {e}") from e
