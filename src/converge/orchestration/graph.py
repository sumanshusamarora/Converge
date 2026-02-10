"""LangGraph workflow for repository coordination."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

try:
    from langgraph.graph import END, StateGraph
    from langgraph.types import interrupt
except ImportError:  # pragma: no cover - used in offline/test fallback environments
    from converge.orchestration.langgraph_compat import (  # type: ignore[assignment]
        END,
        StateGraph,
        interrupt,
    )

from converge.agents.base import AgentTask, RepoContext
from converge.agents.factory import create_agent
from converge.llm.openai_client import OpenAIClient, heuristic_proposal
from converge.observability.opik_client import opik_track
from converge.orchestration.state import EventRecord, OrchestrationState, RepoPlan, RepositorySignal

logger = logging.getLogger(__name__)

RouteA = Literal["propose_split_node", "write_artifacts_node"]
RouteB = Literal["hitl_interrupt_node", "write_artifacts_node"]


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


@opik_track("agent_plan_node")
def agent_plan_node(state: OrchestrationState) -> OrchestrationState:
    """Use agent to plan changes for each repository.

    Creates an agent based on state["agent_provider"], then calls
    agent.plan() for each repository to produce structured proposals.
    """
    agent_provider = state.get("agent_provider", "codex")
    agent = create_agent(agent_provider)

    # Load AGENTS.md if it exists to provide instructions
    agents_md_path = Path(__file__).parents[3] / "AGENTS.md"
    instructions = ""
    if agents_md_path.exists():
        instructions = agents_md_path.read_text(encoding="utf-8")
    else:
        instructions = "Follow Converge best practices: minimal changes, clear ownership."

    repo_plans: list[RepoPlan] = []

    for repo in state["repos"]:
        repo_path = Path(repo["path"])

        # Build RepoContext
        readme_excerpt = None
        readme_path = repo_path / "README.md"
        if readme_path.exists():
            readme_content = readme_path.read_text(encoding="utf-8")
            # Take first 500 chars as excerpt
            readme_excerpt = readme_content[:500] if len(readme_content) > 500 else readme_content

        repo_context = RepoContext(
            path=repo_path,
            kind=repo.get("repo_type"),
            signals=repo.get("signals", []),
            readme_excerpt=readme_excerpt,
        )

        # Build AgentTask
        task = AgentTask(
            goal=state["goal"],
            repo=repo_context,
            instructions=instructions,
            max_steps=5,
        )

        # Call agent.plan()
        result = agent.plan(task)

        # Convert to RepoPlan
        plan: RepoPlan = {
            "repo_path": str(repo_path),
            "provider": result.provider.value,
            "status": result.status,
            "summary": result.summary,
            "proposed_changes": result.proposed_changes,
            "questions_for_hitl": result.questions_for_hitl,
            "raw": result.raw,
        }

        repo_plans.append(plan)

        logger.info(
            "agent_plan completed: repo=%s, provider=%s, status=%s",
            repo_path,
            result.provider.value,
            result.status,
        )

    state["repo_plans"] = repo_plans
    state["events"].append(
        _record_event("agent_plan_node", f"generated {len(repo_plans)} repo plans")
    )
    return state


@opik_track("decide_node")
def decide_node(state: OrchestrationState) -> OrchestrationState:
    """Apply bounded convergence and decide current status."""
    state["round"] += 1
    missing_repos = any(not repo["exists"] for repo in state["repos"])
    ambiguous = not state["proposal"].get("proposal")

    # Check agent plan statuses if available
    agent_hitl_required = False
    agent_failed = False
    if "repo_plans" in state and state["repo_plans"]:
        for plan in state["repo_plans"]:
            if plan["status"] == "FAILED":
                agent_failed = True
            elif plan["status"] == "HITL_REQUIRED":
                agent_hitl_required = True

    if agent_failed:
        state["status"] = "FAILED"
    elif missing_repos or ambiguous or agent_hitl_required:
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


def route_after_decide(state: OrchestrationState) -> RouteA:
    """Route for conditional mode with bounded retry loop."""
    if state["status"] == "HITL_REQUIRED" and state["round"] < state["max_rounds"]:
        destination: RouteA = "propose_split_node"
    else:
        destination = "write_artifacts_node"
    state["events"].append(_record_event("route_after_decide", f"destination={destination}"))
    return destination


def route_after_decide_interrupt(state: OrchestrationState) -> RouteB:
    """Route for interrupt mode: pause on HITL, otherwise complete run."""
    if state["status"] == "HITL_REQUIRED":
        destination: RouteB = "hitl_interrupt_node"
    else:
        destination = "write_artifacts_node"
    state["events"].append(
        _record_event("route_after_decide_interrupt", f"destination={destination}")
    )
    return destination


@opik_track("hitl_interrupt_node")
def hitl_interrupt_node(state: OrchestrationState) -> OrchestrationState:
    """Pause for human decision when HITL is required."""
    payload = {
        "goal": state["goal"],
        "repos": state["repos"],
        "proposal": state["proposal"],
        "round": state["round"],
        "max_rounds": state["max_rounds"],
        "suggested_human_actions": [
            "Accept current split and proceed",
            "Request another split attempt with clarified ownership",
            "Escalate to architecture/security review",
        ],
    }
    state["events"].append(_record_event("hitl_interrupt_node", "hitl interrupt requested"))

    resumed_value = interrupt(payload)
    decision: dict[str, Any]
    if isinstance(resumed_value, dict) and "human_decision" in resumed_value:
        decision = dict(resumed_value["human_decision"])
    elif isinstance(resumed_value, dict):
        decision = dict(resumed_value)
    else:
        decision = {"action": "unknown"}

    state["human_decision"] = decision
    state["events"].append(_record_event("hitl_decision_received", "human decision recorded"))
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

    # Add agent plans section if available
    if "repo_plans" in state and state["repo_plans"]:
        summary_lines.extend(
            [
                "## Agent Plans",
                "",
            ]
        )
        for plan in state["repo_plans"]:
            summary_lines.append(f"### {plan['repo_path']}")
            summary_lines.append(f"**Provider:** {plan['provider']}")
            summary_lines.append(f"**Status:** {plan['status']}")
            summary_lines.append(f"**Summary:** {plan['summary']}")
            summary_lines.append("")
            summary_lines.append("**Proposed Changes:**")
            for change in plan["proposed_changes"]:
                summary_lines.append(f"- {change}")
            if plan["questions_for_hitl"]:
                summary_lines.append("")
                summary_lines.append("**Questions for HITL:**")
                for question in plan["questions_for_hitl"]:
                    summary_lines.append(f"- {question}")
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

    if state.get("human_decision"):
        summary_lines.extend(["", "## Human Decision", "", f"- {state['human_decision']}"])

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
        "human_decision": state.get("human_decision"),
        "events": state["events"],
        "repo_plans": state.get("repo_plans", []),
    }
    (artifacts_dir / "run.json").write_text(json.dumps(run_payload, indent=2), encoding="utf-8")

    # Write prompts directory if repo_plans exist (deprecated structure, kept for compatibility)
    if "repo_plans" in state and state["repo_plans"]:
        prompts_dir = artifacts_dir / "prompts"
        prompts_dir.mkdir(exist_ok=True)

        for i, plan in enumerate(state["repo_plans"]):
            repo_name = Path(plan["repo_path"]).name or f"repo_{i}"
            provider = plan["provider"]

            # Write basic prompt for backward compatibility
            prompt_filename = f"{repo_name}_{provider}_prompt.txt"
            prompt_path = prompts_dir / prompt_filename

            prompt_content = f"""# {provider.upper()} Prompt for {plan["repo_path"]}

