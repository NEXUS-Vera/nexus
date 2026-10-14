"""Workspace file blob store."""

from __future__ import annotations

from nexus_persistence.file_store.errors import (
    FileStoreError,
    FileStoreIntegrityError,
    FileStoreNotFoundError,
)
from nexus_persistence.file_store.hashing import blob_digest, opaque_content_reference
from nexus_persistence.file_store.local import LocalFileStore
from nexus_persistence.file_store.memory import InMemoryFileStore
from nexus_persistence.file_store.protocol import FileStore

__all__ = [
    "FileStore",
    "FileStoreError",
    "FileStoreIntegrityError",
    "FileStoreNotFoundError",
    "InMemoryFileStore",
    "LocalFileStore",
    "blob_digest",
    "opaque_content_reference",
]
