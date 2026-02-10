"""Tests for OpenAI client wrapper."""

import pytest

from converge.llm.openai_client import DEFAULT_MODEL, OpenAIClient


def test_openai_client_defaults_to_gpt5_family_model() -> None:
    assert DEFAULT_MODEL.startswith("gpt-5")
    assert OpenAIClient().model.startswith("gpt-5")


def test_openai_client_fallback_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = OpenAIClient(model="gpt-5-mini")

    result = client.propose_responsibility_split(
        goal="Add discount support",
        repo_summaries=[{"path": "api", "repo_type": "python", "signals": ["pyproject.toml"]}],
    )

    assert "proposal" in result
    assert "questions_for_hitl" in result
    assert "Enable OPENAI_API_KEY to use LLM proposals" in result["questions_for_hitl"]
