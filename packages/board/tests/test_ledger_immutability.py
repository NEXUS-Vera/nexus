"""Ledger immutability tests."""

from __future__ import annotations

import pytest
from helpers import actor, build_test_kernel
from nexus_board.errors import LedgerImmutableError
from nexus_persistence.errors import LedgerImmutableError as PersistenceLedgerImmutableError


def test_ledger_append_only() -> None:
    kernel, _, kernel_store, project_id = build_test_kernel()
    event = kernel.ledger.append(
        project_id=project_id,
        event_type="workspace.created",
        actor=actor(),
        subject_type="workspace",
        subject_id="ws_TESTWORKSPACE00001",
        payload={"workspaceId": "ws_TESTWORKSPACE00001"},
    )
    events, _ = kernel.ledger.list_events(project_id)
    assert any(e["eventId"] == event["eventId"] for e in events)

    with pytest.raises((LedgerImmutableError, PersistenceLedgerImmutableError)):
        kernel.ledger.update_event(event)
    with pytest.raises((LedgerImmutableError, PersistenceLedgerImmutableError)):
        kernel.ledger.delete_event(event["eventId"])
    with pytest.raises(PersistenceLedgerImmutableError):
        kernel_store.update_project_event(event)
    with pytest.raises(PersistenceLedgerImmutableError):
        kernel_store.delete_project_event(event["eventId"])
