"""Execution policy and capability model for Converge agents.

This module defines the execution policy that controls when and how
agents can execute commands, with safety checks and allowlists.

DEPRECATED: This module has been moved to converge.execution.policy.
Import from there instead. This wrapper is maintained for backward compatibility.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Import from new location for backward compatibility
from converge.execution.policy import (
    get_default_allowlist as _get_default_allowlist,
)


# Re-export with old names for backward compatibility
class ExecutionMode(str, Enum):
    """Agent execution mode.

    DEPRECATED: Use converge.execution.policy.ExecutionMode instead.

    Note: This enum maintains backward compatibility with the old
    PLAN_ONLY and EXECUTE_ALLOWED values while the new module
    uses PLAN_ONLY, EXECUTE_INTERACTIVE, and EXECUTE_HEADLESS.
    """

    PLAN_ONLY = "plan_only"
    EXECUTE_ALLOWED = "execute_allowed"


@dataclass
class ExecutionPolicy:
    """Policy controlling agent execution capabilities.

    DEPRECATED: Use converge.execution.policy.ExecutionPolicy instead.

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
        return any(command_lower.startswith(prefix) for prefix in self.allowlisted_commands)


def get_default_allowlist() -> list[str]:
    """Return the default command allowlist.

    DEPRECATED: Use converge.execution.policy.get_default_allowlist instead.

    Returns:
        List of allowed command prefixes
    """
    return _get_default_allowlist()


def policy_from_env_and_request(
    env: dict[str, str] | None = None,
    task_request_metadata: dict[str, Any] | None = None,
    cli_flags: dict[str, Any] | None = None,
) -> ExecutionPolicy:
    """Create an ExecutionPolicy from environment, task metadata, and CLI flags.

    DEPRECATED: Use converge.execution.policy.policy_from_env_and_flags instead.

    Execution is allowed only when BOTH:
    - env CONVERGE_CODEX_ENABLED=true
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

    # Check if Codex execution is enabled via environment
    codex_enabled = env.get("CONVERGE_CODEX_ENABLED", "false").lower() == "true"

    # Check if execution is explicitly allowed via task or CLI flags
    task_allow_exec = task_request_metadata.get("allow_exec", False)
    cli_allow_exec = cli_flags.get("allow_exec", False)
    allow_exec_flag = task_allow_exec or cli_allow_exec

    # Execution is allowed only if BOTH conditions are met
    if codex_enabled and allow_exec_flag:
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
