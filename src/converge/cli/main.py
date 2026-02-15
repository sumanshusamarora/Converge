"""Command-line interface for Converge."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import click

from converge.agents.codex_agent import CodexAgent
from converge.core.config import load_queue_settings, load_server_settings
from converge.core.env import load_environment
from converge.core.logging import setup_logging
from converge.observability.opik_client import configure_opik
from converge.orchestration.runner import run_coordinate
from converge.queue.factory import create_queue
from converge.queue.schemas import TaskRequest, TaskResult, TaskStatus
from converge.worker.poller import PollingWorker

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Converge: Multi-repository coordination and governance tool.

    Converge helps multiple repositories that build one product
    collaborate, decide, and converge safely.
    """


@cli.command("install-codex-cli")
@click.option(
    "--package-manager",
    default="auto",
    type=click.Choice(["auto", "npm", "pnpm", "yarn"], case_sensitive=False),
    help="Package manager to use for Codex CLI install",
)
@click.option(
    "--run",
    "run_script",
    is_flag=True,
    default=False,
    help="Execute the install script immediately",
)
def install_codex_cli(package_manager: str, run_script: bool) -> None:
    """Print or run a script that installs Codex CLI."""
    selected_pm = _resolve_package_manager(package_manager.lower())
    script = _build_codex_install_script(selected_pm)

    if not run_script:
        click.echo(script)
        return

    result = subprocess.run(
        ["/bin/bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            f"Codex CLI install failed (exit={result.returncode}): {(result.stderr or '').strip()}"
        )

    click.echo((result.stdout or "").strip())


@cli.command("doctor")
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Print diagnostics as JSON",
)
def doctor(json_output: bool) -> None:
    """Show runtime diagnostics for planning/execution setup."""
    load_environment()
    diagnostics = CodexAgent().plan_diagnostics()

    if json_output:
        click.echo(json.dumps(diagnostics, indent=2, sort_keys=True))
        return

    planning_mode = str(diagnostics.get("planning_mode", "heuristic"))
    should_attempt = bool(diagnostics.get("should_attempt_codex_plan", False))
    codex_binary = diagnostics.get("codex_binary")
    fallback_reasons = diagnostics.get("fallback_reasons", [])
    recommendations = diagnostics.get("recommendations", [])
    login_status = diagnostics.get("codex_login_status", {})
    codex_model_configured = diagnostics.get("codex_model_configured")
    codex_model_selected = diagnostics.get("codex_model_selected")
    codex_model_candidates = diagnostics.get("codex_model_candidates", [])
    codex_plan_mode = diagnostics.get("codex_plan_mode")

    status_label = "PASS" if planning_mode == "codex_cli" else "WARN"
    click.echo(f"{status_label}: Codex planning mode = {planning_mode}")
    click.echo(f"should_attempt_codex_plan: {str(should_attempt).lower()}")
    if codex_plan_mode:
        click.echo(f"codex_plan_mode: {codex_plan_mode}")
    click.echo(f"codex_path: {diagnostics.get('codex_path')}")
    click.echo(f"codex_binary: {codex_binary or 'not found'}")
    click.echo(f"codex_model_configured: {codex_model_configured or 'auto'}")
    click.echo(f"codex_model_selected: {codex_model_selected or 'not_selected_yet'}")
    if isinstance(codex_model_candidates, list) and codex_model_candidates:
        candidates = ", ".join(str(item) for item in codex_model_candidates)
        click.echo(f"codex_model_candidates: {candidates}")

    if isinstance(login_status, dict):
        checked = bool(login_status.get("checked", False))
        if checked:
            auth_state = login_status.get("authenticated")
            if auth_state is True:
                auth_text = "true"
            elif auth_state is False:
                auth_text = "false"
            else:
                auth_text = "unknown"
            click.echo(f"codex_authenticated: {auth_text}")
        else:
            click.echo("codex_authenticated: not_checked")

    if isinstance(fallback_reasons, list) and fallback_reasons:
        click.echo("fallback_reasons:")
        for reason in fallback_reasons:
            click.echo(f"- {reason}")
    else:
        click.echo("fallback_reasons: none")

    if isinstance(recommendations, list) and recommendations:
        click.echo("recommendations:")
        for recommendation in recommendations:
            click.echo(f"- {recommendation}")


def _resolve_package_manager(package_manager: str) -> str:
    if package_manager != "auto":
        return package_manager

    for candidate in ("npm", "pnpm", "yarn"):
        if shutil.which(candidate):
            return candidate
    return "npm"


def _build_codex_install_script(package_manager: str) -> str:
    install_cmds = {
        "npm": "npm install -g @openai/codex",
        "pnpm": "pnpm add -g @openai/codex",
        "yarn": "yarn global add @openai/codex",
    }
    install_cmd = install_cmds[package_manager]
    return textwrap.dedent(f"""\
        set -euo pipefail
        if ! command -v {package_manager} >/dev/null 2>&1; then
          echo "{package_manager} is not installed. Please install it first."
          exit 1
        fi
        {install_cmd}
        codex --version
        """)


