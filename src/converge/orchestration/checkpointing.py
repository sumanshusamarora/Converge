"""LangGraph checkpoint helpers backed by the configured task database."""

from __future__ import annotations

import logging
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)
DEFAULT_CHECKPOINT_DB_URI = "sqlite:///./converge.db"


@dataclass
class CheckpointerHandle:
    """Container for a checkpointer object and its lifecycle stack."""

    checkpointer: Any
    _stack: ExitStack

    def close(self) -> None:
        """Release any resources held by the checkpointer."""
        self._stack.close()


def create_db_checkpointer(database_uri: str | None) -> CheckpointerHandle | None:
    """Create a LangGraph DB checkpointer for SQLite/Postgres URIs.

    Args:
        database_uri: SQLAlchemy-style connection URI.

    Returns:
        A checkpointer handle when available, otherwise ``None``.
    """
    resolved_database_uri = (database_uri or "").strip() or DEFAULT_CHECKPOINT_DB_URI
    if not database_uri or not database_uri.strip():
        logger.info(
            "SQLALCHEMY_DATABASE_URI not set; defaulting LangGraph checkpoints to %s",
            DEFAULT_CHECKPOINT_DB_URI,
        )

    try:
        url = make_url(resolved_database_uri)
    except Exception:
        logger.warning("Invalid SQLALCHEMY_DATABASE_URI; skipping LangGraph checkpointing")
        return None

    backend = url.get_backend_name()
    conn_string = _normalized_connection_string(resolved_database_uri)

    if backend in {"postgresql", "postgres"}:
        return _load_checkpointer(
            module_name="langgraph.checkpoint.postgres",
            class_name="PostgresSaver",
            conn_string=conn_string,
            install_hint="pip install langgraph-checkpoint-postgres",
        )

    if backend == "sqlite":
        return _load_checkpointer(
            module_name="langgraph.checkpoint.sqlite",
            class_name="SqliteSaver",
            conn_string=conn_string,
            install_hint="pip install langgraph-checkpoint-sqlite",
        )

    logger.info("No LangGraph DB checkpointer for backend '%s'; using non-persistent flow", backend)
    return None


def _normalized_connection_string(database_uri: str) -> str:
    """Normalize SQLAlchemy URLs for checkpointer libraries."""
    url = make_url(database_uri)
    drivername = url.drivername
    if "+" in drivername:
        url = url.set(drivername=drivername.split("+", 1)[0])
    return url.render_as_string(hide_password=False)


def _load_checkpointer(
    module_name: str,
    class_name: str,
    conn_string: str,
    install_hint: str,
) -> CheckpointerHandle | None:
    try:
        module = __import__(module_name, fromlist=[class_name])
        saver_cls = getattr(module, class_name)
    except Exception:
        logger.warning(
            "LangGraph DB checkpointer module unavailable (%s). Install with: %s",
            module_name,
            install_hint,
        )
        return None

    stack = ExitStack()
    try:
        builder = getattr(saver_cls, "from_conn_string", None)
        if callable(builder):
            maybe_ctx = builder(conn_string)
        else:
            maybe_ctx = saver_cls(conn_string)

        if hasattr(maybe_ctx, "__enter__") and hasattr(maybe_ctx, "__exit__"):
            checkpointer = stack.enter_context(maybe_ctx)
        else:
            checkpointer = maybe_ctx

        setup = getattr(checkpointer, "setup", None)
        if callable(setup):
            setup()

        return CheckpointerHandle(checkpointer=checkpointer, _stack=stack)
    except Exception:
        stack.close()
        logger.exception(
            "Failed to initialize LangGraph DB checkpointer; using non-persistent flow"
        )
        return None
