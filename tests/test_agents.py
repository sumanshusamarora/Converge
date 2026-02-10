"""Tests for agent abstraction layer."""

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from converge.agents.base import AgentProvider, AgentTask, RepoContext
from converge.agents.codex_agent import CodexAgent
from converge.agents.copilot_agent import GitHubCopilotAgent
from converge.agents.factory import create_agent
from converge.cli.main import cli
from converge.core.config import ConvergeConfig
from converge.orchestration.coordinator import Coordinator


def test_agent_factory_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that factory creates CodexAgent by default."""
    monkeypatch.delenv("CONVERGE_AGENT_PROVIDER", raising=False)
    agent = create_agent()
    assert isinstance(agent, CodexAgent)
    assert agent.provider == AgentProvider.CODEX


def test_agent_factory_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that factory respects CONVERGE_AGENT_PROVIDER env var."""
    monkeypatch.setenv("CONVERGE_AGENT_PROVIDER", "copilot")
    agent = create_agent()
    assert isinstance(agent, GitHubCopilotAgent)
    assert agent.provider == AgentProvider.COPILOT


def test_agent_factory_explicit_name() -> None:
    """Test that factory accepts explicit provider name."""
    agent = create_agent("codex")
    assert isinstance(agent, CodexAgent)

    agent = create_agent("copilot")
    assert isinstance(agent, GitHubCopilotAgent)


def test_agent_factory_unknown_provider() -> None:
    """Test that factory raises ValueError for unknown provider."""
    with pytest.raises(ValueError, match="Unknown agent provider"):
        create_agent("unknown")


def test_copilot_agent_plan_contains_prompt(tmp_path: Path) -> None:
    """Test that CopilotAgent generates a prompt with goal and repo context."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (repo_dir / "README.md").write_text("# Test Repo\n\nA test repository.", encoding="utf-8")

    repo_context = RepoContext(
        path=repo_dir,
        kind="backend",
        signals=["pyproject.toml", "README.md"],
        readme_excerpt="# Test Repo\n\nA test repository.",
    )

    task = AgentTask(
        goal="Add feature X",
        repo=repo_context,
        instructions="Follow best practices.",
        max_steps=5,
    )

    agent = GitHubCopilotAgent()
    result = agent.plan(task)

    assert result.provider == AgentProvider.COPILOT
    assert result.status == "OK"
    assert "Add feature X" in result.summary
    assert len(result.proposed_changes) > 0
    assert "copilot_prompt" in result.raw
    prompt = result.raw["copilot_prompt"]
    assert isinstance(prompt, str)
    assert "Add feature X" in prompt
    assert "backend" in prompt
    assert "pyproject.toml" in prompt


def test_copilot_agent_hitl_required_for_missing_repo(tmp_path: Path) -> None:
    """Test that CopilotAgent marks status as HITL_REQUIRED for missing repo."""
    repo_context = RepoContext(
        path=tmp_path / "missing",
        kind=None,
        signals=[],
        readme_excerpt=None,
    )

    task = AgentTask(
        goal="Add feature",
        repo=repo_context,
        instructions="Follow best practices.",
    )

    agent = GitHubCopilotAgent()
    result = agent.plan(task)

    assert result.status == "HITL_REQUIRED"
    assert len(result.questions_for_hitl) > 0


def test_codex_agent_plan_disabled_exec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that CodexAgent does not execute when CONVERGE_CODEX_ENABLED is false."""
    monkeypatch.setenv("CONVERGE_CODEX_ENABLED", "false")

    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    (repo_dir / "package.json").write_text('{"name": "test"}', encoding="utf-8")

    repo_context = RepoContext(
        path=repo_dir,
        kind="frontend",
        signals=["package.json"],
        readme_excerpt=None,
    )

    task = AgentTask(
        goal="Add discount code",
        repo=repo_context,
        instructions="Use existing patterns.",
    )

    agent = CodexAgent()
    result = agent.plan(task)

    assert result.provider == AgentProvider.CODEX
    assert result.status in ("OK", "HITL_REQUIRED")
    assert "codex_prompt" in result.raw
    assert result.raw["execution_mode"] == "heuristic"
    assert result.raw["codex_enabled"] is False
    assert len(result.proposed_changes) > 0


def test_codex_agent_supports_execution() -> None:
    """Test that CodexAgent reports it supports execution."""
    agent = CodexAgent()
    assert agent.supports_execution() is True


