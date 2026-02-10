"""Environment loading helpers."""

from __future__ import annotations

from os import PathLike
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv_real

    def _load_dotenv(dotenv_path: str | PathLike[str] | None, override: bool) -> bool:
        return _load_dotenv_real(dotenv_path=dotenv_path, override=override)
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    from converge.core.dotenv_compat import load_dotenv as _load_dotenv_fallback

    def _load_dotenv(dotenv_path: str | PathLike[str] | None, override: bool) -> bool:
        normalized_path = Path(dotenv_path) if dotenv_path is not None else None
        return _load_dotenv_fallback(dotenv_path=normalized_path, override=override)


def _repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[3]


def load_environment(env_file: str | None = None) -> None:
    """Load environment variables from a dotenv file when present."""
    dotenv_path = Path(env_file) if env_file else _repo_root() / ".env"
    _load_dotenv(dotenv_path=dotenv_path, override=False)
