"""Command-line interface for Converge."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click

from converge.core.config import load_queue_settings, load_server_settings
from converge.core.env import load_environment
from converge.core.logging import setup_logging
from converge.observability.opik_client import configure_opik
from converge.orchestration.runner import run_coordinate
from converge.queue.factory import create_queue
from converge.worker.poller import PollingWorker

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Converge: Multi-repository coordination and governance tool.

    Converge helps multiple repositories that build one product
    collaborate, decide, and converge safely.
    """


@cli.command()
@click.option("--goal", required=True, help="The high-level goal to achieve across repositories")
@click.option(
    "--repos",
    required=True,
    multiple=True,
    help="Repository identifiers (can be specified multiple times)",
)
@click.option("--max-rounds", default=2, type=int, help="Maximum number of convergence rounds")
@click.option(
    "--output-dir",
    default=".converge",
    help="Base directory for output artifacts (default: .converge)",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
@click.option("--model", default=None, help="Override OpenAI model for proposal generation")
@click.option("--no-llm", is_flag=True, default=False, help="Force heuristic proposal generation")
@click.option(
    "--no-tracing",
    is_flag=True,
    default=False,
    help="Disable tracing for this run only",
)
@click.option(
    "--hil-mode",
    default="conditional",
    type=click.Choice(["conditional", "interrupt"], case_sensitive=False),
    help="HITL strategy to use (default: conditional)",
)
@click.option(
    "--agent-provider",
    default=None,
    type=click.Choice(["codex", "copilot"], case_sensitive=False),
    help="Agent provider to use (default: from CONVERGE_AGENT_PROVIDER or codex)",
)
@click.option(
    "--enable-codex-exec",
    is_flag=True,
    default=False,
    help="Enable Codex CLI execution (requires OPENAI_API_KEY)",
)
def coordinate(
    goal: str,
    repos: tuple[str, ...],
    max_rounds: int,
    output_dir: str,
    log_level: str,
    model: str | None,
    no_llm: bool,
    no_tracing: bool,
    hil_mode: str,
    agent_provider: str | None,
    enable_codex_exec: bool,
) -> None:
    """Coordinate changes across multiple repositories."""
    load_environment()
    setup_logging(level=log_level)

    try:
        if no_tracing:
            os.environ["OPIK_TRACK_DISABLE"] = "true"
        configure_opik()
        if model:
            os.environ["CONVERGE_OPENAI_MODEL"] = model
        if no_llm:
            os.environ["CONVERGE_NO_LLM"] = "true"
        os.environ["CONVERGE_HIL_MODE"] = hil_mode.lower()
        if enable_codex_exec:
            os.environ["CONVERGE_CODEX_ENABLED"] = "true"

        outcome = run_coordinate(
            goal=goal,
            repos=list(repos),
            max_rounds=max_rounds,
            agent_provider=agent_provider,
            base_output_dir=Path(output_dir),
        )

        logger.info("Status: %s", outcome.status)
        logger.info("Artifacts Location: %s", outcome.artifacts_dir)

        if outcome.status == "HITL_REQUIRED":
            sys.exit(2)
        if outcome.status == "FAILED":
            sys.exit(1)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during coordination: %s", exc)
        sys.exit(1)


@cli.command()
@click.option(
    "--once",
    "run_once",
    is_flag=True,
    default=False,
    help="Run one poll cycle and exit",
)
@click.option("--poll-interval", type=float, default=None, help="Polling interval in seconds")
@click.option("--batch-size", type=int, default=None, help="Number of tasks to claim per cycle")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
def worker(
    run_once: bool, poll_interval: float | None, batch_size: int | None, log_level: str
) -> None:
    """Run the background polling worker for queued tasks."""
    load_environment()
    setup_logging(level=log_level)

    try:
        configure_opik()
        settings = load_queue_settings()
        if settings.backend == "db" and not settings.sqlalchemy_database_uri:
            raise ValueError("SQLALCHEMY_DATABASE_URI is required when CONVERGE_QUEUE_BACKEND=db")

        worker_poll_interval = (
            poll_interval if poll_interval is not None else settings.worker_poll_interval_seconds
        )
        worker_batch_size = batch_size if batch_size is not None else settings.worker_batch_size

        queue = create_queue()
        polling_worker = PollingWorker(
            queue=queue,
            poll_interval_seconds=worker_poll_interval,
            batch_size=worker_batch_size,
        )
        if run_once:
            polling_worker.run_once()
            return
        polling_worker.run_forever()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during worker execution: %s", exc)
        sys.exit(1)


@cli.command()
@click.option("--host", default=None, help="Server host")
@click.option("--port", type=int, default=None, help="Server port")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
def server(host: str | None, port: int | None, reload: bool, log_level: str) -> None:
    """Run the webhook ingestion HTTP server."""
    load_environment()
    setup_logging(level=log_level)

    try:
        settings = load_server_settings()
        resolved_host = host if host is not None else settings.host
        resolved_port = port if port is not None else settings.port

        import uvicorn

        from converge.server.app import create_app

        uvicorn.run(
            create_app(),
            host=resolved_host,
            port=resolved_port,
            reload=reload,
        )
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during server execution: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    cli()
