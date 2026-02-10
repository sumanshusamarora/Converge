"""Tests for webhook ingestion FastAPI server."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from converge.server.app import create_app
from converge.server.security import compute_signature


@pytest.fixture
def server_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Configure environment for server tests."""
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("CONVERGE_QUEUE_BACKEND", "db")
    monkeypatch.setenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("CONVERGE_WEBHOOK_SECRET", "")
    monkeypatch.setenv("CONVERGE_WEBHOOK_MAX_BODY_BYTES", "262144")
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")


def test_webhook_task_ingest_enqueues(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/task",
        json={"goal": "Do thing", "repos": ["repo-a"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deduped"] is False
    assert payload["task_id"]

    task_response = client.get(f"/tasks/{payload['task_id']}")
    assert task_response.status_code == 200
    assert task_response.json()["status"] == "PENDING"


def test_webhook_idempotency(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    headers = {"Idempotency-Key": "same-key"}
    payload = {"goal": "Do thing", "repos": ["repo-a"], "source": "webhook"}

    first = client.post("/webhooks/task", json=payload, headers=headers)
    second = client.post("/webhooks/task", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["task_id"] == second.json()["task_id"]
    assert second.json()["deduped"] is True


def test_webhook_hmac_required_when_secret_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'server_hmac.db'}")
    monkeypatch.setenv("CONVERGE_QUEUE_BACKEND", "db")
    monkeypatch.setenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("CONVERGE_WEBHOOK_SECRET", "abc")
    monkeypatch.setenv("CONVERGE_WEBHOOK_MAX_BODY_BYTES", "262144")
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")

    app = create_app()
    client = TestClient(app)

    raw_body = json.dumps({"goal": "Do thing", "repos": ["repo-a"]}).encode("utf-8")
    missing_signature = client.post(
        "/webhooks/task",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )
    assert missing_signature.status_code == 401

    signature = compute_signature("abc", raw_body)
    valid_response = client.post(
        "/webhooks/task",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Converge-Signature": f"sha256={signature}",
        },
    )
    assert valid_response.status_code == 200


def test_webhook_body_size_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'server_limit.db'}")
    monkeypatch.setenv("CONVERGE_QUEUE_BACKEND", "db")
    monkeypatch.setenv("CONVERGE_WORKER_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("CONVERGE_WEBHOOK_SECRET", "")
    monkeypatch.setenv("CONVERGE_WEBHOOK_MAX_BODY_BYTES", "10")
    monkeypatch.setenv("OPIK_TRACK_DISABLE", "true")

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/task",
        json={"goal": "too big payload", "repos": ["repo-a"]},
    )
    assert response.status_code == 413


def test_jira_webhook_maps_goal(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/webhooks/jira",
        json={
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "key": "PROJ-123",
                "fields": {
                    "summary": "Fix authentication",
                    "description": "Update login flow",
                },
            },
        },
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    task_response = client.get(f"/tasks/{task_id}")
    assert task_response.status_code == 200
    assert "Jira PROJ-123: Fix authentication" in task_response.json()["request"]["goal"]
