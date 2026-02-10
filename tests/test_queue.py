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


def test_enqueue_creates_pending_task(monkeypatch: pytest.MonkeyPatch, sqlite_uri: str) -> None:
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)

    task = queue.enqueue(TaskRequest(goal="Goal", repos=["repo_a"]))

    assert task.status == TaskStatus.PENDING
    assert task.attempts == 0


def test_poll_and_claim_updates_status(monkeypatch: pytest.MonkeyPatch, sqlite_uri: str) -> None:
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
        hitl_resolution: dict[str, object] | None = None,
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


def test_hitl_lifecycle_persist_and_resolve(
    monkeypatch: pytest.MonkeyPatch, sqlite_uri: str, tmp_path: Path
) -> None:
    """Test HITL question persistence and resolution flow."""
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)

    # Create and enqueue a task
    task = queue.enqueue(TaskRequest(goal="Test HITL", repos=["repo_a"]))

    # Complete with HITL_REQUIRED status
    from converge.queue.schemas import TaskResult, TaskStatus

    result = TaskResult(
        status=TaskStatus.HITL_REQUIRED,
        summary="Needs human input",
        artifacts_dir=str(tmp_path / "artifacts"),
        hitl_questions=[
            "Should we proceed with breaking change?",
            "Which API version to use?",
        ],
    )
    queue.complete(task.id, result)

    # Verify task is HITL_REQUIRED
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.HITL_REQUIRED

    # Verify questions were persisted
    questions = queue.get_hitl_questions(task.id)
    assert len(questions) == 2
    assert "breaking change" in questions[0]

    # Resolve HITL with human decision
    resolution = {
        "decision": "proceed",
        "api_version": "v2",
        "notes": "Team agreed on v2",
    }
    queue.resolve_hitl(task.id, resolution)

    # Verify task is back to PENDING
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.PENDING

    # Verify resolution was stored
    stored_resolution = queue.get_hitl_resolution(task.id)
    assert stored_resolution is not None
    assert stored_resolution["decision"] == "proceed"
    assert stored_resolution["api_version"] == "v2"


def test_hitl_resolve_requires_hitl_status(
    monkeypatch: pytest.MonkeyPatch, sqlite_uri: str
) -> None:
    """Test that resolve_hitl only works on HITL_REQUIRED tasks."""
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)

    task = queue.enqueue(TaskRequest(goal="Test", repos=["repo_a"]))

    # Try to resolve when status is PENDING (not HITL_REQUIRED)
    with pytest.raises(ValueError, match="not in HITL_REQUIRED status"):
        queue.resolve_hitl(task.id, {"decision": "proceed"})


def test_worker_resume_with_hitl_resolution(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_uri: str,
    tmp_path: Path,
) -> None:
    """Test worker resumes task with HITL resolution."""
    _set_queue_env(monkeypatch, sqlite_uri)
    queue = DatabaseTaskQueue(sqlite_uri)

    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    (fake_repo / "README.md").write_text("# repo", encoding="utf-8")

    task = queue.enqueue(TaskRequest(goal="Goal", repos=[str(fake_repo)]))

    # First run: task requires HITL
    from converge.orchestration.runner import RunOutcome

    first_run_called = {"called": False}

    def fake_run_coordinate_first(
        goal: str,
        repos: list[str],
        max_rounds: int,
        agent_provider: str | None,
        base_output_dir: Path | None,
        hitl_resolution: dict[str, object] | None = None,
    ) -> RunOutcome:
        first_run_called["called"] = True
        assert hitl_resolution is None  # First run has no resolution
        return RunOutcome(
            status="HITL_REQUIRED",
            summary="needs input",
            artifacts_dir=str(tmp_path / "artifacts1"),
            hitl_questions=["Question 1"],
        )

    monkeypatch.setattr("converge.worker.poller.run_coordinate", fake_run_coordinate_first)

    worker = PollingWorker(queue=queue, poll_interval_seconds=0.01, batch_size=1)
    processed = worker.run_once()

    assert processed == 1
    assert first_run_called["called"]

    # Verify task is HITL_REQUIRED
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.HITL_REQUIRED

    # Human resolves HITL
    resolution = {"decision": "approved"}
    queue.resolve_hitl(task.id, resolution)

    # Second run: worker should pass resolution
    second_run_called = {"called": False, "resolution": None}

    def fake_run_coordinate_second(
        goal: str,
        repos: list[str],
        max_rounds: int,
        agent_provider: str | None,
        base_output_dir: Path | None,
        hitl_resolution: dict[str, object] | None = None,
    ) -> RunOutcome:
        second_run_called["called"] = True
        second_run_called["resolution"] = hitl_resolution
        return RunOutcome(
            status="CONVERGED",
            summary="completed",
            artifacts_dir=str(tmp_path / "artifacts2"),
            hitl_questions=[],
        )

    monkeypatch.setattr("converge.worker.poller.run_coordinate", fake_run_coordinate_second)

    processed = worker.run_once()

    assert processed == 1
    assert second_run_called["called"]
    assert second_run_called["resolution"] == resolution

    # Verify task is SUCCEEDED
    stored = queue.get(task.id)
    assert stored.status == TaskStatus.SUCCEEDED
