"""SQLAlchemy-backed task queue implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from converge.core.config import load_queue_settings
from converge.queue.base import TaskQueue
from converge.queue.schemas import TaskRecord, TaskRequest, TaskResult, TaskStatus


class Base(DeclarativeBase):
    """Declarative SQLAlchemy base for queue tables."""


class TaskRow(Base):
    """Persistent task row for database queue backends."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DatabaseTaskQueue(TaskQueue):
    """Database queue implementation for SQLite and PostgreSQL."""

    def __init__(self, database_uri: str) -> None:
        self._engine = create_engine(database_uri, future=True, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._dialect_name = self._engine.url.get_backend_name()
        self._max_attempts = load_queue_settings().worker_max_attempts
        Base.metadata.create_all(self._engine)

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a new pending task."""
        now = self._now()
        task_row = TaskRow(
            id=str(uuid4()),
            status=TaskStatus.PENDING.value,
            created_at=now,
            updated_at=now,
            attempts=0,
            request_json=request.model_dump_json(),
            last_error=None,
            artifacts_dir=None,
            claimed_at=None,
            claim_token=None,
        )
        with self._session_factory() as session:
            session.add(task_row)
            session.commit()
            return self._to_record(task_row)

    def poll_and_claim(self, limit: int) -> list[TaskRecord]:
        """Poll pending tasks and claim up to ``limit`` tasks atomically.

        PostgreSQL uses row-level locks with ``SKIP LOCKED`` to allow concurrent
        workers without duplicate claims. SQLite falls back to a single
        transaction with immediate updates.
        """
        now = self._now()
        with self._session_factory() as session:
            if self._dialect_name in {"postgresql", "postgres"}:
                query = (
                    select(TaskRow)
                    .where(TaskRow.status == TaskStatus.PENDING.value)
                    .order_by(TaskRow.created_at.asc())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            else:
                query = (
                    select(TaskRow)
                    .where(TaskRow.status == TaskStatus.PENDING.value)
                    .order_by(TaskRow.created_at.asc())
                    .limit(limit)
                )

            rows = session.scalars(query).all()
            for row in rows:
                row.status = TaskStatus.CLAIMED.value
                row.claimed_at = now
                row.updated_at = now
            session.commit()
            return [self._to_record(row) for row in rows]

    def mark_running(self, task_id: str) -> None:
        """Mark a claimed task as running."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            row.status = TaskStatus.RUNNING.value
            row.updated_at = self._now()
            session.commit()

    def complete(self, task_id: str, result: TaskResult) -> None:
        """Mark task completion with final status and artifacts location."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            row.status = result.status.value
            row.artifacts_dir = result.artifacts_dir
            row.last_error = None
            row.updated_at = self._now()
            session.commit()

    def fail(self, task_id: str, error: str, retryable: bool) -> None:
        """Mark task failure and requeue while attempts remain."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            attempts = row.attempts + 1
            row.attempts = attempts
            row.last_error = error
            row.updated_at = self._now()
            if retryable and attempts < self._max_attempts:
                row.status = TaskStatus.PENDING.value
                row.claimed_at = None
            else:
                row.status = TaskStatus.FAILED.value
            session.commit()

    def get(self, task_id: str) -> TaskRecord:
        """Get a task by id."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            return self._to_record(row)

    def _get_row(self, session: Session, task_id: str) -> TaskRow:
        row = cast(TaskRow | None, session.get(TaskRow, task_id))
        if row is None:
            raise ValueError(f"Task not found: {task_id}")
        return row

    def _to_record(self, row: TaskRow) -> TaskRecord:
        return TaskRecord(
            id=row.id,
            status=TaskStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
            attempts=row.attempts,
            request=TaskRequest.model_validate(json.loads(row.request_json)),
            last_error=row.last_error,
            artifacts_dir=row.artifacts_dir,
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
