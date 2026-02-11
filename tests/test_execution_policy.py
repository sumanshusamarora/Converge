"""Tests for execution policy module."""

import pytest

from converge.execution.policy import (
    ExecutionMode,
    ExecutionPolicy,
    get_default_allowlist,
    policy_from_env_and_flags,
)


def test_execution_mode_enum() -> None:
    """Test ExecutionMode enum values."""
    assert ExecutionMode.PLAN_ONLY.value == "plan"
    assert ExecutionMode.EXECUTE_INTERACTIVE.value == "interactive"
    assert ExecutionMode.EXECUTE_HEADLESS.value == "headless"


def test_execution_policy_defaults() -> None:
    """Test ExecutionPolicy with default values."""
    policy = ExecutionPolicy(mode=ExecutionMode.PLAN_ONLY)

    assert policy.mode == ExecutionMode.PLAN_ONLY
    assert policy.require_tty is False
    assert policy.allowlisted_commands == []
    assert policy.require_git_clean is True
    assert policy.create_branch is True
    assert policy.branch_prefix == "converge/"


def test_execution_policy_custom_values() -> None:
    """Test ExecutionPolicy with custom values."""
    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_INTERACTIVE,
        require_tty=True,
        allowlisted_commands=["pytest", "ruff"],
        require_git_clean=False,
        create_branch=False,
        branch_prefix="custom/",
    )

    assert policy.mode == ExecutionMode.EXECUTE_INTERACTIVE
    assert policy.require_tty is True
    assert policy.allowlisted_commands == ["pytest", "ruff"]
    assert policy.require_git_clean is False
    assert policy.create_branch is False
    assert policy.branch_prefix == "custom/"


def test_is_command_allowed_empty_allowlist() -> None:
    """Test is_command_allowed with empty allowlist."""
    policy = ExecutionPolicy(mode=ExecutionMode.EXECUTE_HEADLESS, allowlisted_commands=[])

    assert policy.is_command_allowed("pytest") is False
    assert policy.is_command_allowed("ruff check .") is False


def test_is_command_allowed_with_allowlist() -> None:
    """Test is_command_allowed with commands in allowlist."""
    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_HEADLESS,
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
        mode=ExecutionMode.EXECUTE_HEADLESS,
        allowlisted_commands=["pytest"],
    )

    assert policy.is_command_allowed("  pytest  ") is True
    assert policy.is_command_allowed("\tpytest\n") is True


def test_get_default_allowlist() -> None:
    """Test that get_default_allowlist returns expected commands."""
    allowlist = get_default_allowlist()

    assert "pytest" in allowlist
    assert "ruff" in allowlist
    assert "npm" in allowlist
    assert "git" in allowlist
    assert "python" in allowlist
    assert "pip" in allowlist

    # Should not include dangerous commands
    assert "rm" not in allowlist
    assert "sudo" not in allowlist


def test_policy_from_env_plan_only_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that policy defaults to PLAN_ONLY when env not set."""
    monkeypatch.delenv("CONVERGE_EXECUTION_MODE", raising=False)

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.PLAN_ONLY
    assert policy.require_tty is False


def test_policy_from_env_interactive_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that interactive mode sets require_tty=True."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "interactive")

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.EXECUTE_INTERACTIVE
    assert policy.require_tty is True


def test_policy_from_env_headless_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that headless mode sets require_tty=False."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.EXECUTE_HEADLESS
    assert policy.require_tty is False


def test_policy_from_env_custom_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that custom allowlist from env is used."""
    monkeypatch.setenv("CONVERGE_ALLOWLISTED_CMDS", "pytest,ruff,custom-cmd")

    policy = policy_from_env_and_flags()

    assert policy.allowlisted_commands == ["pytest", "ruff", "custom-cmd"]


def test_policy_from_env_git_clean_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that require_git_clean flag is read from env."""
    # Default is true
    policy = policy_from_env_and_flags()
    assert policy.require_git_clean is True

    # Set to false
    monkeypatch.setenv("CONVERGE_REQUIRE_GIT_CLEAN", "false")
    policy = policy_from_env_and_flags()
    assert policy.require_git_clean is False


def test_policy_from_env_create_branch_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that create_branch flag is read from env."""
    # Default is true
    policy = policy_from_env_and_flags()
    assert policy.create_branch is True

    # Set to false
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    policy = policy_from_env_and_flags()
    assert policy.create_branch is False


def test_policy_from_env_cli_flags_override() -> None:
    """Test that CLI flags override environment settings."""
    env = {"CONVERGE_EXECUTION_MODE": "plan"}
    cli_flags = {
        "mode": ExecutionMode.EXECUTE_INTERACTIVE,
        "require_tty": True,
        "allowlisted_commands": ["custom"],
        "require_git_clean": False,
        "create_branch": False,
        "branch_prefix": "test/",
    }

    policy = policy_from_env_and_flags(env=env, cli_flags=cli_flags)

    assert policy.mode == ExecutionMode.EXECUTE_INTERACTIVE
    assert policy.require_tty is True
    assert policy.allowlisted_commands == ["custom"]
    assert policy.require_git_clean is False
    assert policy.create_branch is False
    assert policy.branch_prefix == "test/"


def test_policy_from_env_custom_env_dict() -> None:
    """Test policy creation with custom env dict."""
    custom_env = {
        "CONVERGE_EXECUTION_MODE": "headless",
        "CONVERGE_ALLOWLISTED_CMDS": "pytest,ruff",
    }

    policy = policy_from_env_and_flags(env=custom_env)

    assert policy.mode == ExecutionMode.EXECUTE_HEADLESS
    assert policy.allowlisted_commands == ["pytest", "ruff"]


def test_policy_from_env_uses_default_allowlist() -> None:
    """Test that default allowlist is used when not specified."""
    policy = policy_from_env_and_flags()

    default_allowlist = get_default_allowlist()
    assert policy.allowlisted_commands == default_allowlist


def test_policy_from_env_case_insensitive_mode() -> None:
    """Test that CONVERGE_EXECUTION_MODE is case-insensitive."""
    test_cases = [
        ("plan", ExecutionMode.PLAN_ONLY),
        ("PLAN", ExecutionMode.PLAN_ONLY),
        ("Plan", ExecutionMode.PLAN_ONLY),
        ("interactive", ExecutionMode.EXECUTE_INTERACTIVE),
        ("INTERACTIVE", ExecutionMode.EXECUTE_INTERACTIVE),
        ("Interactive", ExecutionMode.EXECUTE_INTERACTIVE),
        ("headless", ExecutionMode.EXECUTE_HEADLESS),
        ("HEADLESS", ExecutionMode.EXECUTE_HEADLESS),
        ("Headless", ExecutionMode.EXECUTE_HEADLESS),
    ]

    for value, expected_mode in test_cases:
        env = {"CONVERGE_EXECUTION_MODE": value}
        policy = policy_from_env_and_flags(env=env)
        assert policy.mode == expected_mode


def test_policy_from_env_whitespace_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that whitespace in env values is handled correctly."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "  interactive  ")
    monkeypatch.setenv("CONVERGE_ALLOWLISTED_CMDS", " pytest , ruff , git ")

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.EXECUTE_INTERACTIVE
    assert policy.allowlisted_commands == ["pytest", "ruff", "git"]


def test_policy_from_env_empty_allowlist_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty allowlist string uses default."""
    monkeypatch.setenv("CONVERGE_ALLOWLISTED_CMDS", "")

    policy = policy_from_env_and_flags()

    assert policy.allowlisted_commands == get_default_allowlist()