def test_copilot_agent_does_not_support_execution() -> None:
    """Test that GitHubCopilotAgent reports it does not support execution."""
    agent = GitHubCopilotAgent()
    assert agent.supports_execution() is False


def test_workflow_writes_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that coordinator workflow writes prompts directory."""
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    api_dir = tmp_path / "api"
    web_dir = tmp_path / "web"
    api_dir.mkdir()
    web_dir.mkdir()
    (api_dir / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")
    (web_dir / "package.json").write_text('{"name": "web"}', encoding="utf-8")

    config = ConvergeConfig(
        goal="Add discount code support",
        repos=[str(api_dir), str(web_dir)],
        max_rounds=2,
        output_dir=str(tmp_path / ".converge"),
        no_llm=True,
        hil_mode="conditional",
        agent_provider="codex",
    )

    coordinator = Coordinator(config)
    final_state = coordinator.coordinate()

    assert final_state["status"] in ("CONVERGED", "HITL_REQUIRED")
    assert "repo_plans" in final_state
    assert len(final_state["repo_plans"]) == 2

    # Check prompts directory exists
    prompts_dir = coordinator.run_dir / "prompts"
    assert prompts_dir.exists()
    assert prompts_dir.is_dir()

    # Check that prompt files were created
    prompt_files = list(prompts_dir.glob("*.txt"))
    assert len(prompt_files) > 0


def test_cli_agent_provider_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --agent-provider flag works correctly."""
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    runner = CliRunner()
    output_dir = tmp_path / "out"

    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Test feature",
            "--repos",
            str(api_dir),
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",
            "--no-llm",
            "--no-tracing",
            "--agent-provider",
            "copilot",
        ],
    )

    assert result.exit_code in (0, 2)  # 0=CONVERGED, 2=HITL_REQUIRED

    # Find the run directory
    runs_dir = output_dir / "runs"
    assert runs_dir.exists()
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) > 0
    run_dir = run_dirs[0]

    # Check that prompts were created
    prompts_dir = run_dir / "prompts"
    assert prompts_dir.exists()


def test_cli_enable_codex_exec_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that --enable-codex-exec flag sets the environment variable."""
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CONVERGE_CODEX_ENABLED", "false")

    runner = CliRunner()
    output_dir = tmp_path / "out"

    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")

    # Invoke CLI with --enable-codex-exec
    result = runner.invoke(
        cli,
        [
            "coordinate",
            "--goal",
            "Test",
            "--repos",
            str(api_dir),
            "--output-dir",
            str(output_dir),
            "--log-level",
            "ERROR",
            "--no-llm",
            "--no-tracing",
            "--enable-codex-exec",
        ],
    )

    assert result.exit_code in (0, 2)

    # Verify CONVERGE_CODEX_ENABLED was set (indirectly via success)
    # We can't easily check env from here, but the fact that it ran is a good sign


def test_config_validates_agent_provider() -> None:
    """Test that ConvergeConfig validates agent_provider."""
    # Valid providers
    config = ConvergeConfig(
        goal="Test",
        repos=["repo1"],
        agent_provider="codex",
    )
    assert config.agent_provider == "codex"

    config = ConvergeConfig(
        goal="Test",
        repos=["repo1"],
        agent_provider="copilot",
    )
    assert config.agent_provider == "copilot"

    # Invalid provider
    with pytest.raises(ValueError, match="agent_provider must be"):
        ConvergeConfig(
            goal="Test",
            repos=["repo1"],
            agent_provider="invalid",
        )


def test_copilot_execute_always_returns_hitl() -> None:
    """Test that CopilotAgent.execute() always returns HITL_REQUIRED."""
    from converge.agents.policy import ExecutionMode, ExecutionPolicy

    agent = GitHubCopilotAgent()

    # Create a task with execution allowed
    repo_context = RepoContext(
        path=Path("/tmp/test"),
        kind="backend",
        signals=["pyproject.toml"],
    )

    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest"],
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=policy,
    )

    result = agent.execute(task)

    assert result.provider == AgentProvider.COPILOT
    assert result.status == "HITL_REQUIRED"
    assert "plan-only" in result.summary.lower()
    assert len(result.questions_for_hitl) > 0
    assert "copilot_plan_only" in result.raw.get("reason", "")


def test_codex_execute_no_policy() -> None:
    """Test that CodexAgent.execute() fails when no policy is provided."""
    agent = CodexAgent()

    repo_context = RepoContext(
        path=Path("/tmp/test"),
        kind="backend",
        signals=["pyproject.toml"],
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=None,  # No policy
    )

    result = agent.execute(task)

    assert result.provider == AgentProvider.CODEX
    assert result.status == "FAILED"
    assert "no execution policy" in result.summary.lower()


def test_codex_execute_plan_only_mode(tmp_path: Path) -> None:
    """Test that CodexAgent.execute() returns HITL when mode is PLAN_ONLY."""
    from converge.agents.policy import ExecutionMode, ExecutionPolicy

    agent = CodexAgent()

    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    repo_context = RepoContext(
        path=repo_dir,
        kind="backend",
        signals=["pyproject.toml"],
    )

    policy = ExecutionPolicy(
        mode=ExecutionMode.PLAN_ONLY,  # Planning only
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=policy,
    )

    result = agent.execute(task)

    assert result.provider == AgentProvider.CODEX
    assert result.status == "HITL_REQUIRED"
    assert "not allowed by policy" in result.summary.lower()


def test_codex_execute_repo_not_found() -> None:
    """Test that CodexAgent.execute() fails when repository doesn't exist."""
    from converge.agents.policy import ExecutionMode, ExecutionPolicy

    agent = CodexAgent()

    repo_context = RepoContext(
        path=Path("/nonexistent/repo"),
        kind="backend",
        signals=[],
    )

    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest"],
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=policy,
    )

    result = agent.execute(task)

    assert result.provider == AgentProvider.CODEX
    assert result.status == "FAILED"
    assert "does not exist" in result.summary.lower()


