"""Kernel file-store selection follows the actual database and explicit overrides."""

from pathlib import Path

import pytest
from nexus_board import build_project_kernel
from nexus_persistence import InMemoryFileStore, LocalFileStore, build_stores


@pytest.mark.parametrize(
    "backend, database", [("memory", ""), ("sqlite", ":memory:"), ("sqlite", "project.db")]
)
def test_kernel_file_store_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, database: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEXUS_FILE_STORE_ROOT", raising=False)
    projects, store = build_stores(backend, f"sqlite:///{database}")
    kernel = build_project_kernel(store, project_store=projects, auto_start_scheduler=False)
    if database == "project.db":
        assert isinstance(kernel.file_store, LocalFileStore)
        assert kernel.file_store.root == tmp_path / "files"
    else:
        assert isinstance(kernel.file_store, InMemoryFileStore)
        assert not (tmp_path / "files").exists()

    monkeypatch.setenv("NEXUS_FILE_STORE_ROOT", str(tmp_path / "custom"))
    kernel = build_project_kernel(store, project_store=projects, auto_start_scheduler=False)
    assert isinstance(kernel.file_store, LocalFileStore)
    assert kernel.file_store.root == tmp_path / "custom"
    explicit = InMemoryFileStore()
    kernel = build_project_kernel(
        store, project_store=projects, file_store=explicit, auto_start_scheduler=False
    )
    assert kernel.file_store is explicit
