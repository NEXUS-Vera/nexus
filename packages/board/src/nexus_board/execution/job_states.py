"""ExecutionJob status transitions and ExecutionRun mapping."""

from __future__ import annotations

from nexus_board.errors import BoardError

JOB_STATUSES = frozenset(
    {
        "queued",
        "starting",
        "running",
        "cancelling",
        "succeeded",
        "failed",
        "timed-out",
        "cancelled",
    }
)

JOB_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "timed-out", "cancelled"})

# Allowed directed transitions for ExecutionJob.
_ALLOWED: dict[str, frozenset[str]] = {
    "queued": frozenset({"starting", "cancelled"}),
    "starting": frozenset({"running", "failed", "timed-out", "cancelled", "cancelling"}),
    "running": frozenset({"succeeded", "failed", "timed-out", "cancelling"}),
    "cancelling": frozenset({"cancelled", "failed", "timed-out"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "timed-out": frozenset(),
    "cancelled": frozenset(),
}

# Job status → ExecutionRun status. ``stale`` is never a job concern.
_JOB_TO_RUN: dict[str, str] = {
    "queued": "queued",
    "starting": "starting",
    "running": "running",
    "cancelling": "running",
    "succeeded": "completed",
    "failed": "failed",
    "timed-out": "timed-out",
    "cancelled": "cancelled",
}


class IllegalJobTransitionError(BoardError):
    code = "ILLEGAL_JOB_TRANSITION"


def assert_job_transition(current: str, nxt: str) -> None:
    if current not in JOB_STATUSES:
        raise IllegalJobTransitionError(f"Unknown job status: {current}")
    if nxt not in JOB_STATUSES:
        raise IllegalJobTransitionError(f"Unknown job status: {nxt}")
    if nxt not in _ALLOWED[current]:
        raise IllegalJobTransitionError(f"Illegal job transition: {current} → {nxt}")


def job_status_to_run_status(job_status: str, *, warnings: bool = False) -> str:
    if job_status not in _JOB_TO_RUN:
        raise IllegalJobTransitionError(f"Unknown job status: {job_status}")
    if job_status == "succeeded" and warnings:
        return "completed-with-warnings"
    return _JOB_TO_RUN[job_status]
