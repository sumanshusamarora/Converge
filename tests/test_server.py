"""Tests for webhook ingestion FastAPI server."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from converge.queue.schemas import TaskResult, TaskStatus
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
    monkeypatch.setenv(
        "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'server_hmac.db'}"
    )
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
    monkeypatch.setenv(
        "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'server_limit.db'}"
    )
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
    assert (
        "Jira PROJ-123: Fix authentication" in task_response.json()["request"]["goal"]
    )


def test_task_events_endpoint_includes_hitl_states(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/tasks",
        json={"goal": "Needs manual decision", "repos": ["repo-a"]},
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["id"]

    queue = app.state.queue
    queue.complete(
        task_id,
        TaskResult(
            status=TaskStatus.HITL_REQUIRED,
            summary="Need human input",
            hitl_questions=["Choose owner for API contract update"],
            status_reason="Ownership is ambiguous",
        ),
    )
    queue.resolve_hitl(
        task_id,
        {
            "answers": {"owner": "backend-team"},
            "resolved_at": "2026-02-13T00:00:00Z",
        },
    )

    response = client.get(f"/api/tasks/{task_id}/events")
    assert response.status_code == 200
    events = response.json()

    timestamps = [event["ts"] for event in events]
    assert timestamps == sorted(timestamps)

    event_types = {event["type"] for event in events}
    assert "HITL_REQUIRED" in event_types
    assert "HITL_RESOLVED" in event_types


def test_list_tasks_returns_paginated_payload(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    for index in range(3):
        response = client.post(
            "/api/tasks",
            json={"goal": f"Task {index}", "repos": ["repo-a"]},
        )
        assert response.status_code == 200

    page_one = client.get("/api/tasks?page=1&page_size=2")
    assert page_one.status_code == 200
    payload_one = page_one.json()
    assert payload_one["page"] == 1
    assert payload_one["page_size"] == 2
    assert payload_one["offset"] == 0
    assert payload_one["total"] == 3
    assert payload_one["has_next"] is True
    assert payload_one["has_prev"] is False
    assert len(payload_one["items"]) == 2

    page_two = client.get("/api/tasks?page=2&page_size=2")
    assert page_two.status_code == 200
    payload_two = page_two.json()
    assert payload_two["page"] == 2
    assert payload_two["page_size"] == 2
    assert payload_two["offset"] == 2
    assert payload_two["total"] == 3
    assert payload_two["has_next"] is False
    assert payload_two["has_prev"] is True
    assert len(payload_two["items"]) == 1


def test_task_creation_assigns_default_project(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    default_project = client.get("/api/projects/default")
    assert default_project.status_code == 200
    default_project_id = default_project.json()["id"]

    response = client.post(
        "/api/tasks",
        json={"goal": "Project assignment check", "repos": ["repo-a"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == default_project_id
    assert payload["request"]["project_id"] == default_project_id


def test_followup_task_from_existing_task(server_env: None) -> None:
    app = create_app()
    client = TestClient(app)

    create_response = client.post(
        "/api/tasks",
        json={"goal": "Initial planning", "repos": ["repo-a"]},
    )
    assert create_response.status_code == 200
    task = create_response.json()

    followup_response = client.post(
        f"/api/tasks/{task['id']}/followup",
        json={
            "instruction": "Use existing API contracts; avoid new deps",
            "execute_immediately": False,
        },
    )
    assert followup_response.status_code == 200
    followup = followup_response.json()
    assert followup["id"] != task["id"]
    assert "existing API contracts" in (
        followup["request"]["custom_instructions"] or ""
    )
    assert followup["request"]["metadata"]["followup_from_task_id"] == task["id"]
