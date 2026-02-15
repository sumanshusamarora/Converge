"""Opik configuration and optional tracing helpers."""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_CONFIGURED = False
_OPIK_ENABLED = False

TRUE_LIKE = {"1", "true", "yes", "on"}


def _is_true_like(value: str | None) -> bool:
    return value is not None and value.strip().lower() in TRUE_LIKE


def is_tracing_enabled() -> bool:
    """Return whether Opik tracing is currently enabled."""
    return _OPIK_ENABLED


def configure_opik() -> None:
    """Configure Opik tracing from environment variables."""
    global _CONFIGURED, _OPIK_ENABLED
    if _CONFIGURED:
        return

    _CONFIGURED = True
    if _is_true_like(os.getenv("OPIK_TRACK_DISABLE")):
        logger.info("Opik tracing disabled by OPIK_TRACK_DISABLE")
        return

    required = ["OPIK_API_KEY", "OPIK_WORKSPACE", "OPIK_PROJECT_NAME"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        logger.warning("Opik not configured; missing required environment settings")
        return

    try:
        opik_module = importlib.import_module("opik")
        opik_module.configure(use_local=False)
        _OPIK_ENABLED = True
    except Exception:
        logger.warning("Opik initialization failed; continuing without tracing")


def track_langgraph_app(app: Any) -> Any:
    """Track a compiled LangGraph app with Opik when tracing is enabled."""
    if not _OPIK_ENABLED:
        return app

    try:
        langchain_integration = importlib.import_module("opik.integrations.langchain")
        opik_tracer = langchain_integration.OpikTracer(
            tags=["converge"], metadata={"app": "cli"}
        )
        return langchain_integration.track_langgraph(app, opik_tracer)
    except Exception:
        logger.warning(
            "Opik LangGraph integration unavailable; continuing without graph tracing"
        )
        return app


def opik_track(name: str | None = None) -> Callable[[F], F]:
    """Wrap a function with opik.track when tracing is enabled, otherwise no-op."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _OPIK_ENABLED:
                return func(*args, **kwargs)
            try:
                opik_module = importlib.import_module("opik")
                track = getattr(opik_module, "track", None)
                if callable(track):
                    tracked = track(name=name or func.__name__)(func)
                    return tracked(*args, **kwargs)
            except Exception:
                logger.debug(
                    "Opik track wrapper failed; calling function directly",
                    exc_info=True,
                )
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
