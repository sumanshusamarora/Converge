"""LangGraph workflow for repository coordination."""

from __future__ import annotations

import hashlib
import json
import logging
import re
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
from converge.orchestration.state import EventRecord, OrchestrationState, RepoPlan, RepositorySignal

logger = logging.getLogger(__name__)

RouteA = Literal["propose_split_node", "write_artifacts_node"]
RouteB = Literal["hitl_interrupt_node", "write_artifacts_node"]

_SKIP_SCAN_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".converge",
}
_SCAN_SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".cs",
    ".rs",
    ".swift",
}
_MAX_SCAN_FILES = 3000
_MAX_FILE_BYTES = 1_000_000


def _record_event(node: str, message: str) -> EventRecord:
    return {"node": node, "message": message}


def _iter_repo_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    if not repo_path.exists():
        return files

    for path in repo_path.rglob("*"):
        if len(files) >= _MAX_SCAN_FILES:
            break
        if path.is_dir():
            if path.name in _SKIP_SCAN_DIRS:
                continue
            continue
        if any(part in _SKIP_SCAN_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _safe_read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _infer_repo_type_from_sources(repo_path: Path) -> tuple[str, str | None]:
    """Infer repo type from source extension counts when marker files are absent."""
    python_extensions = {".py"}
    node_extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

    python_count = 0
    node_count = 0

    for path in _iter_repo_files(repo_path):
        suffix = path.suffix.lower()
        if suffix in python_extensions:
            python_count += 1
        elif suffix in node_extensions:
            node_count += 1

    if python_count == 0 and node_count == 0:
        return "unknown", None
    if python_count >= node_count:
        return "python", "python_sources"
    return "node", "node_sources"


def _is_contract_artifact(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()

    explicit_names = {
        "openapi.yaml",
        "openapi.yml",
        "openapi.json",
        "asyncapi.yaml",
        "asyncapi.yml",
        "asyncapi.json",
    }
    if name in explicit_names:
        return True

    if (
        name.endswith(".openapi.yaml")
        or name.endswith(".openapi.yml")
        or name.endswith(".openapi.json")
    ):
        return True
    if (
        name.endswith(".asyncapi.yaml")
        or name.endswith(".asyncapi.yml")
        or name.endswith(".asyncapi.json")
    ):
        return True

    if suffix in {".proto", ".graphql", ".gql", ".avsc"}:
        return True

    return name.endswith(".schema.json") or name.endswith(".jsonschema.json")


def _normalize_path(path: str) -> str:
    normalized = path.split("?", 1)[0].strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    canonical_segments: list[str] = []
    for segment in normalized.split("/"):
        if not segment:
            continue
        if re.fullmatch(r"[0-9]+", segment):
            canonical_segments.append("{id}")
            continue
        if re.fullmatch(r"[0-9a-fA-F-]{16,}", segment):
            canonical_segments.append("{id}")
            continue
        canonical_segments.append(segment)

    if not canonical_segments:
        return "/"
    return "/" + "/".join(canonical_segments)


def _extract_openapi_paths(text: str) -> set[str]:
    paths: set[str] = set()

    try:
        payload = json.loads(text)
        payload_paths = payload.get("paths")
        if isinstance(payload_paths, dict):
            for candidate in payload_paths:
                if isinstance(candidate, str):
                    paths.add(_normalize_path(candidate))
            return paths
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r"^\s{0,4}(/[^:\s]+)\s*:\s*$", text, flags=re.MULTILINE):
        paths.add(_normalize_path(match.group(1)))
    return paths


def _extract_asyncapi_channels(text: str) -> set[str]:
    channels: set[str] = set()
    try:
        payload = json.loads(text)
        payload_channels = payload.get("channels")
        if isinstance(payload_channels, dict):
            for candidate in payload_channels:
                if isinstance(candidate, str):
                    channels.add(candidate.strip())
            return channels
    except json.JSONDecodeError:
        pass

    in_channels = False
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.strip() == "channels:":
            in_channels = True
            continue
        if in_channels and re.match(r"^\S", stripped):
            break
        if in_channels:
            match = re.match(r"^\s{2,}([A-Za-z0-9_.\-/{}/]+)\s*:\s*$", stripped)
            if match:
                channels.add(match.group(1))
    return channels


def _extract_proto_symbols(text: str) -> set[str]:
    symbols: set[str] = set()
    for match in re.finditer(r"\bservice\s+([A-Za-z0-9_]+)", text):
        symbols.add(f"rpc:service:{match.group(1)}")
    for match in re.finditer(r"\brpc\s+([A-Za-z0-9_]+)\s*\(", text):
        symbols.add(f"rpc:method:{match.group(1)}")
    return symbols


def _extract_graphql_symbols(text: str) -> set[str]:
    symbols: set[str] = set()
    for match in re.finditer(r"\btype\s+([A-Za-z0-9_]+)\s*{", text):
        symbols.add(f"graphql:type:{match.group(1)}")
    for match in re.finditer(r"\b(query|mutation|subscription)\s+([A-Za-z0-9_]+)", text):
        symbols.add(f"graphql:operation:{match.group(2)}")
    return symbols


def _extract_schema_symbols(path: Path, text: str) -> set[str]:
    symbols: set[str] = set()
    try:
        payload = json.loads(text)
        title = payload.get("title")
        if isinstance(title, str) and title.strip():
            symbols.add(f"schema:title:{title.strip()}")
    except json.JSONDecodeError:
        pass
    symbols.add(f"schema:file:{path.stem}")
    return symbols


def _extract_declared_contract_ids(path: Path, text: str) -> set[str]:
    name = path.name.lower()
    ids: set[str] = set()

    if "openapi" in name:
        for api_path in _extract_openapi_paths(text):
            ids.add(f"http:path:{api_path}")
        ids.add(f"contract:file:{name}")
        return ids

    if "asyncapi" in name:
        for channel in _extract_asyncapi_channels(text):
            ids.add(f"event:channel:{channel}")
        ids.add(f"contract:file:{name}")
        return ids

    suffix = path.suffix.lower()
    if suffix == ".proto":
        ids.update(_extract_proto_symbols(text))
    elif suffix in {".graphql", ".gql"}:
        ids.update(_extract_graphql_symbols(text))
    elif suffix == ".avsc" or name.endswith(".schema.json") or name.endswith(".jsonschema.json"):
        ids.update(_extract_schema_symbols(path, text))

    ids.add(f"contract:file:{name}")
    return ids


def _extract_consumed_contract_refs(path: Path, text: str) -> set[str]:
    refs: set[str] = set()
    if path.suffix.lower() not in _SCAN_SOURCE_EXTENSIONS:
        return refs

    for match in re.finditer(r"""['"](/api/[A-Za-z0-9_./\-{}:]+)['"]""", text):
        refs.add(f"http:path:{_normalize_path(match.group(1))}")

    for match in re.finditer(r"\b(query|mutation|subscription)\s+([A-Za-z0-9_]+)", text):
        refs.add(f"graphql:operation:{match.group(2)}")

    return refs


def _analyze_contract_alignment(state: OrchestrationState) -> dict[str, Any]:
    repo_summaries: list[dict[str, Any]] = []
    issues: list[str] = []
    declared_map: dict[str, list[dict[str, str]]] = {}
    provided_http_paths: set[str] = set()
    consumed_http_refs: list[tuple[str, str]] = []
    consumed_graphql_refs: list[tuple[str, str]] = []
    provided_graphql_symbols: set[str] = set()

    for repo in state["repos"]:
        repo_path = Path(repo["path"])
        artifacts: list[dict[str, Any]] = []
        declared_contract_ids: set[str] = set()
        consumed_contract_ids: set[str] = set()

        if repo_path.exists():
            for file_path in _iter_repo_files(repo_path):
                text = _safe_read_text(file_path)
                if text is None:
                    continue

                relative_path = str(file_path.relative_to(repo_path))
                if _is_contract_artifact(file_path):
                    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
                    ids = _extract_declared_contract_ids(file_path, text)
                    declared_contract_ids.update(ids)
                    artifacts.append(
                        {
                            "path": relative_path,
                            "hash": content_hash,
                            "contract_ids": sorted(ids),
                        }
                    )

                    artifact_key = relative_path.lower()
                    declared_map.setdefault(artifact_key, []).append(
                        {
                            "repo_path": str(repo_path),
                            "hash": content_hash,
                            "path": relative_path,
                        }
                    )

                    for contract_id in ids:
                        if contract_id.startswith("http:path:"):
                            provided_http_paths.add(contract_id)
                        if contract_id.startswith("graphql:operation:"):
                            provided_graphql_symbols.add(contract_id)
                else:
                    consumed = _extract_consumed_contract_refs(file_path, text)
                    consumed_contract_ids.update(consumed)

        for contract_id in consumed_contract_ids:
            if contract_id.startswith("http:path:"):
                consumed_http_refs.append((str(repo_path), contract_id))
            if contract_id.startswith("graphql:operation:"):
                consumed_graphql_refs.append((str(repo_path), contract_id))

        repo_summaries.append(
            {
                "repo_path": str(repo_path),
                "artifacts": artifacts,
                "declared_contract_ids": sorted(declared_contract_ids),
                "consumed_contract_ids": sorted(consumed_contract_ids),
            }
        )

    for relative_path, entries in declared_map.items():
        unique_hashes = {entry["hash"] for entry in entries}
        if len(entries) > 1 and len(unique_hashes) > 1:
            touched_repos = ", ".join(sorted({entry["repo_path"] for entry in entries}))
            issues.append(
                "Contract artifact drift detected for "
                f"'{relative_path}' across repos: {touched_repos}"
            )

    if provided_http_paths:
        for repo_path, ref in consumed_http_refs:
            if ref not in provided_http_paths:
                issues.append(f"{repo_path} consumes undefined API path contract: {ref}")

    if provided_graphql_symbols:
        for repo_path, ref in consumed_graphql_refs:
            if ref not in provided_graphql_symbols:
                issues.append(f"{repo_path} consumes undefined GraphQL contract: {ref}")

    return {
        "repos": repo_summaries,
        "issues": sorted(set(issues)),
        "summary": {
            "repo_count": len(repo_summaries),
            "artifact_count": sum(
                len(repo_summary["artifacts"]) for repo_summary in repo_summaries
            ),
            "issue_count": len(set(issues)),
        },
    }


def contract_alignment_node(state: OrchestrationState) -> OrchestrationState:
    """Analyze cross-repository contract declarations and potential mismatches."""
    analysis = _analyze_contract_alignment(state)
    state["contract_analysis"] = analysis
    issue_count = analysis.get("summary", {}).get("issue_count", 0)
    artifact_count = analysis.get("summary", {}).get("artifact_count", 0)
    state["events"].append(
        _record_event(
            "contract_alignment_node",
            f"contracts analyzed: artifacts={artifact_count}, issues={issue_count}",
        )
    )
    return state


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
            else:
                inferred_repo_type, inferred_signal = _infer_repo_type_from_sources(path)
                if inferred_repo_type != "unknown":
                    repo_type = inferred_repo_type
                    if inferred_signal and inferred_signal not in signals:
                        signals.append(inferred_signal)
                    if inferred_repo_type == "python":
                        constraints.append("Python sources detected (fallback scan)")
                    else:
                        constraints.append("Node sources detected (fallback scan)")

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

    contract_issues = state.get("contract_analysis", {}).get("issues", [])
    contract_hitl_required = len(contract_issues) > 0

    if agent_failed:
        state["status"] = "FAILED"
    elif missing_repos or ambiguous or agent_hitl_required or contract_hitl_required:
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


def hitl_interrupt_node(state: OrchestrationState) -> OrchestrationState:
    """Pause for human decision when HITL is required."""
    payload = {
        "goal": state["goal"],
        "repos": state["repos"],
        "proposal": state["proposal"],
        "contract_analysis": state.get("contract_analysis", {}),
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

    contract_analysis = state.get("contract_analysis", {})
    contract_issues = contract_analysis.get("issues", [])
    contract_summary = contract_analysis.get("summary", {})
    summary_lines.extend(
        [
            "## Contract Alignment",
            "",
            f"- Artifacts discovered: {contract_summary.get('artifact_count', 0)}",
            f"- Contract issues: {contract_summary.get('issue_count', 0)}",
        ]
    )
    if contract_issues:
        summary_lines.append("- Issues requiring review:")
        for issue in contract_issues:
            summary_lines.append(f"  - {issue}")
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
        "contract_analysis": state.get("contract_analysis", {}),
    }
    (artifacts_dir / "run.json").write_text(json.dumps(run_payload, indent=2), encoding="utf-8")

    (artifacts_dir / "contract-map.json").write_text(
        json.dumps(contract_analysis, indent=2),
        encoding="utf-8",
    )

    contract_lines = [
        "# Contract Checks",
        "",
        f"Goal: {state['goal']}",
        f"Issues: {contract_summary.get('issue_count', 0)}",
        f"Artifacts: {contract_summary.get('artifact_count', 0)}",
        "",
    ]
    if contract_issues:
        contract_lines.extend(["## Issues", ""])
        for issue in contract_issues:
            contract_lines.append(f"- {issue}")
        contract_lines.append("")

    contract_lines.extend(["## Per Repository", ""])
    for repo_summary in contract_analysis.get("repos", []):
        contract_lines.append(f"### {repo_summary.get('repo_path', 'unknown')}")
        artifacts = repo_summary.get("artifacts", [])
        declared = repo_summary.get("declared_contract_ids", [])
        consumed = repo_summary.get("consumed_contract_ids", [])
        contract_lines.append(f"- Artifacts: {len(artifacts)}")
        contract_lines.append(f"- Declared contracts: {len(declared)}")
        contract_lines.append(f"- Consumed contracts: {len(consumed)}")
        if artifacts:
            contract_lines.append("- Artifact paths:")
            for artifact in artifacts:
                contract_lines.append(f"  - {artifact.get('path')}")
        contract_lines.append("")

    (artifacts_dir / "contract-checks.md").write_text("\n".join(contract_lines), encoding="utf-8")

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

            # 2. Write agent-prompt.txt - provider-neutral handoff prompt
            copilot_prompt = plan.get("raw", {}).get("copilot_prompt", "")
            if copilot_prompt:
                prompt_content = str(copilot_prompt)
            else:
                # Generate a basic prompt if not available
                prompt_content = f"""# Task for {plan["repo_path"]}

Goal: {state["goal"]}

{plan["summary"]}

Proposed Changes:
"""
                for change in plan["proposed_changes"]:
                    prompt_content += f"- {change}\n"

            (repo_plan_dir / "agent-prompt.txt").write_text(prompt_content, encoding="utf-8")

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


def build_coordinate_graph_conditional(checkpointer: Any | None = None) -> Any:
    """Build graph with conditional edges and bounded retry loop."""
    graph = StateGraph(OrchestrationState)
    graph.add_node("collect_constraints_node", collect_constraints_node)
    graph.add_node("propose_split_node", propose_split_node)
    graph.add_node("agent_plan_node", agent_plan_node)
    graph.add_node("contract_alignment_node", contract_alignment_node)
    graph.add_node("decide_node", decide_node)
    graph.add_node("write_artifacts_node", write_artifacts_node)

    graph.set_entry_point("collect_constraints_node")
    graph.add_edge("collect_constraints_node", "propose_split_node")
    graph.add_edge("propose_split_node", "agent_plan_node")
    graph.add_edge("agent_plan_node", "contract_alignment_node")
    graph.add_edge("contract_alignment_node", "decide_node")
    graph.add_conditional_edges("decide_node", route_after_decide)
    graph.add_edge("write_artifacts_node", END)
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def build_coordinate_graph_interrupt(checkpointer: Any | None = None) -> Any:
    """Build graph that interrupts for human input when HITL is required."""
    graph = StateGraph(OrchestrationState)
    graph.add_node("collect_constraints_node", collect_constraints_node)
    graph.add_node("propose_split_node", propose_split_node)
    graph.add_node("agent_plan_node", agent_plan_node)
    graph.add_node("contract_alignment_node", contract_alignment_node)
    graph.add_node("decide_node", decide_node)
    graph.add_node("hitl_interrupt_node", hitl_interrupt_node)
    graph.add_node("write_artifacts_node", write_artifacts_node)

    graph.set_entry_point("collect_constraints_node")
    graph.add_edge("collect_constraints_node", "propose_split_node")
    graph.add_edge("propose_split_node", "agent_plan_node")
    graph.add_edge("agent_plan_node", "contract_alignment_node")
    graph.add_edge("contract_alignment_node", "decide_node")
    graph.add_conditional_edges("decide_node", route_after_decide_interrupt)
    graph.add_edge("hitl_interrupt_node", "write_artifacts_node")
    graph.add_edge("write_artifacts_node", END)
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
