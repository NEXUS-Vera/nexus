"""Stable ID generators matching contract patterns."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime


def new_id(prefix: str, *, nbytes: int = 16) -> str:
    """Return ``{prefix}_{hex}`` with at least 16 alphanumeric characters after the underscore."""
    return f"{prefix}_{secrets.token_hex(nbytes)}"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def content_digest(content: object) -> str:
    import hashlib
    import json

    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
