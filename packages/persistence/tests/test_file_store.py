"""Local and in-memory file store tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from nexus_persistence.file_store import LocalFileStore, blob_digest
from nexus_persistence.file_store.errors import FileStoreNotFoundError
from nexus_persistence.file_store.memory import InMemoryFileStore


def test_memory_and_local_parity(tmp_path: Path) -> None:
    memory = InMemoryFileStore()
    local = LocalFileStore(tmp_path / "store")
    payload = b"hello-nexus"
    m_hash = memory.put(payload)
    l_hash = local.put(payload)
    assert m_hash == l_hash == blob_digest(payload)
    assert memory.get(m_hash) == local.get(l_hash) == payload
    assert memory.exists(m_hash) and local.exists(l_hash)
    with pytest.raises(FileStoreNotFoundError):
        memory.get("sha256:" + ("0" * 64))


def test_local_atomic_replace_and_no_tmp_leak(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "store")
    digest = store.put(b"one")
    store.put(b"one")
    hex_digest = digest.removeprefix("sha256:")
    final = tmp_path / "store" / hex_digest[:2] / hex_digest[2:4] / hex_digest
    assert final.is_file()
    leftovers = list((tmp_path / "store").rglob("*.tmp"))
    assert leftovers == []


@pytest.mark.parametrize(
    "url, expected",
    [
        ("sqlite:///project.db", "files"),
        ("sqlite+pysqlite:///nested/project.db", "nested/files"),
        ("sqlite://", None),
        ("sqlite:///:memory:", None),
        ("sqlite:///file:shared?mode=memory&cache=shared&uri=true", None),
        ("sqlite:///file::memory:?cache=shared&uri=true", None),
        ("postgresql://localhost/nexus", None),
    ],
)
def test_default_sqlite_file_store_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, url: str, expected: str | None
) -> None:
    from nexus_persistence.file_store.local import default_sqlite_file_store_root

    monkeypatch.chdir(tmp_path)
    root = default_sqlite_file_store_root(url)
    assert root == (tmp_path / expected if expected else None)
    assert not (tmp_path / "files").exists()
    assert default_sqlite_file_store_root(f"sqlite:///{tmp_path / 'db.sqlite'}") == (
        tmp_path / "files"
    )
