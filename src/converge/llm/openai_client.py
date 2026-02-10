"""OpenAI client wrapper for responsibility-split proposals."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from converge.observability.opik_client import is_tracing_enabled

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIClient:
    """Client wrapper for proposal generation."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("CONVERGE_OPENAI_MODEL") or DEFAULT_MODEL

    def propose_responsibility_split(
        self, goal: str, repo_summaries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate a structured split proposal using OpenAI or a local heuristic fallback."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.info("OPENAI_API_KEY not configured; using heuristic proposal")
            fallback = heuristic_proposal(goal, repo_summaries)
            fallback["questions_for_hitl"].append("Enable OPENAI_API_KEY to use LLM proposals")
            return fallback

        try:
            from openai import OpenAI

            client: Any = OpenAI(api_key=api_key)
            if is_tracing_enabled():
                try:
                    from opik.integrations.openai import track_openai

                    client = track_openai(client)
                except Exception:
                    logger.debug("Opik OpenAI integration unavailable", exc_info=True)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only with keys: proposal, rationale, risks, "
                        "questions_for_hitl."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"goal": goal, "repo_summaries": repo_summaries}),
                },
            ]
            completion = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            parsed = json.loads(content)
            return {
                "proposal": parsed.get("proposal", {}),
                "rationale": str(parsed.get("rationale", "")),
                "risks": [str(risk) for risk in parsed.get("risks", [])],
                "questions_for_hitl": [
                    str(question) for question in parsed.get("questions_for_hitl", [])
                ],
            }
        except Exception:
            logger.warning("OpenAI proposal generation failed; falling back to heuristic")
            return heuristic_proposal(goal, repo_summaries)


def heuristic_proposal(goal: str, repo_summaries: list[dict[str, Any]]) -> dict[str, Any]:
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
        elif repo_type == "node" or any(hint in repo_name for hint in ["web", "ui", "frontend"]):
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
