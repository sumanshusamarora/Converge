"""Copilot CLI executor for interactive plan execution.

This module provides integration with GitHub Copilot CLI for interactive
command execution. Copilot CLI execution REQUIRES a TTY and is designed
for local, interactive use only.
"""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def is_tty() -> bool:
    """Check if running in a TTY environment.

    Returns:
        True if both stdin and stdout are TTY devices, False otherwise
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def check_gh_available() -> bool:
    """Check if GitHub CLI (gh) is available on the system.

    Returns:
        True if gh command is found in PATH, False otherwise
    """
    return shutil.which("gh") is not None


def check_copilot_available() -> bool:
    """Check if GitHub Copilot CLI extension is available.

    Returns:
        True if gh copilot extension is installed and working, False otherwise
    """
    try:
        result = subprocess.run(
            ["gh", "copilot", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@dataclass
class CmdResult:
    """Result of a command execution.

    Attributes:
        ok: Whether the command succeeded
        exit_code: Exit code of the command
        stdout_path: Path to captured stdout (if any)
        stderr_path: Path to captured stderr (if any)
        message: Optional message describing the result
    """

    ok: bool
    exit_code: int
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    message: str | None = None


class CopilotCliExecutor:
    """Executor for GitHub Copilot CLI in interactive mode.

    This executor integrates with GitHub Copilot CLI to provide AI-assisted
    command suggestions and explanations. It REQUIRES a TTY and is designed
    for interactive, local use only.
    """

    def run_plan(
        self,
        repo_path: Path,
        prompt_path: Path,
        artifacts_dir: Path,
        repo_slug: str,
    ) -> CmdResult:
        """Run a plan using GitHub Copilot CLI.

        This method:
        1. Validates TTY availability (required)
        2. Validates GitHub CLI and Copilot extension availability
        3. Executes Copilot CLI command to suggest actions
        4. Captures output to artifacts directory

        Args:
            repo_path: Path to the repository
            prompt_path: Path to file containing the prompt/instruction
            artifacts_dir: Directory to store execution artifacts
            repo_slug: Repository identifier (e.g., "owner/repo")

        Returns:
            CmdResult indicating success or failure
        """
        # Gate 1: Check TTY requirement
        if not is_tty():
            return CmdResult(
                ok=False,
                exit_code=2,
                message=(
                    "Copilot CLI execution requires interactive TTY. "
                    "Rerun locally in an interactive terminal."
                ),
            )

        # Gate 2: Check GitHub CLI availability
        if not check_gh_available():
            return CmdResult(
                ok=False,
                exit_code=2,
                message=(
                    "GitHub CLI (gh) not found. Install from: https://cli.github.com/"
                ),
            )

        # Gate 3: Check Copilot extension availability
        if not check_copilot_available():
            return CmdResult(
                ok=False,
                exit_code=2,
                message=(
                    "GitHub Copilot CLI extension not available. "
                    "Install with: gh extension install github/gh-copilot"
                ),
            )

        # Create execution artifacts directory
        execution_dir = artifacts_dir / "executions"
        execution_dir.mkdir(parents=True, exist_ok=True)

        # Prepare stdout/stderr paths
        stdout_path = (
            execution_dir / f"copilot_cli_{repo_slug.replace('/', '_')}_stdout.txt"
        )
        stderr_path = (
            execution_dir / f"copilot_cli_{repo_slug.replace('/', '_')}_stderr.txt"
        )

        # Read the prompt/instruction
        try:
            with open(prompt_path) as f:
                instruction = f.read().strip()
        except Exception as e:
            return CmdResult(
                ok=False,
                exit_code=1,
                message=f"Failed to read prompt file: {e}",
            )

        # Execute Copilot CLI suggest command
        # Using 'gh copilot suggest' to propose commands based on the instruction
        try:
            with open(stdout_path, "w") as stdout_f, open(stderr_path, "w") as stderr_f:
                result = subprocess.run(
                    ["gh", "copilot", "suggest", "-t", "shell", instruction],
                    cwd=repo_path,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )

            if result.returncode == 0:
                return CmdResult(
                    ok=True,
                    exit_code=0,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    message="Copilot CLI suggestion completed successfully",
                )
            else:
                return CmdResult(
                    ok=False,
                    exit_code=result.returncode,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    message=f"Copilot CLI exited with code {result.returncode}",
                )

        except subprocess.TimeoutExpired:
            return CmdResult(
                ok=False,
                exit_code=124,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                message="Copilot CLI command timed out after 5 minutes",
            )
        except Exception as e:
            return CmdResult(
                ok=False,
                exit_code=1,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                message=f"Copilot CLI execution failed: {e}",
            )
