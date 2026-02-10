"""Environment loading helpers."""

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    from converge.core.dotenv_compat import load_dotenv


def _repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[3]


def load_environment(env_file: str | None = None) -> None:
    """Load environment variables from a dotenv file when present."""
    dotenv_path = Path(env_file) if env_file else _repo_root() / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=False)