Goal: {state["goal"]}
Status: {plan["status"]}

Summary: {plan["summary"]}

Proposed Changes:
"""
            for change in plan["proposed_changes"]:
                prompt_content += f"- {change}\n"

            if plan["questions_for_hitl"]:
                prompt_content += "\nQuestions for HITL:\n"
                for question in plan["questions_for_hitl"]:
                    prompt_content += f"- {question}\n"

            prompt_path.write_text(prompt_content, encoding="utf-8")

    # Write structured repo-plans directory (NEW: Handoff Pack)
    if "repo_plans" in state and state["repo_plans"]:
        repo_plans_dir = artifacts_dir / "repo-plans"
        repo_plans_dir.mkdir(exist_ok=True)

        for i, plan in enumerate(state["repo_plans"]):
            repo_name = Path(plan["repo_path"]).name or f"repo_{i}"
            repo_plan_dir = repo_plans_dir / repo_name
            repo_plan_dir.mkdir(exist_ok=True)

            # 1. Write plan.md - human-readable plan summary
            plan_md_lines = [
                f"# Plan: {plan['repo_path']}",
                "",
                f"**Goal:** {state['goal']}",
                f"**Provider:** {plan['provider']}",
                f"**Status:** {plan['status']}",
                "",
                "## Summary",
                "",
                plan["summary"],
                "",
                "## Proposed Changes",
                "",
            ]
            for change in plan["proposed_changes"]:
                plan_md_lines.append(f"- {change}")

            if plan["questions_for_hitl"]:
                plan_md_lines.extend(["", "## Questions for HITL", ""])
                for question in plan["questions_for_hitl"]:
                    plan_md_lines.append(f"- {question}")

            (repo_plan_dir / "plan.md").write_text("\n".join(plan_md_lines), encoding="utf-8")

            # 2. Write copilot-prompt.txt - VS Code ready prompt
            copilot_prompt = plan.get("raw", {}).get("copilot_prompt", "")
            if copilot_prompt:
                (repo_plan_dir / "copilot-prompt.txt").write_text(
                    str(copilot_prompt), encoding="utf-8"
                )
            else:
                # Generate a basic prompt if not available
                basic_prompt = f"""# Task for {plan["repo_path"]}

