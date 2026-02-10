"""Minimal dotenv-compatible loader used for local execution and tests."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(dotenv_path: str | Path | None = None, override: bool = False) -> bool:
    """Load environment variables from a dotenv file.

    This is a tiny compatible subset of python-dotenv's `load_dotenv` behavior.
    """
    if dotenv_path is None:
        dotenv_path = Path(".env")
    path = Path(dotenv_path)
    if not path.exists():
        return False

    loaded = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value
            loaded = True
    return loaded
