"""Configuration models for Converge."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Basic runtime configuration for Converge."""

    environment: str = "dev"
    log_level: str = "INFO"