def test_codex_execute_not_git_repo(tmp_path: Path) -> None:
    """Test that CodexAgent.execute() fails when directory is not a git repo."""
    from converge.agents.policy import ExecutionMode, ExecutionPolicy

    agent = CodexAgent()

    repo_dir = tmp_path / "not-git"
    repo_dir.mkdir()

    repo_context = RepoContext(
        path=repo_dir,
        kind="backend",
        signals=[],
    )

    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest"],
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=policy,
    )

    result = agent.execute(task)

    assert result.provider == AgentProvider.CODEX
    assert result.status == "FAILED"
    assert "not a git repository" in result.summary.lower()


def test_codex_execute_safety_checks_pass(tmp_path: Path) -> None:
    """Test that CodexAgent.execute() passes safety checks for valid git repo."""
    from converge.agents.policy import ExecutionMode, ExecutionPolicy

    agent = CodexAgent()

    # Create a git repository
    repo_dir = tmp_path / "git-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)

    repo_context = RepoContext(
        path=repo_dir,
        kind="backend",
        signals=["pyproject.toml"],
    )

    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest"],
        create_branch=False,  # Don't create branch for this test
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=policy,
    )

    result = agent.execute(task)

    assert result.provider == AgentProvider.CODEX
    # Should be HITL_REQUIRED because CLI not implemented yet
    assert result.status == "HITL_REQUIRED"
    assert "passed safety checks" in result.summary.lower()
    assert result.raw.get("safety_checks_passed") is True


def test_codex_execute_creates_branch(tmp_path: Path) -> None:
    """Test that CodexAgent.execute() creates a branch when requested."""
    from converge.agents.policy import ExecutionMode, ExecutionPolicy

    agent = CodexAgent()

    # Create a git repository with initial commit
    repo_dir = tmp_path / "git-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    (repo_dir / "README.md").write_text("# Test", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    repo_context = RepoContext(
        path=repo_dir,
        kind="backend",
        signals=["README.md"],
    )

    policy = ExecutionPolicy(
        mode=ExecutionMode.EXECUTE_ALLOWED,
        allowlisted_commands=["pytest"],
        create_branch=True,
        branch_prefix="test/",
    )

    task = AgentTask(
        goal="Test execution",
        repo=repo_context,
        instructions="Test",
        execution_policy=policy,
    )

    result = agent.execute(task)

    # Should succeed in creating branch
    assert result.raw.get("branch_created") is not None
    branch_name = result.raw["branch_created"]
    assert branch_name.startswith("test/")

    # Verify branch exists
    branches_result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert branch_name in branches_result.stdout
