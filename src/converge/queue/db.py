"""Database task queue implementation backed by SQLite-compatible SQL."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from converge.core.config import load_queue_settings
from converge.queue.base import TaskQueue
from converge.queue.schemas import TaskRecord, TaskRequest, TaskResult, TaskStatus


class DatabaseTaskQueue(TaskQueue):
    """Database queue implementation using a SQLALCHEMY_DATABASE_URI connection string."""

    def __init__(self, database_uri: str) -> None:
        self._db_path = self._parse_sqlite_path(database_uri)
        self._max_attempts = load_queue_settings().worker_max_attempts
        self._initialize_schema()

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a new pending task record."""
        now = self._now_iso()
        task_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, status, created_at, updated_at, attempts, request_json,
                    last_error, artifacts_dir, claimed_at, claim_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    TaskStatus.PENDING.value,
                    now,
                    now,
                    0,
                    request.model_dump_json(),
                    None,
                    None,
                    None,
                    None,
                ),
            )
            conn.commit()
        return self.get(task_id)

    def poll_and_claim(self, limit: int) -> list[TaskRecord]:
        """Poll pending tasks and claim them in one immediate transaction."""
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT id FROM tasks
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (TaskStatus.PENDING.value, limit),
            ).fetchall()

            claimed_ids = [row[0] for row in rows]
            for task_id in claimed_ids:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = ?, claimed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (TaskStatus.CLAIMED.value, now, now, task_id),
                )
            conn.commit()

        return [self.get(task_id) for task_id in claimed_ids]

    def mark_running(self, task_id: str) -> None:
        """Mark a claimed task as running."""
        with self._connect() as conn:
            updated = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (TaskStatus.RUNNING.value, self._now_iso(), task_id),
            )
            if updated.rowcount == 0:
                raise ValueError(f"Task not found: {task_id}")
            conn.commit()

    def complete(self, task_id: str, result: TaskResult) -> None:
        """Mark task completion with final status and artifacts."""
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE tasks
                SET status = ?, artifacts_dir = ?, last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (result.status.value, result.artifacts_dir, self._now_iso(), task_id),
            )
            if updated.rowcount == 0:
                raise ValueError(f"Task not found: {task_id}")
            conn.commit()

    def fail(self, task_id: str, error: str, retryable: bool) -> None:
        """Mark task failure and requeue while attempts remain."""
        task = self.get(task_id)
        attempts = task.attempts + 1
        status = (
            TaskStatus.PENDING.value
            if retryable and attempts < self._max_attempts
            else TaskStatus.FAILED.value
        )
        claimed_at = None if status == TaskStatus.PENDING.value else self._now_iso()

        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE tasks
                SET attempts = ?, last_error = ?, status = ?, claimed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (attempts, error, status, claimed_at, self._now_iso(), task_id),
            )
            if updated.rowcount == 0:
                raise ValueError(f"Task not found: {task_id}")
            conn.commit()

    def get(self, task_id: str) -> TaskRecord:
        """Get the latest task record."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, status, created_at, updated_at, attempts, request_json,
                       last_error, artifacts_dir
                FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Task not found: {task_id}")

        return TaskRecord(
            id=row[0],
            status=TaskStatus(row[1]),
            created_at=self._parse_datetime(row[2]),
            updated_at=self._parse_datetime(row[3]),
            attempts=row[4],
            request=TaskRequest.model_validate(json.loads(row[5])),
            last_error=row[6],
            artifacts_dir=row[7],
        )

    def _initialize_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    request_json TEXT NOT NULL,
                    last_error TEXT,
                    artifacts_dir TEXT,
                    claimed_at TEXT,
                    claim_token TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at)"
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_sqlite_path(self, database_uri: str) -> Path:
        prefix = "sqlite:///"
        if not database_uri.startswith(prefix):
            raise ValueError("Only sqlite:/// URIs are supported in this iteration")
        db_path = Path(database_uri[len(prefix) :])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
