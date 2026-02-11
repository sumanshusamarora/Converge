"""Execution module for Converge.

This module provides execution policy and executor implementations
for controlled code execution via different providers.
"""

from converge.execution.copilot_cli import (
    CmdResult,
    CopilotCliExecutor,
    check_copilot_available,
    is_tty,
)
from converge.execution.policy import (
    ExecutionMode,
    ExecutionPolicy,
    get_default_allowlist,
    policy_from_env_and_flags,
)

__all__ = [
    "ExecutionMode",
    "ExecutionPolicy",
    "get_default_allowlist",
    "policy_from_env_and_flags",
    "CmdResult",
    "CopilotCliExecutor",
    "check_copilot_available",
    "is_tty",
]
