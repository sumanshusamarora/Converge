"""Execution policy and capability model for Converge agents.

This module defines the execution policy that controls when and how
agents can execute commands, with safety checks and allowlists.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionMode(str, Enum):
    """Agent execution mode."""

    PLAN_ONLY = "plan_only"
    EXECUTE_ALLOWED = "execute_allowed"


@dataclass
class ExecutionPolicy:
    """Policy controlling agent execution capabilities.

    Attributes:
        mode: Whether execution is allowed or planning-only
        allowlisted_commands: Command prefixes that are allowed during execution
        require_git_clean: Whether repository must have clean working directory
        create_branch: Whether to create a new branch for changes
        branch_prefix: Prefix for created branches (default: "converge/")
    """

    mode: ExecutionMode
    allowlisted_commands: list[str] = field(default_factory=list)
    require_git_clean: bool = False
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


def policy_from_env_and_request(
    env: dict[str, str] | None = None,
    task_request_metadata: dict[str, Any] | None = None,
    cli_flags: dict[str, Any] | None = None,
) -> ExecutionPolicy:
    """Create an ExecutionPolicy from environment, task metadata, and CLI flags.

    Execution is allowed only when BOTH:
    - env CONVERGE_CODING_AGENT_EXEC_ENABLED=true
    - task/CLI explicit allow-exec flag is set

    Args:
        env: Environment variables (defaults to os.environ)
        task_request_metadata: Task-specific metadata (may contain allow_exec flag)
        cli_flags: CLI flags (may contain allow_exec flag)

    Returns:
        ExecutionPolicy configured based on inputs
    """
    if env is None:
        env = dict(os.environ)

    if task_request_metadata is None:
        task_request_metadata = {}

    if cli_flags is None:
        cli_flags = {}

    # Check if coding-agent execution is enabled via environment
    execution_enabled = (
        env.get("CONVERGE_CODING_AGENT_EXEC_ENABLED", "false").lower() == "true"
    )

    # Check if execution is explicitly allowed via task or CLI flags
    task_allow_exec = task_request_metadata.get("allow_exec", False)
    cli_allow_exec = cli_flags.get("allow_exec", False)
    allow_exec_flag = task_allow_exec or cli_allow_exec

    # Execution is allowed only if BOTH conditions are met
    if execution_enabled and allow_exec_flag:
        mode = ExecutionMode.EXECUTE_ALLOWED
    else:
        mode = ExecutionMode.PLAN_ONLY

    # Get safety flags
    require_git_clean = cli_flags.get("require_git_clean", False)
    create_branch = cli_flags.get("create_branch", True)
    branch_prefix = cli_flags.get("branch_prefix", "converge/")

    # Get allowlist (use default if not specified)
    allowlist = cli_flags.get("allowlisted_commands", get_default_allowlist())

    return ExecutionPolicy(
        mode=mode,
        allowlisted_commands=allowlist,
        require_git_clean=require_git_clean,
        create_branch=create_branch,
        branch_prefix=branch_prefix,
    )
