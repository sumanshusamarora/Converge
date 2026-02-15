"""Tests for worker CLI and retry behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from converge.cli.main import cli
from converge.queue.db import DatabaseTaskQueue
from converge.queue.schemas import TaskRequest, TaskStatus
from converge.worker.poller import PollingWorker


def _configure_env(monkeypatch: pytest.MonkeyPatch, database_uri: str) -> None:
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", database_uri)
    monkeypatch.setenv("CONVERGE_QUEUE_BACKEND", "db")
    monkeypatch.setenv("CONVERGE_WORKER_POLL_INTERVAL_SECONDS", "0.01")
    monkeypatch.setenv("CONVERGE_WORKER_BATCH_SIZE", "1")
    monkeypatch.setenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")


def test_worker_cli_once_processes_one_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "worker.db"
    database_uri = f"sqlite:///{db_path}"
    _configure_env(monkeypatch, database_uri)

    queue = DatabaseTaskQueue(database_uri)
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    (fake_repo / "pyproject.toml").write_text(
        "[project]\nname='repo'\n", encoding="utf-8"
    )
    task = queue.enqueue(TaskRequest(goal="Goal", repos=[str(fake_repo)]))

    from converge.orchestration.runner import RunOutcome

    def fake_run_coordinate(
        goal: str,
        repos: list[str],
        max_rounds: int,
        agent_provider: str | None,
        base_output_dir: Path | None,
        hitl_resolution: dict[str, object] | None = None,
        thread_id: str | None = None,
        project_id: str | None = None,
        project_name: str | None = None,
        project_preferences: dict[str, object] | None = None,
        project_instructions: str | None = None,
        custom_instructions: str | None = None,
        execute_immediately: bool = False,
    ) -> RunOutcome:
        artifacts_dir = tmp_path / "cli-artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        return RunOutcome(
            status="CONVERGED",
            summary="ok",
            artifacts_dir=str(artifacts_dir),
            hitl_questions=[],
        )

    monkeypatch.setattr("converge.worker.poller.run_coordinate", fake_run_coordinate)

    runner = CliRunner()
    result = runner.invoke(cli, ["worker", "--once", "--log-level", "ERROR"])

    assert result.exit_code == 0
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.SUCCEEDED


def test_retry_behavior_until_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "retry.db"
    database_uri = f"sqlite:///{db_path}"
    _configure_env(monkeypatch, database_uri)

    queue = DatabaseTaskQueue(database_uri)
    task = queue.enqueue(TaskRequest(goal="Goal", repos=[str(tmp_path)]))

    def raising_run_coordinate(
        goal: str,
        repos: list[str],
        max_rounds: int,
        agent_provider: str | None,
        base_output_dir: Path | None,
        hitl_resolution: dict[str, object] | None = None,
        thread_id: str | None = None,
        project_id: str | None = None,
        project_name: str | None = None,
        project_preferences: dict[str, object] | None = None,
        project_instructions: str | None = None,
        custom_instructions: str | None = None,
        execute_immediately: bool = False,
    ) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr("converge.worker.poller.run_coordinate", raising_run_coordinate)

    worker = PollingWorker(queue=queue, poll_interval_seconds=0.01, batch_size=1)
    worker.run_once()
    first = queue.get(task.id)
    assert first.attempts == 1
    assert first.status == TaskStatus.PENDING

    worker.run_once()
    second = queue.get(task.id)
    assert second.attempts == 2
    assert second.status == TaskStatus.PENDING

    worker.run_once()
    third = queue.get(task.id)
    assert third.attempts == 3
    assert third.status == TaskStatus.FAILED
