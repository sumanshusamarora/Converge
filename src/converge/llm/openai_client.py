"""OpenAI client wrapper for responsibility-split proposals."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5-mini"


class OpenAIClient:
    """Client wrapper for proposal generation."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("CONVERGE_OPENAI_MODEL") or DEFAULT_MODEL

    def propose_responsibility_split(
        self,
        goal: str,
        repo_summaries: list[dict[str, Any]],
        planning_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a structured split proposal using LangChain OpenAI or a local fallback."""
        api_key = os.getenv("OPENAI_API_KEY")
        effective_context = planning_context or {}
        if not api_key:
            logger.info("OPENAI_API_KEY not configured; using heuristic proposal")
            fallback = heuristic_proposal(
                goal, repo_summaries, planning_context=effective_context
            )
            fallback["questions_for_hitl"].append(
                "Enable OPENAI_API_KEY to use LLM proposals"
            )
            return fallback

        try:
            from langchain.chat_models import init_chat_model

            model = init_chat_model(self.model, model_provider="openai")
            prompt = (
                "Return JSON only with keys: proposal, rationale, risks, questions_for_hitl."
                " Use project context defaults and avoid non-blocking HITL questions."
                f"\nInput: {json.dumps({'goal': goal, 'repo_summaries': repo_summaries, 'planning_context': effective_context})}"
            )
            response = model.invoke(prompt)
            content = _extract_content(response)
            parsed = json.loads(content)
            proposal_obj = parsed.get("proposal", {})
            if not isinstance(proposal_obj, dict):
                proposal_obj = {}

            risks_obj = parsed.get("risks", [])
            if not isinstance(risks_obj, list):
                risks_obj = [str(risks_obj)]

            questions_obj = parsed.get("questions_for_hitl", [])
            if not isinstance(questions_obj, list):
                questions_obj = [str(questions_obj)]

            return {
                "proposal": proposal_obj,
                "rationale": str(parsed.get("rationale", "")),
                "risks": [str(risk) for risk in risks_obj],
                "questions_for_hitl": [str(question) for question in questions_obj],
            }
        except Exception:
            logger.warning(
                "OpenAI proposal generation failed; falling back to heuristic"
            )
            return heuristic_proposal(
                goal, repo_summaries, planning_context=effective_context
            )


def _extract_content(response: Any) -> str:
    """Extract textual content from a LangChain chat response."""
    content = getattr(response, "content", "{}")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts) or "{}"
    return str(content)


def heuristic_proposal(
    goal: str,
    repo_summaries: list[dict[str, Any]],
    planning_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a deterministic split proposal without external network calls."""
    _ = planning_context or {}
    assignments: dict[str, list[str]] = {}
    for repo_summary in repo_summaries:
        repo_path = str(repo_summary.get("path", "unknown"))
        repo_type = str(repo_summary.get("repo_type", "unknown"))
        repo_name = repo_path.lower()

        if repo_type == "python" or any(
            hint in repo_name for hint in ["api", "service", "backend"]
        ):
            assignments[repo_path] = [
                f"Implement server-side logic for {goal}",
                "Own validation and persistence changes",
            ]
        elif repo_type == "node" or any(
            hint in repo_name for hint in ["web", "ui", "frontend"]
        ):
            assignments[repo_path] = [
                f"Implement user-facing updates for {goal}",
                "Own client-side state and UX behavior",
            ]
        else:
            assignments[repo_path] = [
                f"Implement {goal} in its owned domain",
                "Coordinate contract changes with peer repositories",
            ]

    return {
        "proposal": {"assignments": assignments},
        "rationale": "Heuristic split derived from repository type signals.",
        "risks": ["Cross-repository contracts may require coordinated rollout"],
        "questions_for_hitl": [],
    }
