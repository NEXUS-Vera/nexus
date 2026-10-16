"""In-process FIFO scheduler for Nexus-owned ExecutionJobs."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from nexus_board.errors import BoardError


class ExecutionQueueFullError(BoardError):
    code = "EXECUTION_QUEUE_FULL"


class ExecutionCapacityError(BoardError):
    code = "EXECUTION_CAPACITY_EXCEEDED"


@dataclass(frozen=True)
class SchedulerConfig:
    max_running_global: int = 2
    max_running_per_project: int = 1
    max_queued: int = 32


class InProcessExecutionScheduler:
    """FIFO queue with global and per-project concurrency bounds.

    Dispatch skips a queued job when its project is already at
    ``max_running_per_project``, allowing another project's eligible job to
    run. This is lightweight project-aware fair FIFO, not full round-robin.

    Designed so a future DB-backed worker can replace this without changing
    the public ExecutionRun contract.
    """

    def __init__(
        self,
        config: SchedulerConfig | None = None,
        *,
        on_dispatch: Callable[[str], None] | None = None,
    ) -> None:
        self._config = config or SchedulerConfig()
        self._on_dispatch = on_dispatch
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._queue: deque[tuple[str, str]] = deque()  # (job_id, project_id)
        self._running: dict[str, str] = {}  # job_id -> project_id
        self._cancelled_queued: set[str] = set()
        self._closed = False
        self._worker: threading.Thread | None = None
        self._rejected_jobs = 0

    @property
    def config(self) -> SchedulerConfig:
        return self._config

    def start(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._closed = False
            self._worker = threading.Thread(
                target=self._loop,
                name="nexus-execution-scheduler",
                daemon=True,
            )
            self._worker.start()

    def stop(self, *, wait: bool = False) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify_all()
        if wait and self._worker is not None:
            self._worker.join(timeout=5)

    def enqueue(self, job_id: str, project_id: str) -> int:
        with self._cv:
            if len(self._queue) >= self._config.max_queued:
                self._rejected_jobs += 1
                raise ExecutionQueueFullError(
                    f"Execution queue is full (maxQueued={self._config.max_queued})"
                )
            self._queue.append((job_id, project_id))
            position = len(self._queue) - 1
            self._cv.notify()
            return position

    def mark_queued_cancelled(self, job_id: str) -> bool:
        """Remove a queued job if still waiting. Returns True when removed."""
        with self._cv:
            for idx, (queued_id, _project_id) in enumerate(self._queue):
                if queued_id == job_id:
                    del self._queue[idx]
                    self._cancelled_queued.add(job_id)
                    return True
            self._cancelled_queued.add(job_id)
            return False

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled_queued

    def clear_cancel_request(self, job_id: str) -> None:
        with self._lock:
            self._cancelled_queued.discard(job_id)

    def notify_job_finished(self, job_id: str) -> None:
        with self._cv:
            self._running.pop(job_id, None)
            self._cancelled_queued.discard(job_id)
            self._cv.notify()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "queued": [job_id for job_id, _ in self._queue],
                "running": dict(self._running),
                "maxRunningGlobal": self._config.max_running_global,
                "maxRunningPerProject": self._config.max_running_per_project,
                "maxQueued": self._config.max_queued,
                "rejectedJobs": self._rejected_jobs,
            }

    def health(self) -> dict[str, object]:
        snap = self.snapshot()
        return {
            "queuedJobs": len(snap["queued"]),  # type: ignore[arg-type]
            "runningJobs": len(snap["running"]),  # type: ignore[arg-type]
            "globalCapacity": self._config.max_running_global,
            "perProjectCapacity": self._config.max_running_per_project,
            "maxQueued": self._config.max_queued,
            "rejectedJobs": snap["rejectedJobs"],
            "queued": snap["queued"],
            "running": snap["running"],
        }

    def _project_running_count(self, project_id: str) -> int:
        return sum(1 for pid in self._running.values() if pid == project_id)

    def _loop(self) -> None:
        while True:
            job_id: str | None = None
            with self._cv:
                while not self._closed:
                    candidate = self._pick_next_locked()
                    if candidate is not None:
                        job_id, project_id = candidate
                        self._running[job_id] = project_id
                        break
                    self._cv.wait(timeout=0.1)
                if self._closed and job_id is None:
                    return
            if job_id is None:
                continue
            if self._on_dispatch is not None:
                try:
                    self._on_dispatch(job_id)
                finally:
                    self.notify_job_finished(job_id)

    def _pick_next_locked(self) -> tuple[str, str] | None:
        if len(self._running) >= self._config.max_running_global:
            return None
        for idx, (job_id, project_id) in enumerate(self._queue):
            if self._project_running_count(project_id) >= self._config.max_running_per_project:
                continue
            del self._queue[idx]
            return job_id, project_id
        return None
