"""Content-hash helpers for workspace blobs."""

from __future__ import annotations

import hashlib
import re

HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


def blob_digest(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"


def digest_hex(content_hash: str) -> str:
    if not HASH_RE.fullmatch(content_hash):
        raise ValueError("Invalid content hash")
    return content_hash.removeprefix("sha256:")


def opaque_content_reference(content_hash: str) -> str:
    """Return an opaque blob reference that is not a host path."""
    return f"cas:{digest_hex(content_hash)}"
