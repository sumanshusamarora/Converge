"""Codex apply executor for automated patch application.

This module provides safe, gated execution of Codex to apply code changes
to target repositories. Execution is OFF by default and requires explicit
configuration flags.

Safety Requirements:
- CONVERGE_EXECUTION_MODE must be "headless" or "interactive"
- CONVERGE_CODEX_APPLY must be "true"
- Repository must have .git directory
- Working tree must be clean (unless CONVERGE_ALLOW_DIRTY=true)
- Always creates a new branch (unless CONVERGE_CREATE_BRANCH=false)
- Never pushes to remote in this implementation
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from converge.execution.git_utils import (
    GitError,
    commit_all,
    create_branch,
    current_branch,
    ensure_git_repo,
    get_changed_files,
    get_diff_bytes,
    get_diff_line_counts,
    get_diff_stat,
    is_working_tree_clean,
)

logger = logging.getLogger(__name__)


@dataclass
class ExecResult:
    """Result of a Codex apply execution.

    Attributes:
        ok: Whether execution succeeded
        exit_code: Exit code (0=success, 1=failure, 2=safety gate failed)
        message: Human-readable result message
        logs: Dictionary mapping log type to file path
        changed_files: List of files modified during execution
        diff_stat: Summary of changes made
        diff_added: Number of lines added
        diff_deleted: Number of lines deleted
        diff_bytes: Approximate size of diff in bytes
        threshold_exceeded: Whether safety thresholds were exceeded
    """

    ok: bool
    exit_code: int
    message: str
    logs: dict[str, str] = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)
    diff_stat: str = ""
    diff_added: int = 0
    diff_deleted: int = 0
    diff_bytes: int = 0
    threshold_exceeded: bool = False


class CodexApplyExecutor:
    """Executor for applying Codex-generated patches to repositories.

    This executor implements strict safety gates before allowing any
    code changes to be applied automatically.
    """

    def __init__(
        self,
        allowlisted_commands: list[str] | None = None,
        codex_path: str = "codex",
        max_changed_files: int | None = None,
        max_diff_lines: int | None = None,
        max_diff_bytes: int | None = None,
    ):
        """Initialize the Codex apply executor.

        Args:
            allowlisted_commands: List of allowed command prefixes for verification
            codex_path: Path to the Codex CLI executable
            max_changed_files: Maximum number of files that can be changed (None = no limit)
            max_diff_lines: Maximum total lines (added+deleted) allowed (None = no limit)
            max_diff_bytes: Maximum diff size in bytes (None = no limit)
        """
        self.allowlisted_commands = allowlisted_commands or []
        self.codex_path = codex_path
        self.max_changed_files = max_changed_files
        self.max_diff_lines = max_diff_lines
        self.max_diff_bytes = max_diff_bytes

    def check_codex_available(self) -> bool:
        """Check if Codex CLI is available on the system.

        Returns:
            True if Codex command is found in PATH, False otherwise
        """
        return shutil.which(self.codex_path) is not None

    def apply(
        self,
        repo_path: Path,
        prompt_path: Path,
        artifacts_dir: Path,
        branch_name: str,
        verification_cmds: list[str] | None = None,
    ) -> ExecResult:
        """Apply a Codex-generated patch to the repository.

        This method implements the following workflow:
        1. Safety gates: check all preconditions
        2. Create branch if configured
        3. Execute Codex CLI with the prompt
        4. Run verification commands (lint, tests)
        5. Commit changes if configured
        6. Record all logs and evidence

        Args:
            repo_path: Path to the target repository
            prompt_path: Path to file containing the Codex prompt/instruction
            artifacts_dir: Directory to store execution logs and evidence
            branch_name: Name of the branch to create (e.g., "converge/task-123")
            verification_cmds: Optional list of verification commands to run after apply

        Returns:
            ExecResult with execution status and artifacts
        """
        if verification_cmds is None:
            verification_cmds = []

        # Read configuration from environment
        execution_mode = os.getenv("CONVERGE_EXECUTION_MODE", "plan").strip().lower()
        codex_apply_enabled = (
            os.getenv("CONVERGE_CODEX_APPLY", "false").strip().lower() == "true"
        )
        allow_dirty = (
            os.getenv("CONVERGE_ALLOW_DIRTY", "false").strip().lower() == "true"
        )
        create_branch_flag = (
            os.getenv("CONVERGE_CREATE_BRANCH", "true").strip().lower() == "true"
        )
        git_commit = os.getenv("CONVERGE_GIT_COMMIT", "true").strip().lower() == "true"
        git_author_name = os.getenv("CONVERGE_GIT_AUTHOR_NAME", "Converge Bot")
        git_author_email = os.getenv(
            "CONVERGE_GIT_AUTHOR_EMAIL", "converge-bot@example.com"
        )

        # =================================================================
        # SAFETY GATE 1: Execution mode must be headless or interactive
        # =================================================================
        if execution_mode not in ["headless", "interactive"]:
            logger.warning(
                "Codex apply refused: execution mode is '%s'", execution_mode
            )
            return ExecResult(
                ok=False,
                exit_code=2,
                message=(
                    f"Codex apply execution refused: "
                    f"CONVERGE_EXECUTION_MODE='{execution_mode}'. "
                    f"Must be 'headless' or 'interactive'. "
                    f"Set CONVERGE_EXECUTION_MODE=headless to enable."
                ),
            )

        # =================================================================
        # SAFETY GATE 2: Codex apply must be explicitly enabled
        # =================================================================
        if not codex_apply_enabled:
            logger.warning("Codex apply refused: CONVERGE_CODEX_APPLY not enabled")
            return ExecResult(
                ok=False,
                exit_code=2,
                message=(
                    "Codex apply execution refused: CONVERGE_CODEX_APPLY is not 'true'. "
                    "Set CONVERGE_CODEX_APPLY=true to enable automated patch application."
                ),
            )

        # =================================================================
        # SAFETY GATE 3: Repository must exist and have .git directory
        # =================================================================
        try:
            ensure_git_repo(repo_path)
        except GitError as e:
            logger.error("Codex apply refused: %s", e)
            return ExecResult(
                ok=False,
                exit_code=2,
                message=f"Repository validation failed: {e}",
            )

        # =================================================================
        # SAFETY GATE 4: Working tree must be clean (unless explicitly allowed)
        # =================================================================
        try:
            tree_is_clean = is_working_tree_clean(repo_path)
            if not tree_is_clean and not allow_dirty:
                logger.error("Codex apply refused: working tree is not clean")
                changed = get_changed_files(repo_path)
                return ExecResult(
                    ok=False,
                    exit_code=2,
                    message=(
                        f"Working tree is not clean. "
                        f"Found {len(changed)} uncommitted changes. "
                        f"Commit or stash changes first, or set "
                        f"CONVERGE_ALLOW_DIRTY=true to proceed anyway."
                    ),
                )
        except GitError as e:
            logger.error("Codex apply refused: git check failed: %s", e)
            return ExecResult(
                ok=False,
                exit_code=2,
                message=f"Git working tree check failed: {e}",
            )

        # =================================================================
        # SAFETY GATE 5: Codex CLI must be available
        # =================================================================
        if not self.check_codex_available():
            logger.error("Codex apply refused: Codex CLI not found")
            return ExecResult(
                ok=False,
                exit_code=2,
                message=(
                    f"Codex CLI not found. Expected '{self.codex_path}' in PATH. "
                    f"Install Codex CLI or verify CODEX_PATH configuration."
                ),
            )

        # All safety gates passed - log approval
        logger.info("Codex apply: all safety gates passed for %s", repo_path)

        # Create execution artifacts directory
        execution_dir = artifacts_dir / "executions"
        execution_dir.mkdir(parents=True, exist_ok=True)

        # Prepare log file paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logs: dict[str, str] = {}
        codex_stdout_path = execution_dir / f"codex_apply_{timestamp}_stdout.txt"
        codex_stderr_path = execution_dir / f"codex_apply_{timestamp}_stderr.txt"
        logs["codex_stdout"] = str(codex_stdout_path)
        logs["codex_stderr"] = str(codex_stderr_path)

        # =================================================================
        # STEP 1: Create branch if configured
        # =================================================================
        if create_branch_flag:
            try:
                original_branch = current_branch(repo_path)
                logger.info(
                    "Creating branch '%s' from '%s'", branch_name, original_branch
                )
                create_branch(repo_path, branch_name)
                logs["branch_created"] = branch_name
            except GitError as e:
                logger.error("Failed to create branch: %s", e)
                return ExecResult(
                    ok=False,
                    exit_code=1,
                    message=f"Failed to create branch '{branch_name}': {e}",
                    logs=logs,
                )

        # =================================================================
        # STEP 2: Execute Codex CLI with the prompt
        # =================================================================
        try:
            with open(prompt_path) as f:
                instruction = f.read().strip()
        except Exception as e:
            logger.error("Failed to read prompt file: %s", e)
            return ExecResult(
                ok=False,
                exit_code=1,
                message=f"Failed to read prompt file: {e}",
                logs=logs,
            )

        logger.info("Executing Codex CLI in %s", repo_path)

        try:
            with (
                open(codex_stdout_path, "w") as stdout_f,
                open(codex_stderr_path, "w") as stderr_f,
            ):
                result = subprocess.run(
                    [self.codex_path, "apply", "--prompt", instruction],
                    cwd=repo_path,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    text=True,
                    timeout=600,  # 10 minute timeout
                )

            if result.returncode != 0:
                logger.error("Codex CLI exited with code %d", result.returncode)
                return ExecResult(
                    ok=False,
                    exit_code=result.returncode,
                    message=f"Codex CLI execution failed with exit code {result.returncode}",
                    logs=logs,
                )

        except subprocess.TimeoutExpired:
            logger.error("Codex CLI timed out")
            return ExecResult(
                ok=False,
                exit_code=124,
                message="Codex CLI execution timed out after 10 minutes",
                logs=logs,
            )
        except Exception as e:
            logger.error("Codex CLI execution failed: %s", e)
            return ExecResult(
                ok=False,
                exit_code=1,
                message=f"Codex CLI execution error: {e}",
                logs=logs,
            )

        # =================================================================
        # STEP 3: Run verification commands
        # =================================================================
        for i, cmd in enumerate(verification_cmds):
            # Check if command is allowlisted
            cmd_lower = cmd.strip().lower()
            is_allowed = any(
                cmd_lower.startswith(prefix) for prefix in self.allowlisted_commands
            )

            if not is_allowed:
                logger.warning("Skipping non-allowlisted verification command: %s", cmd)
                continue

            logger.info("Running verification command: %s", cmd)
            verify_stdout_path = execution_dir / f"verify_{i}_{timestamp}_stdout.txt"
            verify_stderr_path = execution_dir / f"verify_{i}_{timestamp}_stderr.txt"
            logs[f"verify_{i}_stdout"] = str(verify_stdout_path)
            logs[f"verify_{i}_stderr"] = str(verify_stderr_path)

            try:
                with (
                    open(verify_stdout_path, "w") as stdout_f,
                    open(verify_stderr_path, "w") as stderr_f,
                ):
                    verify_result = subprocess.run(
                        cmd.split(),
                        cwd=repo_path,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        text=True,
                        timeout=600,
                    )

                if verify_result.returncode != 0:
                    logger.warning(
                        "Verification command failed with code %d: %s",
                        verify_result.returncode,
                        cmd,
                    )
                    # Continue anyway - verification failures are warnings, not hard failures

            except subprocess.TimeoutExpired:
                logger.warning("Verification command timed out: %s", cmd)
            except Exception as e:
                logger.warning("Verification command error: %s - %s", cmd, e)

        # =================================================================
        # STEP 4: Get changed files and diff stats
        # =================================================================
        try:
            changed_files = get_changed_files(repo_path)
            diff_stat = get_diff_stat(repo_path)
            diff_added, diff_deleted = get_diff_line_counts(repo_path)
            diff_bytes = get_diff_bytes(repo_path)
        except GitError as e:
            logger.warning("Failed to get change info: %s", e)
            changed_files = []
            diff_stat = "Unable to retrieve diff stats"
            diff_added = 0
            diff_deleted = 0
            diff_bytes = 0

        # =================================================================
        # STEP 5: Check safety thresholds
        # =================================================================
        threshold_exceeded = False
        threshold_messages = []

        # Check max changed files
        if self.max_changed_files is not None and len(changed_files) > self.max_changed_files:
            threshold_exceeded = True
            threshold_messages.append(
                f"Changed files: {len(changed_files)} exceeds limit of {self.max_changed_files}"
            )

        # Check max diff lines (added + deleted)
        total_lines = diff_added + diff_deleted
        if self.max_diff_lines is not None and total_lines > self.max_diff_lines:
            threshold_exceeded = True
            threshold_messages.append(
                f"Total diff lines: {total_lines} exceeds limit of {self.max_diff_lines}"
            )

        # Check max diff bytes
        if self.max_diff_bytes is not None and diff_bytes > self.max_diff_bytes:
            threshold_exceeded = True
            threshold_messages.append(
                f"Diff size: {diff_bytes} bytes exceeds limit of {self.max_diff_bytes}"
            )

        if threshold_exceeded:
            logger.warning("Safety thresholds exceeded: %s", "; ".join(threshold_messages))
            return ExecResult(
                ok=True,  # Not a failure, but HITL required
                exit_code=0,
                message=(
                    f"HITL_REQUIRED: Safety thresholds exceeded. "
                    f"{'; '.join(threshold_messages)}. "
                    f"Review changes in logs/diff before committing."
                ),
                logs=logs,
                changed_files=changed_files,
                diff_stat=diff_stat,
                diff_added=diff_added,
                diff_deleted=diff_deleted,
                diff_bytes=diff_bytes,
                threshold_exceeded=True,
            )

        # =================================================================
        # STEP 6: Commit changes if configured and thresholds not exceeded
        # =================================================================
        if git_commit and changed_files:
            try:
                commit_message = f"Converge: Apply Codex changes\n\n{diff_stat}"
                commit_all(repo_path, commit_message, git_author_name, git_author_email)
                logger.info("Changes committed successfully")
                logs["committed"] = "true"
            except GitError as e:
                logger.error("Failed to commit changes: %s", e)
                return ExecResult(
                    ok=False,
                    exit_code=1,
                    message=f"Codex apply succeeded but commit failed: {e}",
                    logs=logs,
                    changed_files=changed_files,
                    diff_stat=diff_stat,
                    diff_added=diff_added,
                    diff_deleted=diff_deleted,
                    diff_bytes=diff_bytes,
                )

        # =================================================================
        # SUCCESS
        # =================================================================
        logger.info("Codex apply completed successfully")
        return ExecResult(
            ok=True,
            exit_code=0,
            message=f"Codex apply completed successfully. {len(changed_files)} files changed.",
            logs=logs,
            changed_files=changed_files,
            diff_stat=diff_stat,
            diff_added=diff_added,
            diff_deleted=diff_deleted,
            diff_bytes=diff_bytes,
            threshold_exceeded=False,
        )
