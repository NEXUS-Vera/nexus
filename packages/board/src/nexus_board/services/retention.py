"""Reference-aware retention / GC for Phase 14 runtime storage growth.

Protects engineering history and live runtime references. Reclaims only
orphan blobs, unreferenced filesystem snapshots, and terminal job log chunks
under policy. Never emits Project Ledger events for GC deletions.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from nexus_persistence.file_store.protocol import FileStore


@dataclass(frozen=True)
class RetentionPolicy:
    """Configurable retention knobs. Conservative development defaults."""

    # None => reclaim orphans immediately when unreferenced.
    orphan_blob_max_age_seconds: int | None = None
    reclaimable_snapshot_max_age_seconds: int = 7 * 24 * 3600
    terminal_log_max_age_seconds: int = 7 * 24 * 3600
    max_reclaim_blobs: int | None = None
    max_reclaim_snapshots: int | None = None
    max_reclaim_log_jobs: int | None = None

    @classmethod
    def from_environ(cls) -> RetentionPolicy:
        def _int(name: str, default: int | None) -> int | None:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            return int(raw)

        return cls(
            orphan_blob_max_age_seconds=_int("NEXUS_RETENTION_ORPHAN_BLOB_MAX_AGE_SECONDS", None),
            reclaimable_snapshot_max_age_seconds=int(
                os.environ.get(
                    "NEXUS_RETENTION_SNAPSHOT_MAX_AGE_SECONDS",
                    str(7 * 24 * 3600),
                )
            ),
            terminal_log_max_age_seconds=int(
                os.environ.get(
                    "NEXUS_RETENTION_LOG_MAX_AGE_SECONDS",
                    str(7 * 24 * 3600),
                )
            ),
            max_reclaim_blobs=_int("NEXUS_RETENTION_MAX_RECLAIM_BLOBS", None),
            max_reclaim_snapshots=_int("NEXUS_RETENTION_MAX_RECLAIM_SNAPSHOTS", None),
            max_reclaim_log_jobs=_int("NEXUS_RETENTION_MAX_RECLAIM_LOG_JOBS", None),
        )


@dataclass
class GcCandidate:
    kind: str  # blob | filesystem-snapshot | execution-log-chunks
    id: str
    reason: str
    bytes: int | None = None
    protected: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GcPlan:
    candidates: list[GcCandidate]
    protected_summary: dict[str, int]
    dry_run: bool = True

    def reclaimable(self) -> list[GcCandidate]:
        return [c for c in self.candidates if not c.protected]


class _RetentionKernelStore(Protocol):
    def list_referenced_content_hashes(self) -> set[str]: ...

    def list_all_snapshots(self) -> list[dict[str, Any]]: ...

    def list_all_workspaces(self) -> list[dict[str, Any]]: ...

    def list_all_proposals(self) -> list[dict[str, Any]]: ...

    def list_all_execution_runs(self) -> list[dict[str, Any]]: ...

    def list_all_execution_jobs(self) -> list[dict[str, Any]]: ...

    def list_all_produced_outputs(self) -> list[dict[str, Any]]: ...

    def reclaim_snapshot(self, snapshot_id: str) -> None: ...

    def delete_execution_log_chunks(self, execution_job_id: str) -> int: ...


TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "timed-out", "cancelled"})


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _older_than(ts: datetime | None, max_age_seconds: int, *, now: datetime) -> bool:
    if ts is None:
        return True
    return ts <= now - timedelta(seconds=max_age_seconds)


class RetentionService:
    """Plan and apply reference-aware GC. Dry-run by default."""

    def __init__(
        self,
        kernel_store: _RetentionKernelStore,
        file_store: FileStore,
        *,
        policy: RetentionPolicy | None = None,
    ) -> None:
        self._kernel = kernel_store
        self._files = file_store
        self._policy = policy or RetentionPolicy.from_environ()

    @property
    def policy(self) -> RetentionPolicy:
        return self._policy

    def protected_snapshot_ids(self) -> set[str]:
        protected: set[str] = set()
        for workspace in self._kernel.list_all_workspaces():
            current = workspace.get("currentSnapshotId")
            if isinstance(current, str):
                protected.add(current)
        for proposal in self._kernel.list_all_proposals():
            snap = proposal.get("snapshotId")
            if isinstance(snap, str):
                protected.add(snap)
        for run in self._kernel.list_all_execution_runs():
            snap = run.get("inputSnapshotId")
            if isinstance(snap, str):
                protected.add(snap)
            identity = run.get("runtimeIdentity") or {}
            rid = identity.get("workspaceSnapshotId")
            if isinstance(rid, str):
                protected.add(rid)
        for job in self._kernel.list_all_execution_jobs():
            snap = job.get("workspaceSnapshotId")
            if isinstance(snap, str):
                protected.add(snap)
        # Semantic (non-filesystem) snapshots are never reclaimable by this GC.
        for snapshot in self._kernel.list_all_snapshots():
            content = snapshot.get("content") or {}
            if content.get("kind") != "filesystem":
                protected.add(snapshot["snapshotId"])
        return protected

    def plan(self, *, now: datetime | None = None) -> GcPlan:
        clock = now or datetime.now(UTC)
        protected_snaps = self.protected_snapshot_ids()
        candidates: list[GcCandidate] = []

        # --- orphan blobs ---
        referenced = self._kernel.list_referenced_content_hashes()
        listing = getattr(self._files, "list_content_hashes", None)
        stored: set[str] = (
            set(cast(Callable[[], list[str]], listing)()) if callable(listing) else set()
        )
        orphans = sorted(stored - referenced)
        if self._policy.max_reclaim_blobs is not None:
            orphans = orphans[: self._policy.max_reclaim_blobs]
        for content_hash in orphans:
            size = None
            getter = getattr(self._files, "size", None)
            if callable(getter):
                try:
                    size = int(cast(Callable[[str], int], getter)(content_hash))
                except Exception:  # noqa: BLE001
                    size = None
            candidates.append(
                GcCandidate(
                    kind="blob",
                    id=content_hash,
                    reason="orphan-unreferenced",
                    bytes=size,
                    protected=False,
                )
            )

        # --- filesystem snapshots ---
        snap_count = 0
        for snapshot in self._kernel.list_all_snapshots():
            snap_id = snapshot["snapshotId"]
            content = snapshot.get("content") or {}
            if content.get("kind") != "filesystem":
                candidates.append(
                    GcCandidate(
                        kind="filesystem-snapshot",
                        id=snap_id,
                        reason="semantic-or-non-filesystem",
                        protected=True,
                    )
                )
                continue
            if snap_id in protected_snaps:
                candidates.append(
                    GcCandidate(
                        kind="filesystem-snapshot",
                        id=snap_id,
                        reason="referenced",
                        protected=True,
                    )
                )
                continue
            created = _parse_ts(snapshot.get("createdAt"))
            if not _older_than(
                created,
                self._policy.reclaimable_snapshot_max_age_seconds,
                now=clock,
            ):
                candidates.append(
                    GcCandidate(
                        kind="filesystem-snapshot",
                        id=snap_id,
                        reason="within-retention-window",
                        protected=True,
                        details={"createdAt": snapshot.get("createdAt")},
                    )
                )
                continue
            if (
                self._policy.max_reclaim_snapshots is not None
                and snap_count >= self._policy.max_reclaim_snapshots
            ):
                continue
            snap_count += 1
            candidates.append(
                GcCandidate(
                    kind="filesystem-snapshot",
                    id=snap_id,
                    reason="unreferenced-filesystem-past-retention",
                    protected=False,
                    details={"createdAt": snapshot.get("createdAt")},
                )
            )

        # --- terminal job logs ---
        log_count = 0
        for job in self._kernel.list_all_execution_jobs():
            if job.get("status") not in TERMINAL_JOB_STATUSES:
                continue
            completed = _parse_ts(job.get("completedAt") or job.get("createdAt"))
            if not _older_than(
                completed,
                self._policy.terminal_log_max_age_seconds,
                now=clock,
            ):
                continue
            if (
                self._policy.max_reclaim_log_jobs is not None
                and log_count >= self._policy.max_reclaim_log_jobs
            ):
                break
            log_count += 1
            candidates.append(
                GcCandidate(
                    kind="execution-log-chunks",
                    id=job["executionJobId"],
                    reason="terminal-job-logs-past-retention",
                    protected=False,
                    details={"status": job.get("status"), "completedAt": job.get("completedAt")},
                )
            )

        return GcPlan(
            candidates=candidates,
            protected_summary={
                "protectedSnapshots": len(protected_snaps),
                "referencedHashes": len(referenced),
                "storedHashes": len(stored),
            },
            dry_run=True,
        )

    def apply(self, plan: GcPlan | None = None, *, dry_run: bool = False) -> dict[str, Any]:
        resolved = plan or self.plan()
        if dry_run:
            return {
                "dryRun": True,
                "deleted": [],
                "failed": [],
                "plan": _plan_as_dict(resolved),
            }
        deleted: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        # Reclaim snapshots before blobs so snapshot manifests stop protecting hashes.
        for candidate in resolved.reclaimable():
            try:
                if candidate.kind == "filesystem-snapshot":
                    self._kernel.reclaim_snapshot(candidate.id)
                elif candidate.kind == "blob":
                    self._files.delete(candidate.id)
                elif candidate.kind == "execution-log-chunks":
                    removed = self._kernel.delete_execution_log_chunks(candidate.id)
                    deleted.append(
                        {
                            "kind": candidate.kind,
                            "id": candidate.id,
                            "reason": candidate.reason,
                            "chunksRemoved": removed,
                        }
                    )
                    continue
                else:
                    continue
                deleted.append(
                    {
                        "kind": candidate.kind,
                        "id": candidate.id,
                        "reason": candidate.reason,
                        "bytes": candidate.bytes,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failed.append(
                    {
                        "kind": candidate.kind,
                        "id": candidate.id,
                        "error": str(exc)[:300],
                    }
                )
        # Second pass: blobs that became orphaned after snapshot reclaim.
        if any(c.kind == "filesystem-snapshot" for c in resolved.reclaimable()):
            follow = self.plan()
            for candidate in follow.reclaimable():
                if candidate.kind != "blob":
                    continue
                if any(d.get("id") == candidate.id for d in deleted):
                    continue
                try:
                    self._files.delete(candidate.id)
                    deleted.append(
                        {
                            "kind": candidate.kind,
                            "id": candidate.id,
                            "reason": "orphan-after-snapshot-reclaim",
                            "bytes": candidate.bytes,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    failed.append(
                        {
                            "kind": candidate.kind,
                            "id": candidate.id,
                            "error": str(exc)[:300],
                        }
                    )
        return {
            "dryRun": False,
            "deleted": deleted,
            "failed": failed,
            "plan": _plan_as_dict(resolved),
        }


def _plan_as_dict(plan: GcPlan) -> dict[str, Any]:
    return {
        "protectedSummary": plan.protected_summary,
        "candidates": [
            {
                "kind": c.kind,
                "id": c.id,
                "reason": c.reason,
                "bytes": c.bytes,
                "protected": c.protected,
                "details": c.details,
            }
            for c in plan.candidates
        ],
    }
