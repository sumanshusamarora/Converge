"""LangGraph workflow for repository coordination."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from converge.llm.openai_client import OpenAIClient, heuristic_proposal
from converge.observability.opik_client import opik_track
from converge.orchestration.state import EventRecord, OrchestrationState, RepositorySignal

logger = logging.getLogger(__name__)


def _record_event(node: str, message: str) -> EventRecord:
    return {"node": node, "message": message}


@opik_track("collect_constraints_node")
def collect_constraints_node(state: OrchestrationState) -> OrchestrationState:
    """Discover repository constraints and technology signals."""
    repos: list[RepositorySignal] = []

    for repo in state["repos"]:
        path = Path(repo["path"])
        exists = path.exists()
        signals: list[str] = []
        constraints: list[str] = []
        repo_type = "unknown"

        if not exists:
            constraints.append("repo path not found")
        else:
            signal_files = ["pyproject.toml", "requirements.txt", "package.json", "README.md"]
            signals = [signal for signal in signal_files if (path / signal).exists()]
            if "pyproject.toml" in signals or "requirements.txt" in signals:
                repo_type = "python"
                constraints.append("Python project detected")
            elif "package.json" in signals:
                repo_type = "node"
                constraints.append("Node project detected")

            if "README.md" in signals:
                constraints.append("Repository documentation found")

        repos.append(
            {
                "path": str(path),
                "exists": exists,
                "repo_type": repo_type,
                "signals": signals,
                "constraints": constraints or ["No obvious constraints detected"],
            }
        )

    state["repos"] = repos
    state["events"].append(_record_event("collect_constraints_node", "constraints collected"))
    return state


@opik_track("propose_split_node")
def propose_split_node(state: OrchestrationState) -> OrchestrationState:
    """Propose responsibility split using OpenAI or fallback heuristic."""
    repo_summaries: list[dict[str, Any]] = [
        {"path": repo["path"], "repo_type": repo["repo_type"], "signals": repo["signals"]}
        for repo in state["repos"]
    ]

    if state["no_llm"]:
        proposal = heuristic_proposal(state["goal"], repo_summaries)
        proposal["questions_for_hitl"].append("LLM disabled by --no-llm; using heuristic proposal")
    else:
        proposal = OpenAIClient(model=state["model"]).propose_responsibility_split(
            state["goal"], repo_summaries
        )

    state["proposal"] = proposal
    state["events"].append(_record_event("propose_split_node", "proposal generated"))
    return state


@opik_track("decide_node")
def decide_node(state: OrchestrationState) -> OrchestrationState:
    """Apply bounded convergence and decide final status."""
    state["round"] = min(state["round"] + 1, state["max_rounds"])
    missing_repos = any(not repo["exists"] for repo in state["repos"])
    ambiguous = not state["proposal"].get("proposal")

    if missing_repos or ambiguous:
        state["status"] = "HITL_REQUIRED"
    else:
        state["status"] = "CONVERGED"

    state["events"].append(
        _record_event(
            "decide_node",
            f"status={state['status']}, round={state['round']}/{state['max_rounds']}",
        )
    )
    return state


@opik_track("write_artifacts_node")
def write_artifacts_node(state: OrchestrationState) -> OrchestrationState:
    """Write run artifacts for human and machine consumption."""
    artifacts_dir = state["artifacts_dir"]
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = [
        "# Coordination Summary",
        "",
        f"**Goal:** {state['goal']}",
        f"**Status:** {state['status']}",
        f"**Rounds:** {state['round']} / {state['max_rounds']}",
        "",
        "## Constraints Collected",
        "",
    ]

    for repo in state["repos"]:
        summary_lines.append(f"### {repo['path']}")
        for constraint in repo["constraints"]:
            summary_lines.append(f"- {constraint}")
        summary_lines.append("")

    summary_lines.extend(
        [
            "## Proposed Responsibility Split",
            "",
            f"**Rationale:** {state['proposal'].get('rationale', '')}",
            "",
        ]
    )
    for risk in state["proposal"].get("risks", []):
        summary_lines.append(f"- Risk: {risk}")

    (artifacts_dir / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    matrix_lines = ["# Responsibility Matrix", "", f"**Goal:** {state['goal']}", ""]
    assignments = state["proposal"].get("proposal", {}).get("assignments", {})
    if isinstance(assignments, dict):
        for repo, responsibilities in assignments.items():
            matrix_lines.append(f"## {repo}")
            matrix_lines.append("")
            if isinstance(responsibilities, list):
                for responsibility in responsibilities:
                    matrix_lines.append(f"- {responsibility}")
            matrix_lines.append("")
    (artifacts_dir / "responsibility-matrix.md").write_text(
        "\n".join(matrix_lines),
        encoding="utf-8",
    )

    constraints_payload = {
        "goal": state["goal"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": state["repos"],
    }
    (artifacts_dir / "constraints.json").write_text(
        json.dumps(constraints_payload, indent=2),
        encoding="utf-8",
    )

    run_payload = {
        "goal": state["goal"],
        "status": state["status"],
        "round": state["round"],
        "max_rounds": state["max_rounds"],
        "events": state["events"],
    }
    (artifacts_dir / "run.json").write_text(json.dumps(run_payload, indent=2), encoding="utf-8")
    state["events"].append(_record_event("write_artifacts_node", "artifacts written"))
    return state


def build_coordinate_graph() -> Any:
    """Build LangGraph workflow for coordinate command."""
    graph = StateGraph(OrchestrationState)
    graph.add_node("collect_constraints_node", collect_constraints_node)
    graph.add_node("propose_split_node", propose_split_node)
    graph.add_node("decide_node", decide_node)
    graph.add_node("write_artifacts_node", write_artifacts_node)

    graph.set_entry_point("collect_constraints_node")
    graph.add_edge("collect_constraints_node", "propose_split_node")
    graph.add_edge("propose_split_node", "decide_node")
    graph.add_edge("decide_node", "write_artifacts_node")
    graph.add_edge("write_artifacts_node", END)

    return graph.compile()
