"""Polling worker loop for processing queued Converge tasks."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from converge.orchestration.runner import run_coordinate
from converge.queue.base import TaskQueue
from converge.queue.schemas import TaskResult, TaskStatus

logger = logging.getLogger(__name__)
_MAX_ERROR_LENGTH = 500


class PollingWorker:
    """Worker that polls a task queue and executes task runs."""

    def __init__(self, queue: TaskQueue, poll_interval_seconds: float, batch_size: int) -> None:
        self._queue = queue
        self._poll_interval_seconds = poll_interval_seconds
        self._batch_size = batch_size

    def run_once(self) -> int:
        """Process at most one polling cycle and return processed task count."""
        tasks = self._queue.poll_and_claim(self._batch_size)
        for task in tasks:
            try:
                self._queue.mark_running(task.id)

                # Check if task has HITL resolution (resumed from HITL_REQUIRED)
                hitl_resolution = self._queue.get_hitl_resolution(task.id)

                outcome = run_coordinate(
                    goal=task.request.goal,
                    repos=task.request.repos,
                    max_rounds=task.request.max_rounds,
                    agent_provider=task.request.agent_provider,
                    base_output_dir=Path(".converge"),
                    hitl_resolution=hitl_resolution,
                    thread_id=task.id,
                )

                if outcome.status == "FAILED":
                    self._queue.fail(task.id, outcome.summary[:_MAX_ERROR_LENGTH], retryable=True)
                    continue

                result_status = (
                    TaskStatus.HITL_REQUIRED
                    if outcome.status == "HITL_REQUIRED"
                    else TaskStatus.SUCCEEDED
                )
                result = TaskResult(
                    status=result_status,
                    summary=outcome.summary,
                    artifacts_dir=outcome.artifacts_dir,
                    hitl_questions=outcome.hitl_questions,
                )
                self._queue.complete(task.id, result)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Task processing failed for task_id=%s", task.id)
                truncated_error = str(exc)[:_MAX_ERROR_LENGTH]
                self._queue.fail(task.id, truncated_error, retryable=True)
        return len(tasks)

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        """Run continuous polling until stop_event is set."""
        while True:
            if stop_event and stop_event.is_set():
                return
            self.run_once()
            time.sleep(self._poll_interval_seconds)
