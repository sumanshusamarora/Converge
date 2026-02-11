"""Execution policy and capability model for Converge agents.

This module defines the execution policy that controls when and how
agents can execute commands, with safety checks and allowlists.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionMode(str, Enum):
    """Agent execution mode.

    - PLAN_ONLY: Agent produces plans only, no code execution
    - EXECUTE_INTERACTIVE: Agent can execute with TTY (user interaction possible)
    - EXECUTE_HEADLESS: Agent can execute in headless mode (worker/Docker)
    """

    PLAN_ONLY = "plan"
    EXECUTE_INTERACTIVE = "interactive"
    EXECUTE_HEADLESS = "headless"


@dataclass
class ExecutionPolicy:
    """Policy controlling agent execution capabilities.

    Attributes:
        mode: Execution mode (plan, interactive, or headless)
        require_tty: Whether TTY is required for execution
        allowlisted_commands: Command prefixes that are allowed during execution
        require_git_clean: Whether repository must have clean working directory
        create_branch: Whether to create a new branch for changes
        branch_prefix: Prefix for created branches (default: "converge/")
    """

    mode: ExecutionMode
    require_tty: bool = False
    allowlisted_commands: list[str] = field(default_factory=list)
    require_git_clean: bool = True
    create_branch: bool = True
    branch_prefix: str = "converge/"

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed by the policy.

        Args:
            command: The command string to check

        Returns:
            True if command starts with an allowlisted prefix, False otherwise
        """
        if not self.allowlisted_commands:
            return False

        command_lower = command.strip().lower()
        return any(command_lower.startswith(prefix) for prefix in self.allowlisted_commands)


def get_default_allowlist() -> list[str]:
    """Return the default command allowlist.

    Returns:
        List of allowed command prefixes
    """
    return [
        "pytest",
        "ruff",
        "black",
        "mypy",
        "npm",
        "pnpm",
        "yarn",
        "python",
        "pip",
        "git",
        "cat",
        "ls",
        "find",
        "grep",
        "mkdir",
        "touch",
    ]


def policy_from_env_and_flags(
    env: dict[str, str] | None = None,
    cli_flags: dict[str, Any] | None = None,
    task_metadata: dict[str, Any] | None = None,
) -> ExecutionPolicy:
    """Create an ExecutionPolicy from environment variables and flags.

    Policy determination:
    - Mode is determined from CONVERGE_EXECUTION_MODE env var (default: "plan")
    - Interactive mode requires TTY
    - Headless mode does not require TTY
    - Plan mode never requires TTY

    Args:
        env: Environment variables (defaults to os.environ)
        cli_flags: CLI flags (may override env settings)
        task_metadata: Task-specific metadata (may contain execution settings)

    Returns:
        ExecutionPolicy configured based on inputs
    """
    if env is None:
        env = dict(os.environ)

    if cli_flags is None:
        cli_flags = {}

    if task_metadata is None:
        task_metadata = {}

    # Determine execution mode from environment
    mode_str = env.get("CONVERGE_EXECUTION_MODE", "plan").lower()

    if mode_str == "interactive":
        mode = ExecutionMode.EXECUTE_INTERACTIVE
        require_tty = True
    elif mode_str == "headless":
        mode = ExecutionMode.EXECUTE_HEADLESS
        require_tty = False
    else:
        # Default to plan-only
        mode = ExecutionMode.PLAN_ONLY
        require_tty = False

    # Override from CLI flags if provided
    if "execution_mode" in cli_flags:
        flag_mode = cli_flags["execution_mode"]
        if flag_mode == "interactive":
            mode = ExecutionMode.EXECUTE_INTERACTIVE
            require_tty = True
        elif flag_mode == "headless":
            mode = ExecutionMode.EXECUTE_HEADLESS
            require_tty = False
        elif flag_mode == "plan":
            mode = ExecutionMode.PLAN_ONLY
            require_tty = False

    # Get safety flags with defaults
    require_git_clean_str = env.get("CONVERGE_REQUIRE_GIT_CLEAN", "true").lower()
    require_git_clean = require_git_clean_str == "true"

    create_branch_str = env.get("CONVERGE_CREATE_BRANCH", "true").lower()
    create_branch = create_branch_str == "true"

    branch_prefix = env.get("CONVERGE_BRANCH_PREFIX", "converge/")

    # Override from CLI flags
    require_git_clean = cli_flags.get("require_git_clean", require_git_clean)
    create_branch = cli_flags.get("create_branch", create_branch)
    branch_prefix = cli_flags.get("branch_prefix", branch_prefix)

    # Get allowlist from env or use default
    allowlist_str = env.get("CONVERGE_ALLOWLISTED_CMDS", "")
    if allowlist_str:
        allowlist = [cmd.strip() for cmd in allowlist_str.split(",") if cmd.strip()]
    else:
        allowlist = get_default_allowlist()

    # CLI flags can override allowlist
    allowlist = cli_flags.get("allowlisted_commands", allowlist)

    return ExecutionPolicy(
        mode=mode,
        require_tty=require_tty,
        allowlisted_commands=allowlist,
        require_git_clean=require_git_clean,
        create_branch=create_branch,
        branch_prefix=branch_prefix,
    )
