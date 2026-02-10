"""Tests for OpenAI client wrapper."""

import pytest

from converge.llm.openai_client import OpenAIClient


def test_openai_client_fallback_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = OpenAIClient(model="gpt-4o-mini")

    result = client.propose_responsibility_split(
        goal="Add discount support",
        repo_summaries=[{"path": "api", "repo_type": "python", "signals": ["pyproject.toml"]}],
    )

    assert "proposal" in result
    assert "questions_for_hitl" in result
    assert "Enable OPENAI_API_KEY to use LLM proposals" in result["questions_for_hitl"]
