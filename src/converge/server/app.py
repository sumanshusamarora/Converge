"""FastAPI application for webhook-based task ingestion."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException, Request

from converge.core.config import load_queue_settings, load_server_settings
from converge.integrations.jira import jira_payload_to_task
from converge.queue.base import TaskQueue
from converge.queue.factory import create_queue
from converge.queue.schemas import TaskRecord, TaskRequest
from converge.server.schemas import (
    JiraWebhookPayload,
    WebhookIngestResponse,
    WebhookTaskIngestRequest,
)
from converge.server.security import verify_signature

logger = logging.getLogger(__name__)


def _to_ingest_response(task: TaskRecord, deduped: bool) -> WebhookIngestResponse:
    return WebhookIngestResponse(
        task_id=task.id,
        status=task.status.value,
        deduped=deduped,
        task_url=f"/tasks/{task.id}",
    )


def _maybe_verify_signature(
    request_body: bytes,
    signature_header: str | None,
) -> None:
    settings = load_server_settings()
    if settings.webhook_secret is None:
        return
    if signature_header is None or not verify_signature(
        settings.webhook_secret,
        request_body,
        signature_header,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _enforce_body_size_limit(request_body: bytes) -> None:
    max_body_bytes = load_server_settings().webhook_max_body_bytes
    if len(request_body) > max_body_bytes:
        raise HTTPException(status_code=413, detail="Webhook body too large")


def _enqueue_with_optional_dedupe(
    queue: TaskQueue,
    request: TaskRequest,
    source: str,
    idempotency_key: str | None,
) -> tuple[TaskRecord, bool]:
    existing = queue.find_by_source_idempotency(source=source, idempotency_key=idempotency_key)
    task = queue.enqueue_with_dedupe(
        request=request,
        source=source,
        idempotency_key=idempotency_key,
    )
    return task, existing is not None


def create_app() -> FastAPI:
    """Create and configure the webhook ingestion FastAPI app."""
    queue_settings = load_queue_settings()
    if queue_settings.backend != "db":
        raise ValueError("CONVERGE_QUEUE_BACKEND must be 'db' for webhook ingestion")
    queue = create_queue()

    app = FastAPI(title="Converge Webhook Server", version="0.1.0")
    app.state.queue = queue

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        """Health check endpoint."""
        return {"ok": True}

    @app.get("/tasks/{task_id}", response_model=TaskRecord)
    def get_task(task_id: str) -> TaskRecord:
        """Get task details by task id."""
        try:
            return queue.get(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/webhooks/task", response_model=WebhookIngestResponse)
    async def ingest_task_webhook(
        request: Request,
        x_converge_signature: str | None = Header(default=None),
        idempotency_key_header: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> WebhookIngestResponse:
        """Ingest a generic task webhook payload into the internal queue."""
        body = await request.body()
        _enforce_body_size_limit(body)
        _maybe_verify_signature(body, x_converge_signature)

        payload = WebhookTaskIngestRequest.model_validate_json(body)
        idempotency_key = payload.idempotency_key or idempotency_key_header
        source = payload.source
        task_request = TaskRequest(
            goal=payload.goal,
            repos=payload.repos,
            max_rounds=payload.max_rounds,
            agent_provider=payload.agent_provider,
            metadata=payload.metadata,
        )
        task, deduped = _enqueue_with_optional_dedupe(
            queue=queue,
            request=task_request,
            source=source,
            idempotency_key=idempotency_key,
        )
        return _to_ingest_response(task, deduped)

    @app.post("/webhooks/jira", response_model=WebhookIngestResponse)
    async def ingest_jira_webhook(
        request: Request,
        x_converge_signature: str | None = Header(default=None),
    ) -> WebhookIngestResponse:
        """Ingest a Jira webhook payload into the internal queue."""
        body = await request.body()
        _enforce_body_size_limit(body)
        _maybe_verify_signature(body, x_converge_signature)

        jira_payload = JiraWebhookPayload.model_validate_json(body)
        task_request, idempotency_key = jira_payload_to_task(jira_payload)
        task, deduped = _enqueue_with_optional_dedupe(
            queue=queue,
            request=task_request,
            source="jira",
            idempotency_key=idempotency_key,
        )
        return _to_ingest_response(task, deduped)

    return app
