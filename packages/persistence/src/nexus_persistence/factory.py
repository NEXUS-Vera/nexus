"""Store factory."""

from __future__ import annotations

import os

from nexus_persistence.memory.store import InMemoryProjectStore
from nexus_persistence.postgres.session import create_db_engine, create_session_factory
from nexus_persistence.postgres.store import PostgresProjectStore
from nexus_persistence.protocol import ProjectPackageStore


def build_project_store(
    backend: str | None = None,
    database_url: str | None = None,
) -> ProjectPackageStore:
    mode = (backend or os.environ.get("NEXUS_STORAGE_BACKEND") or "memory").strip().lower()
    if mode in {"memory", "mem", "inmemory"}:
        return InMemoryProjectStore()
    if mode in {"postgres", "postgresql", "pg"}:
        url = (
            database_url
            or os.environ.get("NEXUS_DATABASE_URL")
            or "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
        )
        engine = create_db_engine(url)
        return PostgresProjectStore(create_session_factory(engine))
    if mode in {"sqlite", "sqlite3"}:
        url = database_url or os.environ.get("NEXUS_DATABASE_URL") or "sqlite:///nexus.db"
        engine = create_db_engine(url)
        return PostgresProjectStore(create_session_factory(engine))
    raise ValueError(f"Unsupported storage backend: {mode}")
