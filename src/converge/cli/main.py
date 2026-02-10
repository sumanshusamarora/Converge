"""Command-line interface for Converge."""

import logging
import sys

import click

from converge.core.config import ConvergeConfig
from converge.core.logging import setup_logging
from converge.orchestration.coordinator import Coordinator

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Converge: Multi-repository coordination and governance tool.

    Converge helps multiple repositories that build one product
    collaborate, decide, and converge safely.
    """
    pass


@cli.command()
@click.option(
    "--goal",
    required=True,
    help="The high-level goal to achieve across repositories",
)
@click.option(
    "--repos",
    required=True,
    multiple=True,
    help="Repository identifiers (can be specified multiple times)",
)
@click.option(
    "--max-rounds",
    default=2,
    type=int,
    help="Maximum number of convergence rounds (default: 2)",
)
@click.option(
    "--output-dir",
    default="./converge-output",
    help="Directory for output artifacts (default: ./converge-output)",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
def coordinate(
    goal: str,
    repos: tuple[str, ...],
    max_rounds: int,
    output_dir: str,
    log_level: str,
) -> None:
    """Coordinate changes across multiple repositories.

    This command orchestrates multi-repository coordination:
    1. Collects constraints from each repository
    2. Proposes a responsibility split
    3. Executes bounded convergence rounds
    4. Generates human-readable artifacts

    Example:
        converge coordinate --goal "Add discount_code support" --repos api --repos web
    """
    # Setup logging
    setup_logging(level=log_level)

    try:
        # Create configuration
        config = ConvergeConfig(
            goal=goal,
            repos=list(repos),
            max_rounds=max_rounds,
            output_dir=output_dir,
            log_level=log_level,
        )

        logger.info("=" * 80)
        logger.info("Converge Coordination Session")
        logger.info("=" * 80)
        logger.info("Goal: %s", config.goal)
        logger.info("Repositories: %s", ", ".join(config.repos))
        logger.info("Max Rounds: %d", config.max_rounds)
        logger.info("Output Directory: %s", config.output_dir)
        logger.info("=" * 80)

        # Execute coordination
        coordinator = Coordinator(config)
        final_state = coordinator.coordinate()

        # Report results
        logger.info("=" * 80)
        logger.info("Coordination Complete")
        logger.info("=" * 80)
        logger.info("Status: %s", final_state.status.value)
        logger.info("Rounds Executed: %d", final_state.round_number)
        logger.info("Artifacts Location: %s", config.output_dir)

        if final_state.escalation_reason:
            logger.warning("ESCALATION REQUIRED: %s", final_state.escalation_reason)
            logger.warning("Human review and decision needed.")

        logger.info("=" * 80)

        # Exit with appropriate code
        if final_state.status.value == "escalated":
            sys.exit(2)  # Escalation exit code
        elif final_state.status.value == "failed":
            sys.exit(1)  # Failure exit code

    except ValueError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error during coordination: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
