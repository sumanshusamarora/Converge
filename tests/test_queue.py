"""Tests for queue backends and worker polling with SQLite."""

from __future__ import annotations

from pathlib import Path

import pytest

from converge.queue.db import DatabaseTaskQueue
from converge.queue.schemas import TaskRequest, TaskStatus
from converge.worker.poller import PollingWorker


@pytest.fixture
def sqlite_uri(tmp_path: Path) -> str:
    """Provide a SQLite URI for queue tests."""
    return f"sqlite:///{tmp_path / 'test.db'}"


def _set_queue_env(monkeypatch: pytest.MonkeyPatch, sqlite_uri: str) -> None:
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", sqlite_uri)
    monkeypatch.setenv("CONVERGE_QUEUE_BACKEND", "db")
    monkeypatch.setenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")


def test_enqueue_creates_pending_task(
    monkeypatch: pytest.MonkeyPatch, sqlite_uri: str
) -> None:
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)

    task = queue.enqueue(TaskRequest(goal="Goal", repos=["repo_a"]))

    assert task.status == TaskStatus.PENDING
    assert task.attempts == 0


def test_poll_and_claim_updates_status(
    monkeypatch: pytest.MonkeyPatch, sqlite_uri: str
) -> None:
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)
    task = queue.enqueue(TaskRequest(goal="Goal", repos=["repo_a"]))

    claimed = queue.poll_and_claim(limit=1)

    assert len(claimed) == 1
    assert claimed[0].id == task.id
    assert claimed[0].status == TaskStatus.CLAIMED
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.CLAIMED


def test_worker_run_once_completes_task_and_stores_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_uri: str,
    tmp_path: Path,
) -> None:
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)

    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    (fake_repo / "README.md").write_text("# repo", encoding="utf-8")

    task = queue.enqueue(TaskRequest(goal="Goal", repos=[str(fake_repo)]))

    from converge.orchestration.runner import RunOutcome

    def fake_run_coordinate(
        goal: str,
        repos: list[str],
        max_rounds: int,
        agent_provider: str | None,
        base_output_dir: Path | None,
    ) -> RunOutcome:
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "summary.md").write_text("ok", encoding="utf-8")
        return RunOutcome(
            status="CONVERGED",
            summary="done",
            artifacts_dir=str(artifacts_dir),
            hitl_questions=[],
        )

    monkeypatch.setattr("converge.worker.poller.run_coordinate", fake_run_coordinate)

    worker = PollingWorker(queue=queue, poll_interval_seconds=0.01, batch_size=1)
    processed = worker.run_once()

    assert processed == 1
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.SUCCEEDED
    assert stored.artifacts_dir is not None
    assert Path(stored.artifacts_dir).exists()


def test_postgres_uri_is_supported_by_backend_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres URIs should pass backend parsing (even if driver/DB is unavailable)."""
    monkeypatch.setenv("CONVERGE_QUEUE_BACKEND", "db")
    monkeypatch.setenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3")

    with pytest.raises(Exception) as exc_info:  # noqa: BLE001
        DatabaseTaskQueue("postgresql://user:pass@localhost:5432/converge")

    assert "Only sqlite" not in str(exc_info.value)
