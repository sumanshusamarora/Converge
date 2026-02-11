"""SQLAlchemy-backed task queue implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
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
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(
        String(320), nullable=True, unique=True, index=True
    )
    hitl_questions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    hitl_resolution_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class DatabaseTaskQueue(TaskQueue):
    """Database queue implementation for SQLite and PostgreSQL."""

    def __init__(self, database_uri: str) -> None:
        self._engine = create_engine(database_uri, future=True, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._dialect_name = self._engine.url.get_backend_name()
        self._max_attempts = load_queue_settings().worker_max_attempts
        Base.metadata.create_all(self._engine)
        self._ensure_schema_extensions()

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        """Enqueue a new pending task."""
        return self.enqueue_with_dedupe(request, source=None, idempotency_key=None)

    def enqueue_with_dedupe(
        self, request: TaskRequest, source: str | None, idempotency_key: str | None
    ) -> TaskRecord:
        """Enqueue a task and return existing record when dedupe key already exists."""
        now = self._now()
        dedupe_key = self._build_dedupe_key(source=source, idempotency_key=idempotency_key)
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
            source=source,
            source_event_id=None,
            idempotency_key=idempotency_key,
            dedupe_key=dedupe_key,
        )
        with self._session_factory() as session:
            try:
                session.add(task_row)
                session.commit()
                return self._to_record(task_row)
            except IntegrityError:
                session.rollback()
                existing = self.find_by_source_idempotency(source, idempotency_key)
                if existing is None:
                    raise
                return existing

    def find_by_source_idempotency(
        self, source: str | None, idempotency_key: str | None
    ) -> TaskRecord | None:
        """Find a task by source/idempotency key pair."""
        dedupe_key = self._build_dedupe_key(source=source, idempotency_key=idempotency_key)
        if dedupe_key is None:
            return None
        with self._session_factory() as session:
            row = session.scalar(select(TaskRow).where(TaskRow.dedupe_key == dedupe_key))
            if row is None:
                return None
            return self._to_record(row)

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
            # Persist HITL questions when status is HITL_REQUIRED
            if result.status == TaskStatus.HITL_REQUIRED and result.hitl_questions:
                row.hitl_questions_json = json.dumps(result.hitl_questions)
            row.status_reason = result.status_reason
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

    def get_hitl_questions(self, task_id: str) -> list[str]:
        """Get HITL questions for a task in HITL_REQUIRED status."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            if row.hitl_questions_json:
                return cast(list[str], json.loads(row.hitl_questions_json))
            return []

    def get_hitl_resolution(self, task_id: str) -> dict[str, object] | None:
        """Get HITL resolution if it exists."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            if row.hitl_resolution_json:
                return cast(dict[str, object], json.loads(row.hitl_resolution_json))
            return None

    def resolve_hitl(self, task_id: str, resolution: dict[str, object]) -> None:
        """Resolve HITL questions and transition task back to PENDING."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            if row.status != TaskStatus.HITL_REQUIRED.value:
                raise ValueError(f"Task {task_id} is not in HITL_REQUIRED status")
            row.hitl_resolution_json = json.dumps(resolution)
            row.status = TaskStatus.PENDING.value
            row.claimed_at = None
            row.updated_at = self._now()
            session.commit()

    def list_tasks(
        self, status_filter: TaskStatus | None = None, limit: int = 100, offset: int = 0
    ) -> list[TaskRecord]:
        """List tasks with optional status filter and pagination."""
        with self._session_factory() as session:
            query = select(TaskRow).order_by(TaskRow.created_at.desc())
            if status_filter is not None:
                query = query.where(TaskRow.status == status_filter.value)
            query = query.limit(limit).offset(offset)
            rows = session.scalars(query).all()
            return [self._to_record(row) for row in rows]

    def cancel(self, task_id: str) -> None:
        """Cancel a task."""
        with self._session_factory() as session:
            row = self._get_row(session, task_id)
            if row.status in {TaskStatus.SUCCEEDED.value, TaskStatus.FAILED.value}:
                raise ValueError(f"Cannot cancel task {task_id} with status {row.status}")
            row.status = TaskStatus.CANCELLED.value
            row.updated_at = self._now()
            session.commit()

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
            source=row.source,
            idempotency_key=row.idempotency_key,
            status_reason=row.status_reason,
            resolution_json=row.resolution_json,
        )

    def _build_dedupe_key(self, source: str | None, idempotency_key: str | None) -> str | None:
        if not source or not idempotency_key:
            return None
        return f"{source}:{idempotency_key}"

    def _ensure_schema_extensions(self) -> None:
        """Ensure idempotency/source columns and unique index exist.
        No Alembic in this iteration, so this method performs idempotent schema
        extension checks for existing deployments.
        """
        add_specs: dict[str, str] = {
            "source": "TEXT",
            "source_event_id": "TEXT",
            "idempotency_key": "TEXT",
            "dedupe_key": "TEXT",
            "hitl_questions_json": "TEXT",
            "hitl_resolution_json": "TEXT",
            "status_reason": "TEXT",
            "resolution_json": "TEXT",
        }
        with self._engine.begin() as conn:
            self._acquire_schema_lock(conn)
            columns = {column["name"] for column in inspect(conn).get_columns("tasks")}
            for column_name, column_sql_type in add_specs.items():
                if column_name not in columns:
                    conn.execute(
                        text(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_sql_type}")
                    )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "idx_tasks_source_dedupe_key_unique ON tasks(dedupe_key)"
                )
            )

    def _acquire_schema_lock(self, conn: Connection) -> None:
        """Serialize schema extension DDL on Postgres to avoid startup races."""
        if self._dialect_name in {"postgresql", "postgres"}:
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('converge.tasks.schema'))"))

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
