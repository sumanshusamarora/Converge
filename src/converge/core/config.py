"""Configuration management for Converge."""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ConvergeConfig(BaseModel):
    """Configuration for a Converge coordination session."""

    goal: str
    repos: list[str]
    max_rounds: int = 2
    output_dir: str = ".converge"
    log_level: str = "INFO"
    model: str | None = None
    no_llm: bool = False
    hil_mode: Literal["conditional", "interrupt"] = "conditional"
    agent_provider: str = "codex"
    enable_codex_exec: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Validate configuration values after model initialization."""
        if not self.goal.strip():
            raise ValueError("Goal cannot be empty")
        if not self.repos:
            raise ValueError("At least one repository must be specified")
        if len(self.repos) != len(set(self.repos)):
            raise ValueError("Repository list contains duplicates")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        if self.hil_mode not in {"conditional", "interrupt"}:
            raise ValueError("hil_mode must be either 'conditional' or 'interrupt'")
        if self.agent_provider.lower() not in {"codex", "copilot"}:
            raise ValueError("agent_provider must be either 'codex' or 'copilot'")
        logger.info("Config initialized: goal=%s, repos=%s", self.goal, self.repos)


class QueueSettings(BaseModel):
    """Queue and worker settings loaded from environment variables."""

    backend: str
    sqlalchemy_database_uri: str | None = None
    worker_poll_interval_seconds: float
    worker_batch_size: int
    worker_max_attempts: int


class ServerSettings(BaseModel):
    """Server settings loaded from environment variables."""

    host: str
    port: int
    webhook_secret: str | None
    webhook_max_body_bytes: int
    webhook_idempotency_ttl_seconds: int


def load_queue_settings() -> QueueSettings:
    """Load queue and worker settings from environment with validation."""
    backend = os.getenv("CONVERGE_QUEUE_BACKEND", "db").strip().lower()
    sqlalchemy_database_uri = os.getenv("SQLALCHEMY_DATABASE_URI")

    try:
        worker_poll_interval_seconds = float(
            os.getenv("CONVERGE_WORKER_POLL_INTERVAL_SECONDS", "2")
        )
    except ValueError as exc:
        raise ValueError("CONVERGE_WORKER_POLL_INTERVAL_SECONDS must be a float") from exc

    try:
        worker_batch_size = int(os.getenv("CONVERGE_WORKER_BATCH_SIZE", "1"))
    except ValueError as exc:
        raise ValueError("CONVERGE_WORKER_BATCH_SIZE must be an integer") from exc

    try:
        worker_max_attempts = int(os.getenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3"))
    except ValueError as exc:
        raise ValueError("CONVERGE_WORKER_MAX_ATTEMPTS must be an integer") from exc

    if worker_poll_interval_seconds <= 0:
        raise ValueError("CONVERGE_WORKER_POLL_INTERVAL_SECONDS must be > 0")
    if worker_batch_size <= 0:
        raise ValueError("CONVERGE_WORKER_BATCH_SIZE must be > 0")
    if worker_max_attempts <= 0:
        raise ValueError("CONVERGE_WORKER_MAX_ATTEMPTS must be > 0")

    return QueueSettings(
        backend=backend,
        sqlalchemy_database_uri=sqlalchemy_database_uri,
        worker_poll_interval_seconds=worker_poll_interval_seconds,
        worker_batch_size=worker_batch_size,
        worker_max_attempts=worker_max_attempts,
    )


def load_server_settings() -> ServerSettings:
    """Load HTTP server settings for webhook ingestion."""
    host = os.getenv("CONVERGE_SERVER_HOST", "0.0.0.0")
    try:
        port = int(os.getenv("CONVERGE_SERVER_PORT", "8080"))
    except ValueError as exc:
        raise ValueError("CONVERGE_SERVER_PORT must be an integer") from exc

    webhook_secret = os.getenv("CONVERGE_WEBHOOK_SECRET") or None

    try:
        webhook_max_body_bytes = int(os.getenv("CONVERGE_WEBHOOK_MAX_BODY_BYTES", "262144"))
    except ValueError as exc:
        raise ValueError("CONVERGE_WEBHOOK_MAX_BODY_BYTES must be an integer") from exc

    try:
        webhook_idempotency_ttl_seconds = int(
            os.getenv("CONVERGE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS", "86400")
        )
    except ValueError as exc:
        raise ValueError("CONVERGE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS must be an integer") from exc

    if port <= 0:
        raise ValueError("CONVERGE_SERVER_PORT must be > 0")
    if webhook_max_body_bytes <= 0:
        raise ValueError("CONVERGE_WEBHOOK_MAX_BODY_BYTES must be > 0")
    if webhook_idempotency_ttl_seconds <= 0:
        raise ValueError("CONVERGE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS must be > 0")

    return ServerSettings(
        host=host,
        port=port,
        webhook_secret=webhook_secret,
        webhook_max_body_bytes=webhook_max_body_bytes,
        webhook_idempotency_ttl_seconds=webhook_idempotency_ttl_seconds,
    )
