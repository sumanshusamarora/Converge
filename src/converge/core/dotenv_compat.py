"""Fallback dotenv loader used only when python-dotenv is unavailable."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(dotenv_path: str | Path | None = None, override: bool = False) -> bool:
    """Load simple key=value pairs from a dotenv file."""
    path = Path(dotenv_path) if dotenv_path is not None else Path(".env")
    if not path.exists():
        return False

    loaded = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        if override or normalized_key not in os.environ:
            os.environ[normalized_key] = normalized_value
            loaded = True
    return loaded
