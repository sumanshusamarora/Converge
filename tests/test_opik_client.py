"""Tests for Opik client configuration."""

import importlib

import pytest

from converge.observability import opik_client


def test_configure_opik_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")
    monkeypatch.setattr(opik_client, "_CONFIGURED", False)
    monkeypatch.setattr(opik_client, "_OPIK_ENABLED", False)

    calls: list[str] = []

    def fake_import_module(name: str) -> object:
        calls.append(name)
        raise AssertionError("opik import should not happen when tracing is disabled")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    opik_client.configure_opik()

    assert calls == []
    assert opik_client.is_tracing_enabled() is False
