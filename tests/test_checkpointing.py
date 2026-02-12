"""Tests for LangGraph checkpoint wiring helpers."""

from __future__ import annotations

import pytest

from converge.orchestration import checkpointing


def test_create_db_checkpointer_defaults_to_local_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def fake_load(
        module_name: str,
        class_name: str,
        conn_string: str,
        install_hint: str,
    ) -> None:
        called["module_name"] = module_name
        called["class_name"] = class_name
        called["conn_string"] = conn_string
        called["install_hint"] = install_hint
        return None

    monkeypatch.setattr(checkpointing, "_load_checkpointer", fake_load)

    result = checkpointing.create_db_checkpointer(None)

    assert result is None
    assert called["module_name"] == "langgraph.checkpoint.sqlite"
    assert called["class_name"] == "SqliteSaver"
    assert called["conn_string"] == checkpointing.DEFAULT_CHECKPOINT_DB_URI


def test_create_db_checkpointer_normalizes_postgres_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def fake_load(
        module_name: str,
        class_name: str,
        conn_string: str,
        install_hint: str,
    ) -> None:
        called["module_name"] = module_name
        called["class_name"] = class_name
        called["conn_string"] = conn_string
        called["install_hint"] = install_hint
        return None

    monkeypatch.setattr(checkpointing, "_load_checkpointer", fake_load)

    result = checkpointing.create_db_checkpointer(
        "postgresql+psycopg://user:pass@localhost:5432/converge"
    )

    assert result is None
    assert called["module_name"] == "langgraph.checkpoint.postgres"
    assert called["class_name"] == "PostgresSaver"
    assert called["conn_string"] == "postgresql://user:pass@localhost:5432/converge"
