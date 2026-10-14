"""Draft edit-lease helpers (single active editor)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from nexus_board.errors import DraftEditLeaseHeldError, DraftEditLeaseRequiredError
from nexus_board.ids import new_id

DEFAULT_LEASE_TTL_SECONDS = 15 * 60


def _parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _format_iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_lease_active(
    lease: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when ``lease`` exists and has not expired."""
    if not isinstance(lease, dict):
        return False
    expires_at = lease.get("expiresAt")
    if not isinstance(expires_at, str) or not expires_at:
        return False
    current = now if now is not None else datetime.now(UTC)
    try:
        return _parse_iso(expires_at) > current
    except ValueError:
        return False


def acquire_lease(
    draft: dict[str, Any],
    *,
    actor: dict[str, Any],
    now: datetime | None = None,
    ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> dict[str, Any]:
    """Grant or refresh an edit lease for ``actor``.

    Raises ``DraftEditLeaseHeldError`` when another actor holds an active lease.
    Returns the new ``editLease`` record (does not mutate ``draft``).
    """
    current = now if now is not None else datetime.now(UTC)
    existing = draft.get("editLease")
    if (
        isinstance(existing, dict)
        and is_lease_active(existing, now=current)
        and existing.get("ownerActorId") != actor.get("actorId")
    ):
        raise DraftEditLeaseHeldError(
            "Draft edit lease is held by another actor.",
        )
    if ttl_seconds < 1:
        ttl_seconds = DEFAULT_LEASE_TTL_SECONDS
    expires = current + timedelta(seconds=ttl_seconds)
    lease: dict[str, Any] = {
        "leaseId": new_id("lease"),
        "ownerActorId": actor["actorId"],
        "ownerActorType": actor["actorType"],
        "acquiredAt": _format_iso(current),
        "expiresAt": _format_iso(expires),
        "leaseToken": new_id("tok"),
        "baseDraftVersion": int(draft.get("draftVersion") or 1),
    }
    display_name = actor.get("displayName")
    if isinstance(display_name, str) and display_name:
        lease["ownerDisplayName"] = display_name
    return lease


def release_lease(
    draft: dict[str, Any],
    *,
    actor: dict[str, Any],
    lease_token: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clear the draft lease when the actor (or matching token) is authorized.

    Returns a new draft dict without ``editLease``. Raises when the lease is
    active and held by someone else without a matching token.
    """
    current = now if now is not None else datetime.now(UTC)
    existing = draft.get("editLease")
    if not isinstance(existing, dict) or not is_lease_active(existing, now=current):
        result = dict(draft)
        result.pop("editLease", None)
        return result

    token_ok = (
        isinstance(lease_token, str) and lease_token and lease_token == existing.get("leaseToken")
    )
    owner_ok = existing.get("ownerActorId") == actor.get("actorId")
    if not token_ok and not owner_ok:
        raise DraftEditLeaseHeldError(
            "Cannot release draft edit lease held by another actor.",
        )
    result = dict(draft)
    result.pop("editLease", None)
    return result


def assert_actor_holds_lease(
    draft: dict[str, Any],
    *,
    actor: dict[str, Any],
    now: datetime | None = None,
) -> None:
    """Require an active lease owned by ``actor``."""
    current = now if now is not None else datetime.now(UTC)
    lease = draft.get("editLease")
    if not is_lease_active(lease if isinstance(lease, dict) else None, now=current):
        raise DraftEditLeaseRequiredError(
            "An active draft edit lease is required before mutating the draft.",
        )
    assert isinstance(lease, dict)
    if lease.get("ownerActorId") != actor.get("actorId"):
        raise DraftEditLeaseHeldError(
            "Draft edit lease is held by another actor.",
        )


def refresh_lease_for_owner(
    draft: dict[str, Any],
    *,
    actor: dict[str, Any],
    now: datetime | None = None,
    ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> dict[str, Any] | None:
    """Optionally refresh an active lease for the owning actor; else None."""
    current = now if now is not None else datetime.now(UTC)
    lease = draft.get("editLease")
    if not isinstance(lease, dict) or not is_lease_active(lease, now=current):
        return None
    if lease.get("ownerActorId") != actor.get("actorId"):
        return None
    return acquire_lease(draft, actor=actor, now=current, ttl_seconds=ttl_seconds)


__all__ = [
    "DEFAULT_LEASE_TTL_SECONDS",
    "acquire_lease",
    "assert_actor_holds_lease",
    "is_lease_active",
    "refresh_lease_for_owner",
    "release_lease",
]
