"""Content-addressed blob store protocol for workspace files."""

from __future__ import annotations

from typing import Protocol


class FileStore(Protocol):
    """Replaceable content-addressed blob store.

    Implementations must never interpret caller-supplied workspace paths as host
    filesystem paths. Keys are content hashes only.
    """

    def put(self, data: bytes) -> str:
        """Store ``data`` immutably and return ``sha256:<hex>``."""
        ...

    def get(self, content_hash: str) -> bytes:
        """Return bytes for ``content_hash`` or raise ``FileStoreNotFoundError``."""
        ...

    def exists(self, content_hash: str) -> bool:
        """Return True when the blob is present."""
        ...

    def delete(self, content_hash: str) -> None:
        """Delete a blob if present. No-op when missing.

        Callers must ensure the blob is unreferenced (GC). Mutable index updates
        must not delete blobs that snapshots still reference.
        """
        ...
