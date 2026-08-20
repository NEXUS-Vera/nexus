"""Store factory."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from nexus_persistence.memory.store import InMemoryProjectStore
from nexus_persistence.postgres.session import create_db_engine, create_session_factory
from nexus_persistence.postgres.store import PostgresProjectStore
from nexus_persistence.protocol import ProjectPackageStore

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _upgrade_to_head(engine: Engine) -> None:
    """Bring a database up to the latest revision.

    Alembic stays the single schema authority, so a database created here carries
    a version stamp and a later release can upgrade it in place.
    """
    config = Config()
    config.set_main_option("script_location", str(_PACKAGE_ROOT / "alembic"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


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
        # A SQLite database file is owned by the process that opens it, so the
        # schema has to exist before the first session touches it.
        _upgrade_to_head(engine)
        return PostgresProjectStore(create_session_factory(engine))
    raise ValueError(f"Unsupported storage backend: {mode}")
