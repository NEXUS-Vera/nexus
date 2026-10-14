"""Local content-addressed file store with atomic writes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from nexus_persistence.file_store.errors import FileStoreIntegrityError, FileStoreNotFoundError
from nexus_persistence.file_store.hashing import blob_digest, digest_hex


class LocalFileStore:
    """Store blobs under an application-controlled root.

    Layout: ``{root}/{ab}/{cd}/{abcdef...}`` where the filename is the full
    hex digest without the ``sha256:`` prefix. Temporary objects use ``.tmp``
    suffixes and are finalized with ``os.replace``.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def put(self, data: bytes) -> str:
        content_hash = blob_digest(data)
        hex_digest = digest_hex(content_hash)
        final_path = self._path_for(hex_digest)
        if final_path.is_file():
            existing = final_path.read_bytes()
            if existing != data:
                raise FileStoreIntegrityError("Content-addressed collision with differing bytes")
            return content_hash
        final_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{hex_digest}.",
            suffix=".tmp",
            dir=str(final_path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            written = tmp_path.read_bytes()
            if blob_digest(written) != content_hash:
                raise FileStoreIntegrityError("Written blob failed hash verification")
            os.replace(tmp_path, final_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
        return content_hash

    def get(self, content_hash: str) -> bytes:
        path = self._path_for(digest_hex(content_hash))
        if not path.is_file():
            raise FileStoreNotFoundError(f"Blob not found: {content_hash}")
        data = path.read_bytes()
        if blob_digest(data) != content_hash:
            raise FileStoreIntegrityError("Stored blob failed hash verification")
        return data

    def exists(self, content_hash: str) -> bool:
        try:
            return self._path_for(digest_hex(content_hash)).is_file()
        except ValueError:
            return False

    def delete(self, content_hash: str) -> None:
        try:
            path = self._path_for(digest_hex(content_hash))
        except ValueError:
            return
        path.unlink(missing_ok=True)

    def list_content_hashes(self) -> set[str]:
        hashes: set[str] = set()
        if not self._root.is_dir():
            return hashes
        for path in self._root.rglob("*"):
            if not path.is_file() or path.name.startswith(".") or path.suffix == ".tmp":
                continue
            name = path.name
            if len(name) == 64 and all(ch in "0123456789abcdef" for ch in name):
                hashes.add(f"sha256:{name}")
        return hashes

    def size(self, content_hash: str) -> int:
        path = self._path_for(digest_hex(content_hash))
        if not path.is_file():
            raise FileStoreNotFoundError(f"Blob not found: {content_hash}")
        return path.stat().st_size

    def _path_for(self, hex_digest: str) -> Path:
        return self._root / hex_digest[:2] / hex_digest[2:4] / hex_digest
