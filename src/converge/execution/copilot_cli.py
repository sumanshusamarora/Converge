"""GitHub Copilot CLI executor for Converge.

This module provides interactive execution via GitHub Copilot CLI.
Copilot CLI execution requires TTY and must never run headless.
"""

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CmdResult:
    """Result of a command execution.

    Attributes:
        success: Whether the command succeeded
        exit_code: Command exit code
        stdout: Standard output
        stderr: Standard error
        artifacts_saved: List of artifact file paths created
    """

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    artifacts_saved: list[str]


def is_tty() -> bool:
    """Check if stdin and stdout are TTY devices.

    Returns:
        True if both stdin and stdout are TTY, False otherwise
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def check_copilot_available() -> bool:
    """Check if GitHub Copilot CLI is available.

    Checks for:
    1. gh CLI is installed
    2. gh copilot extension is available

    Returns:
        True if Copilot CLI is available, False otherwise
    """
    # Check if gh is installed
    if shutil.which("gh") is None:
        logger.debug("gh CLI not found in PATH")
        return False

    # Check if gh copilot command is available
    try:
        result = subprocess.run(
            ["gh", "copilot", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            logger.debug("gh copilot is available")
            return True
        else:
            logger.debug("gh copilot command failed: %s", result.stderr)
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Failed to check gh copilot availability: %s", e)
        return False


class CopilotCliExecutor:
    """Executor for GitHub Copilot CLI in interactive mode.

    This executor shells out to `gh copilot` to propose or apply changes.
    It requires TTY and must never run in headless mode.
    """

    def run_plan(
        self,
        repo_path: Path,
        prompt_path: Path,
        artifacts_dir: Path,
    ) -> CmdResult:
        """Execute a plan using GitHub Copilot CLI.

        This method runs gh copilot in interactive mode to propose changes
        based on the provided prompt. It captures output to artifacts.

        Args:
            repo_path: Path to the repository
            prompt_path: Path to file containing the prompt
            artifacts_dir: Directory to save execution artifacts

        Returns:
            CmdResult with execution outcome and artifacts

        Raises:
            RuntimeError: If TTY is not available or Copilot CLI is not installed
        """
        if not is_tty():
            raise RuntimeError("Copilot CLI execution requires TTY. Cannot run in headless mode.")

        if not check_copilot_available():
            raise RuntimeError(
                "GitHub Copilot CLI (gh copilot) is not available. "
                "Install with: gh extension install github/gh-copilot"
            )

        # Ensure artifacts directory exists
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        executions_dir = artifacts_dir / "executions"
        executions_dir.mkdir(parents=True, exist_ok=True)

        # Read the prompt
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.error("Failed to read prompt file: %s", e)
            return CmdResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr=f"Failed to read prompt: {e}",
                artifacts_saved=[],
            )

        # Save prompt to artifacts
        prompt_artifact = executions_dir / "copilot_prompt.txt"
        try:
            prompt_artifact.write_text(prompt_text, encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to save prompt artifact: %s", e)

        # For safety, we use `gh copilot suggest` which is interactive
        # and allows user to review before applying changes.
        # We pass the prompt as stdin to suggest a shell command or explanation.
        logger.info(
            "Running gh copilot suggest in %s with prompt from %s",
            repo_path,
            prompt_path,
        )

        try:
            # Use gh copilot suggest for interactive proposal
            # Note: This is a safe command that doesn't automatically apply changes
            result = subprocess.run(
                ["gh", "copilot", "suggest", prompt_text],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            # Save stdout and stderr to artifacts
            stdout_artifact = executions_dir / "copilot_stdout.txt"
            stderr_artifact = executions_dir / "copilot_stderr.txt"

            artifacts_saved = [str(prompt_artifact)]

            try:
                stdout_artifact.write_text(result.stdout, encoding="utf-8")
                artifacts_saved.append(str(stdout_artifact))
            except OSError as e:
                logger.warning("Failed to save stdout artifact: %s", e)

            try:
                stderr_artifact.write_text(result.stderr, encoding="utf-8")
                artifacts_saved.append(str(stderr_artifact))
            except OSError as e:
                logger.warning("Failed to save stderr artifact: %s", e)

            logger.info(
                "gh copilot suggest completed with exit code %d",
                result.returncode,
            )

            return CmdResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                artifacts_saved=artifacts_saved,
            )

        except subprocess.TimeoutExpired:
            logger.error("gh copilot suggest timed out after 60 seconds")
            return CmdResult(
                success=False,
                exit_code=124,
                stdout="",
                stderr="Command timed out after 60 seconds",
                artifacts_saved=[str(prompt_artifact)],
            )
        except (FileNotFoundError, OSError) as e:
            logger.error("Failed to run gh copilot: %s", e)
            return CmdResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr=f"Failed to run gh copilot: {e}",
                artifacts_saved=[str(prompt_artifact)],
            )
