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
    monkeypatch.delenv("CONVERGE_EXECUTION_MODE", raising=False)

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.PLAN_ONLY
    assert policy.require_tty is False


def test_policy_from_env_interactive_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that interactive mode sets require_tty to True."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "interactive")

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.EXECUTE_INTERACTIVE
    assert policy.require_tty is True


def test_policy_from_env_headless_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that headless mode sets require_tty to False."""
    monkeypatch.setenv("CONVERGE_EXECUTION_MODE", "headless")

    policy = policy_from_env_and_flags()

    assert policy.mode == ExecutionMode.EXECUTE_HEADLESS
    assert policy.require_tty is False


def test_policy_from_env_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that mode parsing is case-insensitive."""
    test_cases = [
        ("INTERACTIVE", ExecutionMode.EXECUTE_INTERACTIVE, True),
        ("Interactive", ExecutionMode.EXECUTE_INTERACTIVE, True),
        ("HEADLESS", ExecutionMode.EXECUTE_HEADLESS, False),
        ("Headless", ExecutionMode.EXECUTE_HEADLESS, False),
        ("PLAN", ExecutionMode.PLAN_ONLY, False),
        ("Plan", ExecutionMode.PLAN_ONLY, False),
    ]

    for mode_str, expected_mode, expected_tty in test_cases:
        monkeypatch.setenv("CONVERGE_EXECUTION_MODE", mode_str)
        policy = policy_from_env_and_flags()
        assert policy.mode == expected_mode
        assert policy.require_tty == expected_tty


def test_policy_from_cli_flags_override() -> None:
    """Test that CLI flags override environment variables."""
    env = {"CONVERGE_EXECUTION_MODE": "plan"}

    # CLI flag overrides env
    policy = policy_from_env_and_flags(
        env=env,
        cli_flags={"execution_mode": "interactive"},
    )

    assert policy.mode == ExecutionMode.EXECUTE_INTERACTIVE
    assert policy.require_tty is True


def test_policy_from_env_safety_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that safety flags are parsed from environment."""
    monkeypatch.setenv("CONVERGE_REQUIRE_GIT_CLEAN", "false")
    monkeypatch.setenv("CONVERGE_CREATE_BRANCH", "false")
    monkeypatch.setenv("CONVERGE_BRANCH_PREFIX", "test/")

    policy = policy_from_env_and_flags()

    assert policy.require_git_clean is False
    assert policy.create_branch is False
    assert policy.branch_prefix == "test/"


def test_policy_from_cli_flags_safety_override() -> None:
    """Test that CLI flags override safety settings."""
    env = {
        "CONVERGE_REQUIRE_GIT_CLEAN": "true",
        "CONVERGE_CREATE_BRANCH": "true",
    }

    policy = policy_from_env_and_flags(
        env=env,
        cli_flags={
            "require_git_clean": False,
            "create_branch": False,
            "branch_prefix": "custom/",
        },
    )

    assert policy.require_git_clean is False
    assert policy.create_branch is False
    assert policy.branch_prefix == "custom/"


def test_policy_from_env_allowlist_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that allowlist is parsed from CSV environment variable."""
    monkeypatch.setenv("CONVERGE_ALLOWLISTED_CMDS", "pytest,ruff,git")

    policy = policy_from_env_and_flags()

    assert policy.allowlisted_commands == ["pytest", "ruff", "git"]


def test_policy_from_env_allowlist_handles_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that allowlist CSV parsing handles whitespace."""
    monkeypatch.setenv("CONVERGE_ALLOWLISTED_CMDS", " pytest , ruff , git ")

    policy = policy_from_env_and_flags()

    assert policy.allowlisted_commands == ["pytest", "ruff", "git"]


def test_policy_from_env_uses_default_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that default allowlist is used when env not set."""
    monkeypatch.delenv("CONVERGE_ALLOWLISTED_CMDS", raising=False)

    policy = policy_from_env_and_flags()

    default_allowlist = get_default_allowlist()
    assert policy.allowlisted_commands == default_allowlist


def test_policy_from_cli_flags_custom_allowlist() -> None:
    """Test that CLI flags can override allowlist."""
    custom_allowlist = ["pytest", "custom-command"]

    policy = policy_from_env_and_flags(cli_flags={"allowlisted_commands": custom_allowlist})

    assert policy.allowlisted_commands == custom_allowlist


def test_policy_defaults_to_git_clean_and_branch() -> None:
    """Test that policy defaults to requiring git clean and creating branch."""
    policy = policy_from_env_and_flags()

    assert policy.require_git_clean is True
    assert policy.create_branch is True
    assert policy.branch_prefix == "converge/"
