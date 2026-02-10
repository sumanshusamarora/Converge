"""Logging helpers for Converge."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _configure_root_logger() -> None:
    """Configure root logging once with a consistent format."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with repository defaults."""
    _configure_root_logger()
    return logging.getLogger(name)
