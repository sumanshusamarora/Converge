"""Tests for agent execution policy."""

import pytest

from converge.agents.policy import (
    ExecutionMode,
    ExecutionPolicy,
    get_default_allowlist,
    policy_from_env_and_request,
)


def test_execution_mode_enum() -> None:
    """Test ExecutionMode enum values."""
    assert ExecutionMode.PLAN_ONLY.value == "plan_only"
    assert ExecutionMode.EXECUTE_ALLOWED.value == "execute_allowed"


def test_execution_policy_defaults() -> None:
    """Test ExecutionPolicy with default values."""
    policy = ExecutionPolicy(mode=ExecutionMode.PLAN_ONLY)

    assert policy.mode == ExecutionMode.PLAN_ONLY
    assert policy.allowlisted_commands == []
    assert policy.require_git_clean is False
    assert policy.create_branch is True
    assert policy.branch_prefix == "converge/"


def test_execution_policy_custom_values() -> None:
    """Test ExecutionPolicy with custom values."""
    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest", "ruff"],
        require_git_clean=True,
        create_branch=False,
        branch_prefix="custom/",
    )

    assert policy.mode == ExecutionMode.EXECUTE_ALLOWED
    assert policy.allowlisted_commands == ["pytest", "ruff"]
    assert policy.require_git_clean is True
    assert policy.create_branch is False
    assert policy.branch_prefix == "custom/"


def test_is_command_allowed_empty_allowlist() -> None:
    """Test is_command_allowed with empty allowlist."""
    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED, allowlisted_commands=[]
    )

    assert policy.is_command_allowed("pytest") is False
    assert policy.is_command_allowed("ruff check .") is False


def test_is_command_allowed_with_allowlist() -> None:
    """Test is_command_allowed with commands in allowlist."""
    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest", "ruff", "git"],
    )

    # Exact matches
    assert policy.is_command_allowed("pytest") is True
    assert policy.is_command_allowed("ruff") is True
    assert policy.is_command_allowed("git") is True

    # Prefix matches
    assert policy.is_command_allowed("pytest tests/") is True
    assert policy.is_command_allowed("ruff check .") is True
    assert policy.is_command_allowed("git status") is True

    # Case insensitive
    assert policy.is_command_allowed("PYTEST") is True
    assert policy.is_command_allowed("Ruff Check .") is True

    # Not in allowlist
    assert policy.is_command_allowed("npm install") is False
    assert policy.is_command_allowed("rm -rf /") is False


def test_is_command_allowed_whitespace() -> None:
    """Test is_command_allowed handles whitespace correctly."""
    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest"],
    )

    assert policy.is_command_allowed("  pytest  ") is True
    assert policy.is_command_allowed("\tpytest\n") is True


def test_get_default_allowlist() -> None:
    """Test that get_default_allowlist returns expected commands."""
    allowlist = get_default_allowlist()

    assert "pytest" in allowlist
    assert "ruff" in allowlist
    assert "black" in allowlist
    assert "mypy" in allowlist
    assert "npm" in allowlist
    assert "git" in allowlist
    assert "python" in allowlist
    assert "pip" in allowlist

    # Should not include dangerous commands
    assert "rm" not in allowlist
    assert "sudo" not in allowlist


def test_policy_from_env_plan_only_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that policy defaults to PLAN_ONLY when env not set."""
    monkeypatch.delenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", raising=False)

    policy = policy_from_env_and_request()

    assert policy.mode == ExecutionMode.PLAN_ONLY


def test_policy_from_env_requires_both_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that execution requires BOTH env and allow_exec flag."""
    # Only env set
    monkeypatch.setenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", "true")
    policy = policy_from_env_and_request(cli_flags={})
    assert policy.mode == ExecutionMode.PLAN_ONLY

    # Only flag set
    monkeypatch.setenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", "false")
    policy = policy_from_env_and_request(cli_flags={"allow_exec": True})
    assert policy.mode == ExecutionMode.PLAN_ONLY

    # Both set
    monkeypatch.setenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", "true")
    policy = policy_from_env_and_request(cli_flags={"allow_exec": True})
    assert policy.mode == ExecutionMode.EXECUTE_ALLOWED


def test_policy_from_env_with_task_allow_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that task metadata allow_exec flag is respected."""
    monkeypatch.setenv("CONVERGE_CODING_AGENT_EXEC_ENABLED", "true")

    policy = policy_from_env_and_request(task_request_metadata={"allow_exec": True})

    assert policy.mode == ExecutionMode.EXECUTE_ALLOWED


def test_policy_from_env_custom_env_dict() -> None:
    """Test policy creation with custom env dict."""
    custom_env = {"CONVERGE_CODING_AGENT_EXEC_ENABLED": "true"}

    policy = policy_from_env_and_request(
        env=custom_env,
        cli_flags={"allow_exec": True},
    )

    assert policy.mode == ExecutionMode.EXECUTE_ALLOWED


def test_policy_from_env_safety_flags() -> None:
    """Test that safety flags are passed through to policy."""
    policy = policy_from_env_and_request(
        cli_flags={
            "allow_exec": False,
            "require_git_clean": True,
            "create_branch": False,
            "branch_prefix": "test/",
        }
    )

    assert policy.require_git_clean is True
    assert policy.create_branch is False
    assert policy.branch_prefix == "test/"


def test_policy_from_env_custom_allowlist() -> None:
    """Test that custom allowlist is passed through to policy."""
    custom_allowlist = ["pytest", "custom-command"]

    policy = policy_from_env_and_request(
        cli_flags={"allowlisted_commands": custom_allowlist}
    )

    assert policy.allowlisted_commands == custom_allowlist


def test_policy_from_env_uses_default_allowlist() -> None:
    """Test that default allowlist is used when not specified."""
    policy = policy_from_env_and_request()

    default_allowlist = get_default_allowlist()
    assert policy.allowlisted_commands == default_allowlist


def test_policy_from_env_case_insensitive_enabled() -> None:
    """Test that CONVERGE_CODING_AGENT_EXEC_ENABLED is case-insensitive."""
    test_cases = ["true", "TRUE", "True", "TrUe"]

    for value in test_cases:
        env = {"CONVERGE_CODING_AGENT_EXEC_ENABLED": value}
        policy = policy_from_env_and_request(env=env, cli_flags={"allow_exec": True})
        assert policy.mode == ExecutionMode.EXECUTE_ALLOWED

    # Test false values
    false_values = ["false", "FALSE", "False", "0", "no", ""]
    for value in false_values:
        env = {"CONVERGE_CODING_AGENT_EXEC_ENABLED": value}
        policy = policy_from_env_and_request(env=env, cli_flags={"allow_exec": True})
        assert policy.mode == ExecutionMode.PLAN_ONLY