@cli.command()
@click.option(
    "--goal", required=True, help="The high-level goal to achieve across repositories"
)
@click.option(
    "--repos",
    required=True,
    multiple=True,
    help="Repository identifiers (can be specified multiple times)",
)
@click.option(
    "--max-rounds", default=2, type=int, help="Maximum number of convergence rounds"
)
@click.option(
    "--output-dir",
    default=".converge",
    help="Base directory for output artifacts (default: .converge)",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    help="Logging level (default: INFO)",
)
@click.option(
    "--model", default=None, help="Override OpenAI model for proposal generation"
)
@click.option(
    "--coding-agent-model",
    default=None,
    help="Override coding-agent planning model (otherwise auto-selects best available)",
)
@click.option(
    "--no-llm", is_flag=True, default=False, help="Force heuristic proposal generation"
)
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
    "--coding-agent",
    default=None,
    type=click.Choice(["codex", "copilot"], case_sensitive=False),
    help="Coding agent to use (default: from CONVERGE_CODING_AGENT or codex)",
)
@click.option(
    "--enable-agent-exec",
    is_flag=True,
    default=False,
    help="Enable coding-agent execution (provider support required)",
)
def coordinate(
    goal: str,
    repos: tuple[str, ...],
    max_rounds: int,
    output_dir: str,
    log_level: str,
    model: str | None,
    coding_agent_model: str | None,
    no_llm: bool,
    no_tracing: bool,
    hil_mode: str,
    coding_agent: str | None,
    enable_agent_exec: bool,
) -> None:
    """Coordinate changes across multiple repositories."""
    load_environment()
    setup_logging(level=log_level)

    persisted_task_id: str | None = None
    queue = None
    project_id: str | None = None
    project_name: str | None = None
    project_preferences: dict[str, object] | None = None
    project_instructions: str | None = None

    try:
        if no_tracing:
            os.environ["OPIK_TRACK_DISABLE"] = "true"
        configure_opik()
        if model:
            os.environ["CONVERGE_OPENAI_MODEL"] = model
        if coding_agent_model:
            os.environ["CONVERGE_CODING_AGENT_MODEL"] = coding_agent_model
        if no_llm:
            os.environ["CONVERGE_NO_LLM"] = "true"
        os.environ["CONVERGE_HIL_MODE"] = hil_mode.lower()
        if enable_agent_exec:
            os.environ["CONVERGE_CODING_AGENT_EXEC_ENABLED"] = "true"

        queue_settings = load_queue_settings()
        if queue_settings.backend == "db" and queue_settings.sqlalchemy_database_uri:
            queue = create_queue()
            task_request = TaskRequest(
                goal=goal,
                repos=list(repos),
                max_rounds=max_rounds,
                agent_provider=coding_agent,
                metadata={
                    "source": "cli.coordinate",
                    "hil_mode": hil_mode.lower(),
                    "no_llm": no_llm,
                    "output_dir": output_dir,
                },
            )
            task = queue.enqueue(task_request)
            persisted_task_id = task.id
            project_id = task.project_id
            project = queue.get_project(task.project_id)
            project_name = project.name
            project_preferences = project.preferences.model_dump()
            project_instructions = project.default_instructions
            queue.mark_running(task.id)
            logger.info("Persisted CLI run as task: %s", task.id)
        elif queue_settings.backend == "db":
            logger.warning(
                "SQLALCHEMY_DATABASE_URI is not set; running without task persistence"
            )

        outcome = run_coordinate(
            goal=goal,
            repos=list(repos),
            max_rounds=max_rounds,
            agent_provider=coding_agent,
            base_output_dir=Path(output_dir),
            thread_id=persisted_task_id,
            project_id=project_id,
            project_name=project_name,
            project_preferences=project_preferences,
            project_instructions=project_instructions,
        )

        if queue is not None and persisted_task_id is not None:
            if outcome.status == "FAILED":
                queue.fail(persisted_task_id, outcome.summary[:500], retryable=False)
            else:
                result_status = (
                    TaskStatus.HITL_REQUIRED
                    if outcome.status == "HITL_REQUIRED"
                    else TaskStatus.SUCCEEDED
                )
                queue.complete(
                    persisted_task_id,
                    TaskResult(
                        status=result_status,
                        summary=outcome.summary,
                        artifacts_dir=outcome.artifacts_dir,
                        hitl_questions=outcome.hitl_questions,
                    ),
                )

        logger.info("Status: %s", outcome.status)
        logger.info("Artifacts Location: %s", outcome.artifacts_dir)
        if persisted_task_id is not None:
            logger.info("Task ID: %s", persisted_task_id)

        if outcome.status == "HITL_REQUIRED":
            sys.exit(2)
        if outcome.status == "FAILED":
            sys.exit(1)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        if queue is not None and persisted_task_id is not None:
            try:
                queue.fail(persisted_task_id, str(exc)[:500], retryable=False)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to mark persisted task as FAILED")
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
@click.option(
    "--poll-interval", type=float, default=None, help="Polling interval in seconds"
)
@click.option(
    "--batch-size", type=int, default=None, help="Number of tasks to claim per cycle"
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
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
            raise ValueError(
                "SQLALCHEMY_DATABASE_URI is required when CONVERGE_QUEUE_BACKEND=db"
            )

        worker_poll_interval = (
            poll_interval
            if poll_interval is not None
            else settings.worker_poll_interval_seconds
        )
        worker_batch_size = (
            batch_size if batch_size is not None else settings.worker_batch_size
        )

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
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
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
