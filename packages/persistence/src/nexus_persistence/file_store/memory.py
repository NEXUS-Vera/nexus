"""In-memory content-addressed file store for tests."""

from __future__ import annotations

from nexus_persistence.file_store.errors import FileStoreNotFoundError
from nexus_persistence.file_store.hashing import blob_digest


class InMemoryFileStore:
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        content_hash = blob_digest(data)
        existing = self._blobs.get(content_hash)
        if existing is not None and existing != data:
            raise ValueError("Content-addressed collision with differing bytes")
        self._blobs[content_hash] = data
        return content_hash

    def get(self, content_hash: str) -> bytes:
        data = self._blobs.get(content_hash)
        if data is None:
            raise FileStoreNotFoundError(f"Blob not found: {content_hash}")
        return data

    def exists(self, content_hash: str) -> bool:
        return content_hash in self._blobs

    def delete(self, content_hash: str) -> None:
        self._blobs.pop(content_hash, None)

    def list_content_hashes(self) -> set[str]:
        return set(self._blobs)

    def size(self, content_hash: str) -> int:
        data = self._blobs.get(content_hash)
        if data is None:
            raise FileStoreNotFoundError(f"Blob not found: {content_hash}")
        return len(data)
