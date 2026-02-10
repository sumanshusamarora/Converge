"""Command-line interface for Converge."""

import logging
import os
import sys
from typing import Literal, cast

import click

from converge.core.config import ConvergeConfig
from converge.core.env import load_environment
from converge.core.logging import setup_logging
from converge.observability.opik_client import configure_opik
from converge.orchestration.coordinator import Coordinator

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
) -> None:
    """Coordinate changes across multiple repositories."""
    load_environment()
    setup_logging(level=log_level)

    try:
        if no_tracing:
            os.environ["OPIK_TRACK_DISABLE"] = "true"
        configure_opik()

        config = ConvergeConfig(
            goal=goal,
            repos=list(repos),
            max_rounds=max_rounds,
            output_dir=output_dir,
            log_level=log_level,
            model=model,
            no_llm=no_llm,
            hil_mode=cast(Literal["conditional", "interrupt"], hil_mode.lower()),
        )

        coordinator = Coordinator(config)
        final_state = coordinator.coordinate()

        logger.info("Status: %s", final_state["status"])
        logger.info("Rounds Executed: %d", final_state["round"])
        logger.info("Artifacts Location: %s", coordinator.run_dir)

        if final_state["status"] == "HITL_REQUIRED":
            sys.exit(2)
        if final_state["status"] == "FAILED":
            sys.exit(1)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during coordination: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    cli()