Goal: {state["goal"]}

{plan["summary"]}

Proposed Changes:
"""
                for change in plan["proposed_changes"]:
                    basic_prompt += f"- {change}\n"
                (repo_plan_dir / "copilot-prompt.txt").write_text(basic_prompt, encoding="utf-8")

            # 3. Write commands.sh - execution hints (if available)
            commands = []
            signals = plan.get("raw", {}).get("signals", [])
            if "pyproject.toml" in signals:
                commands.extend(
                    [
                        "# Python project detected",
                        "# Install dependencies:",
                        "# pip install -e .[dev]",
                        "",
                        "# Run tests:",
                        "# pytest",
                        "",
                        "# Type check:",
                        "# mypy src/",
                        "",
                        "# Format and lint:",
                        "# ruff format .",
                        "# ruff check .",
                    ]
                )
            elif "package.json" in signals:
                commands.extend(
                    [
                        "# Node project detected",
                        "# Install dependencies:",
                        "# npm install",
                        "",
                        "# Run tests:",
                        "# npm test",
                        "",
                        "# Type check:",
                        "# npm run typecheck",
                        "",
                        "# Lint:",
                        "# npm run lint",
                    ]
                )
            else:
                commands.append("# No specific commands detected for this repository type")

            if commands:
                commands_content = "#!/bin/bash\n" + "\n".join(commands) + "\n"
                (repo_plan_dir / "commands.sh").write_text(commands_content, encoding="utf-8")

    state["events"].append(_record_event("write_artifacts_node", "artifacts written"))
    return state


def build_coordinate_graph_conditional() -> Any:
    """Build graph with conditional edges and bounded retry loop."""
    graph = StateGraph(OrchestrationState)
    graph.add_node("collect_constraints_node", collect_constraints_node)
    graph.add_node("propose_split_node", propose_split_node)
    graph.add_node("agent_plan_node", agent_plan_node)
    graph.add_node("decide_node", decide_node)
    graph.add_node("write_artifacts_node", write_artifacts_node)

    graph.set_entry_point("collect_constraints_node")
    graph.add_edge("collect_constraints_node", "propose_split_node")
    graph.add_edge("propose_split_node", "agent_plan_node")
    graph.add_edge("agent_plan_node", "decide_node")
    graph.add_conditional_edges("decide_node", route_after_decide)
    graph.add_edge("write_artifacts_node", END)
    return graph.compile()


def build_coordinate_graph_interrupt() -> Any:
    """Build graph that interrupts for human input when HITL is required."""
    graph = StateGraph(OrchestrationState)
    graph.add_node("collect_constraints_node", collect_constraints_node)
    graph.add_node("propose_split_node", propose_split_node)
    graph.add_node("agent_plan_node", agent_plan_node)
    graph.add_node("decide_node", decide_node)
    graph.add_node("hitl_interrupt_node", hitl_interrupt_node)
    graph.add_node("write_artifacts_node", write_artifacts_node)

    graph.set_entry_point("collect_constraints_node")
    graph.add_edge("collect_constraints_node", "propose_split_node")
    graph.add_edge("propose_split_node", "agent_plan_node")
    graph.add_edge("agent_plan_node", "decide_node")
    graph.add_conditional_edges("decide_node", route_after_decide_interrupt)
    graph.add_edge("hitl_interrupt_node", "write_artifacts_node")
    graph.add_edge("write_artifacts_node", END)
    return graph.compile()
