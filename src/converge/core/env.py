"""Environment loading helpers."""

from pathlib import Path

from dotenv import load_dotenv


def _repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[3]


def load_environment(env_file: str | None = None) -> None:
    """Load environment variables from a dotenv file when present.

    Args:
        env_file: Optional explicit path to dotenv file.
    """
    dotenv_path = Path(env_file) if env_file else _repo_root() / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=False)
