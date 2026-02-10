"""FastAPI application for webhook-based task ingestion."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from converge.core.config import load_queue_settings, load_server_settings
from converge.integrations.jira import jira_payload_to_task
from converge.queue.base import TaskQueue
from converge.queue.factory import create_queue
from converge.queue.schemas import TaskRecord, TaskRequest, TaskStatus
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

    app = FastAPI(title="Converge API Server", version="0.1.0")
    app.state.queue = queue

    # Add CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        """Health check endpoint."""
        return {"ok": True}

    @app.get("/api/tasks")
    def list_tasks(status: str | None = None, limit: int = 100, offset: int = 0) -> list[TaskRecord]:
        """List tasks with optional status filter and pagination."""
        try:
            status_filter = TaskStatus(status) if status else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
        
        if not hasattr(queue, 'list_tasks'):
            raise HTTPException(status_code=501, detail="list_tasks not implemented")
        return queue.list_tasks(status_filter=status_filter, limit=limit, offset=offset)

    @app.get("/api/tasks/{task_id}", response_model=TaskRecord)
    def get_task(task_id: str) -> TaskRecord:
        """Get task details by task id."""
        try:
            return queue.get(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/tasks", response_model=TaskRecord)
    def create_task(task_request: TaskRequest) -> TaskRecord:
        """Enqueue a new task."""
        return queue.enqueue(task_request)

    @app.post("/api/tasks/{task_id}/resolve")
    def resolve_task(task_id: str, resolution: dict[str, Any]) -> dict[str, str]:
        """Resolve a HITL task by setting resolution and changing status to PENDING."""
        import json
        try:
            if not hasattr(queue, 'resolve_hitl'):
                raise HTTPException(status_code=501, detail="resolve_hitl not implemented")
            queue.resolve_hitl(task_id, json.dumps(resolution))
            return {"status": "ok", "message": f"Task {task_id} resolved and requeued"}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict[str, str]:
        """Cancel a task."""
        try:
            if not hasattr(queue, 'cancel'):
                raise HTTPException(status_code=501, detail="cancel not implemented")
            queue.cancel(task_id)
            return {"status": "ok", "message": f"Task {task_id} cancelled"}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/runs/{run_id}/files")
    def list_run_files(run_id: str) -> dict[str, Any]:
        """List files in the artifacts directory for a specific run."""
        output_dir = os.getenv("CONVERGE_OUTPUT_DIR", ".converge")
        run_path = Path(output_dir) / run_id
        
        if not run_path.exists() or not run_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
        # Collect files
        files = []
        for item in run_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(run_path)
                files.append({
                    "path": str(rel_path),
                    "size": item.stat().st_size,
                })
        
        return {"run_id": run_id, "files": files}

    @app.get("/api/runs/{run_id}/files/{path:path}")
    def get_run_file(run_id: str, path: str) -> FileResponse:
        """Download or stream a specific artifact file."""
        output_dir = os.getenv("CONVERGE_OUTPUT_DIR", ".converge")
        run_path = Path(output_dir) / run_id
        file_path = run_path / path
        
        # Security: ensure the file is within the run directory
        try:
            file_path = file_path.resolve()
            run_path = run_path.resolve()
            if not str(file_path).startswith(str(run_path)):
                raise HTTPException(status_code=403, detail="Access denied")
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid path") from exc
        
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"File {path} not found")
        
        return FileResponse(file_path)

    @app.get("/tasks/{task_id}", response_model=TaskRecord)
    def get_task_legacy(task_id: str) -> TaskRecord:
        """Get task details by task id (legacy endpoint for webhooks)."""
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
