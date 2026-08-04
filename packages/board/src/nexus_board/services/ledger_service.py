"""Append-only project event ledger."""

from __future__ import annotations

from typing import Any, Protocol

from nexus_board.errors import LedgerImmutableError
from nexus_board.ids import new_id, utc_now_iso


class _KernelStore(Protocol):
    def append_project_event(self, event: dict[str, Any]) -> None: ...

    def list_project_events(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    def update_project_event(self, event: dict[str, Any]) -> None: ...

    def delete_project_event(self, event_id: str) -> None: ...


class ProjectLedgerService:
    def __init__(self, store: _KernelStore) -> None:
        self._store = store

    def append(
        self,
        *,
        project_id: str,
        event_type: str,
        actor: dict[str, Any],
        subject_type: str,
        subject_id: str,
        payload: dict[str, Any] | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "eventId": new_id("evt"),
            "projectId": project_id,
            "eventType": event_type,
            "occurredAt": occurred_at or utc_now_iso(),
            "actor": actor,
            "subject": {"subjectType": subject_type, "subjectId": subject_id},
            "payload": payload or {},
        }
        if causation_id:
            event["causationId"] = causation_id
        if correlation_id:
            event["correlationId"] = correlation_id
        self._store.append_project_event(event)
        return event

    def list_events(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        return self._store.list_project_events(project_id, limit=limit, cursor=cursor)

    def update_event(self, event: dict[str, Any]) -> None:
        raise LedgerImmutableError("Project events are append-only.")

    def delete_event(self, event_id: str) -> None:
        raise LedgerImmutableError("Project events are append-only.")
