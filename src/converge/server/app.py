"""FastAPI application for webhook-based task ingestion."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from converge.core.config import load_queue_settings, load_server_settings
from converge.integrations.jira import jira_payload_to_task
from converge.queue.base import TaskQueue
from converge.queue.factory import create_queue
from converge.queue.schemas import ProjectRecord, TaskRecord, TaskRequest, TaskStatus
from converge.server.schemas import (
    FollowupTaskRequest,
    JiraWebhookPayload,
    PaginatedTasksResponse,
    ProjectCreatePayload,
    ProjectListResponse,
    ProjectUpdatePayload,
    TaskEventPayload,
    WebhookIngestResponse,
    WebhookTaskIngestRequest,
)
from converge.server.security import verify_signature

logger = logging.getLogger(__name__)

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_RUN_EVENT_MAP: dict[str, tuple[str, str, str]] = {
    "collect_constraints_node": ("PLANNING_STARTED", "Planning started", "info"),
    "propose_split_node": ("PROPOSAL_GENERATED", "Proposal generated", "info"),
    "agent_plan_node": ("ROUND_STARTED", "Repository plans generated", "info"),
    "contract_alignment_node": ("ROUND_STARTED", "Contract alignment analyzed", "info"),
    "decide_node": ("ROUND_STARTED", "Round decision made", "info"),
    "route_after_decide": ("ROUND_STARTED", "Round route selected", "info"),
    "route_after_decide_interrupt": (
        "ROUND_STARTED",
        "Interrupt route selected",
        "info",
    ),
    "hitl_interrupt_node": ("HITL_REQUIRED", "Human input required", "warning"),
    "hitl_decision_received": ("HITL_RESOLVED", "Human decision recorded", "success"),
    "write_artifacts_node": ("ARTIFACTS_WRITTEN", "Artifacts written", "success"),
}


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return _to_utc(dt).isoformat().replace("+00:00", "Z")


def _is_subpath(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _output_root() -> Path:
    return Path(os.getenv("CONVERGE_OUTPUT_DIR", ".converge")).resolve()


def _resolve_run_dir(run_id: str) -> Path:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run id")

    output_root = _output_root()
    candidates = [
        (output_root / run_id).resolve(),
        (output_root / "runs" / run_id).resolve(),
    ]
    for candidate in candidates:
        if (
            _is_subpath(candidate, output_root)
            and candidate.exists()
            and candidate.is_dir()
        ):
            return candidate
    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


def _resolve_task_artifacts_dir(task: TaskRecord) -> Path | None:
    if not task.artifacts_dir:
        return None

    output_root = _output_root()
    raw = Path(task.artifacts_dir)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw.resolve())
    else:
        candidates.append((Path.cwd() / raw).resolve())
        candidates.append((output_root / raw).resolve())

    if len(raw.parts) == 1 and _RUN_ID_PATTERN.fullmatch(raw.parts[0]):
        try:
            return _resolve_run_dir(raw.parts[0])
        except HTTPException:
            pass

    for candidate in candidates:
        if (
            _is_subpath(candidate, output_root)
            and candidate.exists()
            and candidate.is_dir()
        ):
            return candidate
    return None


def _parse_run_payload(task: TaskRecord) -> dict[str, Any] | None:
    run_dir = _resolve_task_artifacts_dir(task)
    if run_dir is None:
        return None

    run_json_path = run_dir / "run.json"
    if not run_json_path.exists() or not run_json_path.is_file():
        return None

    try:
        payload = json.loads(run_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unable to parse run.json for task_id=%s: %s", task.id, exc)
        return None

    if not isinstance(payload, dict):
        return None
    return cast(dict[str, Any], payload)


def _spread_timestamps(start: datetime, end: datetime, count: int) -> list[datetime]:
    if count <= 0:
        return []

    normalized_start = _to_utc(start)
    normalized_end = _to_utc(end)
    if normalized_end <= normalized_start:
        normalized_end = normalized_start + timedelta(seconds=max(count, 1))

    step = (normalized_end - normalized_start) / (count + 1)
    return [normalized_start + (step * (index + 1)) for index in range(count)]


def _build_task_events(queue: TaskQueue, task: TaskRecord) -> list[TaskEventPayload]:
    created_at = _to_utc(task.created_at)
    updated_at = _to_utc(task.updated_at)
    drafts: list[dict[str, Any]] = [
        {
            "type": "TASK_CREATED",
            "title": "Task created",
            "status": "info",
            "ts": created_at,
            "details": {"task_status": task.status.value},
        }
    ]

    active_or_terminal_statuses = {
        TaskStatus.CLAIMED,
        TaskStatus.RUNNING,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.HITL_REQUIRED,
        TaskStatus.CANCELLED,
    }
    if task.status in active_or_terminal_statuses:
        drafts.append(
            {
                "type": "TASK_CLAIMED",
                "title": "Task claimed by worker",
                "status": "info",
                "ts": created_at + timedelta(seconds=1),
                "details": {},
            }
        )

    execution_started_statuses = {
        TaskStatus.RUNNING,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.HITL_REQUIRED,
        TaskStatus.CANCELLED,
    }
    if task.status in execution_started_statuses:
        drafts.append(
            {
                "type": "EXECUTION_STARTED",
                "title": "Execution started",
                "status": "info",
                "ts": created_at + timedelta(seconds=2),
                "details": {},
            }
        )

    run_payload = _parse_run_payload(task)
    raw_events = run_payload.get("events", []) if isinstance(run_payload, dict) else []
    event_items = raw_events if isinstance(raw_events, list) else []
    synthetic_end = updated_at
    if event_items:
        minimum_end = created_at + timedelta(seconds=len(event_items) + 4)
        if synthetic_end < minimum_end:
            synthetic_end = minimum_end

    event_timestamps = _spread_timestamps(created_at, synthetic_end, len(event_items))
    final_event_ts = synthetic_end
    if event_timestamps:
        final_event_ts = event_timestamps[-1] + timedelta(seconds=1)
    for index, raw_event in enumerate(event_items):
        if not isinstance(raw_event, dict):
            continue
        node = str(raw_event.get("node", "unknown"))
        message = str(raw_event.get("message", ""))
        event_type, title, status = _RUN_EVENT_MAP.get(
            node,
            ("ROUND_STARTED", node.replace("_", " "), "info"),
        )
        drafts.append(
            {
                "type": event_type,
                "title": title,
                "status": status,
                "ts": (
                    event_timestamps[index]
                    if index < len(event_timestamps)
                    else updated_at
                ),
                "details": {"node": node, "message": message},
            }
        )

    if task.status == TaskStatus.HITL_REQUIRED or task.hitl_questions:
        drafts.append(
            {
                "type": "HITL_REQUIRED",
                "title": "Human input required",
                "status": "warning",
                "ts": final_event_ts,
                "details": {
                    "status_reason": task.status_reason,
                    "question_count": len(task.hitl_questions),
                },
            }
        )

    hitl_resolution: dict[str, Any] | None = None
    try:
        hitl_resolution = queue.get_hitl_resolution(task.id)
    except Exception:  # pragma: no cover - defensive for alternate queue backends
        logger.exception("Unable to fetch HITL resolution for task_id=%s", task.id)
    if hitl_resolution:
        drafts.append(
            {
                "type": "HITL_RESOLVED",
                "title": "Human input submitted",
                "status": "success",
                "ts": final_event_ts,
                "details": {"resolution_keys": sorted(hitl_resolution.keys())},
            }
        )

    terminal_statuses = {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.HITL_REQUIRED,
        TaskStatus.CANCELLED,
    }
    if task.status in terminal_statuses:
        drafts.append(
            {
                "type": "EXECUTION_FINISHED",
                "title": "Execution finished",
                "status": (
                    "success" if task.status == TaskStatus.SUCCEEDED else "warning"
                ),
                "ts": final_event_ts,
                "details": {"final_status": task.status.value},
            }
        )

    if task.artifacts_dir:
        drafts.append(
            {
                "type": "ARTIFACTS_WRITTEN",
                "title": "Artifacts written",
                "status": "success",
                "ts": final_event_ts,
                "details": {"artifacts_dir": task.artifacts_dir},
            }
        )

    if task.status == TaskStatus.SUCCEEDED:
        drafts.append(
            {
                "type": "TASK_SUCCEEDED",
                "title": "Task succeeded",
                "status": "success",
                "ts": final_event_ts,
                "details": {},
            }
        )
    if task.status == TaskStatus.FAILED:
        drafts.append(
            {
                "type": "TASK_FAILED",
                "title": "Task failed",
                "status": "error",
                "ts": final_event_ts,
                "details": {"last_error": task.last_error},
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in sorted(drafts, key=lambda item: cast(datetime, item["ts"])):
        event_key = (
            cast(str, event["type"]),
            cast(str, event["title"]),
            _iso_utc(cast(datetime, event["ts"])),
        )
        if event_key in seen:
            continue
        seen.add(event_key)
        deduped.append(event)

    return [
        TaskEventPayload(
            id=f"evt_{task.id[:8]}_{index}",
            ts=_iso_utc(cast(datetime, event["ts"])),
            type=cast(str, event["type"]),
            title=cast(str, event["title"]),
            status=cast(str, event["status"]),
            details=cast(dict[str, Any], event.get("details", {})),
        )
        for index, event in enumerate(deduped, start=1)
    ]


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
    existing = queue.find_by_source_idempotency(
        source=source, idempotency_key=idempotency_key
    )
    task = queue.enqueue_with_dedupe(
        request=request,
        source=source,
        idempotency_key=idempotency_key,
    )
    return task, existing is not None


def _merge_instructions(
    default_instruction: str | None, custom_instruction: str | None
) -> str | None:
    default_text = (default_instruction or "").strip()
    custom_text = (custom_instruction or "").strip()
    if default_text and custom_text:
        return f"{default_text}\n\n{custom_text}"
    if custom_text:
        return custom_text
    if default_text:
        return default_text
    return None


def _normalize_task_request_with_project_defaults(
    queue: TaskQueue, task_request: TaskRequest
) -> tuple[TaskRequest, str]:
    project = (
        queue.get_project(task_request.project_id)
        if task_request.project_id
        else queue.get_default_project()
    )
    repos = task_request.repos or project.default_repos
    if not repos:
        raise HTTPException(
            status_code=400,
            detail="Task repos are required (or configure project default_repos)",
        )

    if (
        task_request.execute_immediately
        and project.preferences.execution_flow == "plan_then_execute"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Project execution_flow is plan_then_execute. "
                "Create plan first, then execute as a separate step."
            ),
        )

    normalized = task_request.model_copy(
        update={
            "project_id": project.id,
            "repos": repos,
            "custom_instructions": _merge_instructions(
                project.default_instructions,
                task_request.custom_instructions,
            ),
        }
    )
    return normalized, project.id


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

    @app.get("/api/tasks", response_model=PaginatedTasksResponse)
    def list_tasks(
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        project_id: str | None = None,
    ) -> PaginatedTasksResponse:
        """List tasks with optional status filter and pagination."""
        try:
            status_filter = TaskStatus(status) if status else None
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status}"
            ) from exc
        if page < 1:
            raise HTTPException(status_code=400, detail="page must be >= 1")
        if page_size < 1 or page_size > 200:
            raise HTTPException(
                status_code=400, detail="page_size must be between 1 and 200"
            )

        if not hasattr(queue, "list_tasks"):
            raise HTTPException(status_code=501, detail="list_tasks not implemented")

        offset = (page - 1) * page_size
        result: list[TaskRecord] = queue.list_tasks(
            status_filter=status_filter,
            limit=page_size,
            offset=offset,
            project_id=project_id,
        )
        total = (
            queue.count_tasks(status_filter=status_filter, project_id=project_id)
            if hasattr(queue, "count_tasks")
            else 0
        )
        return PaginatedTasksResponse(
            items=result,
            total=total,
            page=page,
            page_size=page_size,
            offset=offset,
            has_next=offset + len(result) < total,
            has_prev=page > 1,
        )

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
        normalized, _ = _normalize_task_request_with_project_defaults(
            queue, task_request
        )
        return queue.enqueue(normalized)

    @app.post("/api/tasks/{task_id}/followup", response_model=TaskRecord)
    def create_followup_task(task_id: str, payload: FollowupTaskRequest) -> TaskRecord:
        """Create a follow-up task with custom instructions from an existing task."""
        try:
            parent = queue.get(task_id)
            project = queue.get_project(parent.project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if not project.preferences.allow_custom_instructions_after_plan:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Project does not allow post-plan custom instructions. "
                    "Update project preferences to enable this."
                ),
            )
        if (
            payload.execute_immediately
            and project.preferences.execution_flow == "plan_then_execute"
        ):
            raise HTTPException(
                status_code=400,
                detail="Project execution_flow requires manual execute step after planning.",
            )

        request = parent.request.model_copy(
            update={
                "project_id": parent.project_id,
                "custom_instructions": payload.instruction.strip(),
                "execute_immediately": payload.execute_immediately,
                "metadata": {
                    **parent.request.metadata,
                    "followup_from_task_id": parent.id,
                },
            }
        )
        normalized, _ = _normalize_task_request_with_project_defaults(queue, request)
        return queue.enqueue(normalized)

    @app.get("/api/projects", response_model=ProjectListResponse)
    def list_projects() -> ProjectListResponse:
        """List projects."""
        return ProjectListResponse(items=queue.list_projects())

    @app.post("/api/projects", response_model=ProjectRecord)
    def create_project(payload: ProjectCreatePayload) -> ProjectRecord:
        """Create a project."""
        try:
            return queue.create_project(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/default", response_model=ProjectRecord)
    def get_default_project() -> ProjectRecord:
        """Get the default project."""
        return queue.get_default_project()

    @app.get("/api/projects/{project_id}", response_model=ProjectRecord)
    def get_project(project_id: str) -> ProjectRecord:
        """Get a project by id."""
        try:
            return queue.get_project(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/projects/{project_id}", response_model=ProjectRecord)
    def update_project(project_id: str, payload: ProjectUpdatePayload) -> ProjectRecord:
        """Update project settings."""
        try:
            return queue.update_project(project_id, payload)
        except ValueError as exc:
            status_code = 404 if "not found" in str(exc).lower() else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/resolve")
    def resolve_task(task_id: str, resolution: dict[str, Any]) -> dict[str, str]:
        """Resolve a HITL task by setting resolution and changing status to PENDING."""
        try:
            if not hasattr(queue, "resolve_hitl"):
                raise HTTPException(
                    status_code=501, detail="resolve_hitl not implemented"
                )
            queue.resolve_hitl(task_id, resolution)
            return {"status": "ok", "message": f"Task {task_id} resolved and requeued"}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict[str, str]:
        """Cancel a task."""
        try:
            if not hasattr(queue, "cancel"):
                raise HTTPException(status_code=501, detail="cancel not implemented")
            queue.cancel(task_id)
            return {"status": "ok", "message": f"Task {task_id} cancelled"}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}/events", response_model=list[TaskEventPayload])
    def get_task_events(task_id: str) -> list[TaskEventPayload]:
        """Return stable timeline events for a task."""
        try:
            task = queue.get(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _build_task_events(queue, task)

    @app.get("/api/runs/{run_id}/files")
    def list_run_files(run_id: str) -> dict[str, Any]:
        """List files in the artifacts directory for a specific run."""
        run_path = _resolve_run_dir(run_id)

        # Collect files
        files = []
        for item in run_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(run_path)
                files.append(
                    {
                        "path": str(rel_path),
                        "size": item.stat().st_size,
                    }
                )

        return {"run_id": run_id, "files": files}

    @app.get("/api/runs/{run_id}/files/{path:path}")
    def get_run_file(run_id: str, path: str) -> FileResponse:
        """Download or stream a specific artifact file."""
        run_path = _resolve_run_dir(run_id)
        file_path = (run_path / path).resolve()

        # Security: ensure the file is within the run directory
        if not _is_subpath(file_path, run_path):
            raise HTTPException(status_code=403, detail="Access denied")

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
        idempotency_key_header: str | None = Header(
            default=None, alias="Idempotency-Key"
        ),
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
