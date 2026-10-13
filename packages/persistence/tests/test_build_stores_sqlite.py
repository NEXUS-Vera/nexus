"""build_stores must support the SQLite backend used by the packaged desktop shell."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nexus_persistence import build_stores


def test_build_stores_sqlite_creates_project_and_kernel_schema(tmp_path: Path) -> None:
    db = tmp_path / "nexus.sqlite3"
    project_store, kernel_store = build_stores("sqlite", f"sqlite:///{db}")
    assert project_store is not None
    assert kernel_store is not None
    tables = {
        row[0]
        for row in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")
    }
    assert {"projects", "workspaces", "artifact_revisions", "project_events"} <= tables
