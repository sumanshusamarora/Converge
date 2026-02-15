"""Execution mode policy for Converge agents.

This module defines the execution policy that controls when and how
agents can execute commands in different modes (plan-only, interactive, headless).
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionMode(str, Enum):
    """Agent execution mode.

    PLAN_ONLY: Agent generates plans without executing commands
    EXECUTE_INTERACTIVE: Agent can execute commands with TTY (interactive mode)
    EXECUTE_HEADLESS: Agent can execute commands without TTY (worker/Docker)
    """

    PLAN_ONLY = "plan"
    EXECUTE_INTERACTIVE = "interactive"
    EXECUTE_HEADLESS = "headless"


@dataclass
class ExecutionPolicy:
    """Policy controlling agent execution capabilities.

    Attributes:
        mode: The execution mode (plan-only, interactive, or headless)
        require_tty: Whether a TTY is required for execution
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
        return any(
            command_lower.startswith(prefix) for prefix in self.allowlisted_commands
        )


def get_default_allowlist() -> list[str]:
    """Return the default command allowlist.

    Returns:
        List of allowed command prefixes
    """
    return [
        "pytest",
        "ruff",
        "python",
        "pip",
        "npm",
        "pnpm",
        "yarn",
        "git",
    ]


def policy_from_env_and_flags(
    env: dict[str, str] | None = None,
    cli_flags: dict[str, Any] | None = None,
    task_metadata: dict[str, Any] | None = None,
) -> ExecutionPolicy:
    """Create an ExecutionPolicy from environment variables, CLI flags, and task metadata.

    Environment variables:
        CONVERGE_EXECUTION_MODE: "plan" (default), "interactive", or "headless"
        CONVERGE_ALLOWLISTED_CMDS: Comma-separated list of allowed command prefixes
        CONVERGE_REQUIRE_GIT_CLEAN: "true" (default) or "false"
        CONVERGE_CREATE_BRANCH: "true" (default) or "false"

    Args:
        env: Environment variables (defaults to os.environ)
        cli_flags: CLI flags that may override environment settings
        task_metadata: Task-specific metadata

    Returns:
        ExecutionPolicy configured based on inputs
    """
    if env is None:
        env = dict(os.environ)

    if cli_flags is None:
        cli_flags = {}

    if task_metadata is None:
        task_metadata = {}

    # Parse execution mode from environment
    mode_str = env.get("CONVERGE_EXECUTION_MODE", "plan").strip().lower()

    if mode_str == "interactive":
        mode = ExecutionMode.EXECUTE_INTERACTIVE
        require_tty = True
    elif mode_str == "headless":
        mode = ExecutionMode.EXECUTE_HEADLESS
        require_tty = False
    else:  # Default to plan
        mode = ExecutionMode.PLAN_ONLY
        require_tty = False

    # Parse allowlisted commands
    allowlist_str = env.get("CONVERGE_ALLOWLISTED_CMDS", "")
    if allowlist_str.strip():
        allowlisted_commands = [
            cmd.strip() for cmd in allowlist_str.split(",") if cmd.strip()
        ]
    else:
        allowlisted_commands = get_default_allowlist()

    # Parse git safety flags
    require_git_clean_str = (
        env.get("CONVERGE_REQUIRE_GIT_CLEAN", "true").strip().lower()
    )
    require_git_clean = require_git_clean_str == "true"

    create_branch_str = env.get("CONVERGE_CREATE_BRANCH", "true").strip().lower()
    create_branch = create_branch_str == "true"

    # Allow CLI flags to override environment settings
    if "mode" in cli_flags:
        mode = cli_flags["mode"]
    if "require_tty" in cli_flags:
        require_tty = cli_flags["require_tty"]
    if "allowlisted_commands" in cli_flags:
        allowlisted_commands = cli_flags["allowlisted_commands"]
    if "require_git_clean" in cli_flags:
        require_git_clean = cli_flags["require_git_clean"]
    if "create_branch" in cli_flags:
        create_branch = cli_flags["create_branch"]

    branch_prefix = cli_flags.get("branch_prefix", "converge/")

    return ExecutionPolicy(
        mode=mode,
        require_tty=require_tty,
        allowlisted_commands=allowlisted_commands,
        require_git_clean=require_git_clean,
        create_branch=create_branch,
        branch_prefix=branch_prefix,
    )
