"""Store factory."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from nexus_persistence.memory.kernel_store import InMemoryKernelStore
from nexus_persistence.memory.store import InMemoryProjectStore
from nexus_persistence.postgres.kernel_store import PostgresKernelStore
from nexus_persistence.postgres.session import create_db_engine, create_session_factory
from nexus_persistence.postgres.store import PostgresProjectStore
from nexus_persistence.protocol import ProjectKernelStore, ProjectPackageStore

# The migration scripts ship inside the package rather than beside it, so this
# resolves the same way from a checkout and from an installed distribution.
_MIGRATION_SCRIPTS = Path(__file__).resolve().parent / "alembic"


def _upgrade_to_head(engine: Engine) -> None:
    """Bring a database up to the latest revision.

    Alembic stays the single schema authority, so a database created here carries
    a version stamp and a later release can upgrade it in place.
    """
    config = Config()
    config.set_main_option("script_location", str(_MIGRATION_SCRIPTS))
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


def build_kernel_store(
    backend: str | None = None,
    database_url: str | None = None,
    project_store: ProjectPackageStore | None = None,
) -> ProjectKernelStore:
    mode = (backend or os.environ.get("NEXUS_STORAGE_BACKEND") or "memory").strip().lower()
    if mode in {"memory", "mem", "inmemory"}:
        if project_store is not None and not isinstance(project_store, InMemoryProjectStore):
            raise ValueError("Memory kernel store requires InMemoryProjectStore")
        return InMemoryKernelStore(project_store=project_store or InMemoryProjectStore())
    if mode in {"postgres", "postgresql", "pg"}:
        url = (
            database_url
            or os.environ.get("NEXUS_DATABASE_URL")
            or "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
        )
        if project_store is not None and isinstance(project_store, PostgresProjectStore):
            return PostgresKernelStore(
                project_store._session_factory,  # noqa: SLF001
                project_store=project_store,
            )
        engine = create_db_engine(url)
        session_factory = create_session_factory(engine)
        pg_store = (
            project_store
            if isinstance(project_store, PostgresProjectStore)
            else PostgresProjectStore(session_factory)
        )
        return PostgresKernelStore(session_factory, project_store=pg_store)
    raise ValueError(f"Unsupported storage backend: {mode}")


def build_stores(
    backend: str | None = None,
    database_url: str | None = None,
) -> tuple[ProjectPackageStore, ProjectKernelStore]:
    mode = (backend or os.environ.get("NEXUS_STORAGE_BACKEND") or "memory").strip().lower()
    if mode in {"memory", "mem", "inmemory"}:
        memory_project = InMemoryProjectStore()
        return memory_project, InMemoryKernelStore(project_store=memory_project)
    if mode in {"postgres", "postgresql", "pg"}:
        url = (
            database_url
            or os.environ.get("NEXUS_DATABASE_URL")
            or "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
        )
        engine = create_db_engine(url)
        session_factory = create_session_factory(engine)
        pg_project = PostgresProjectStore(session_factory)
        return pg_project, PostgresKernelStore(session_factory, project_store=pg_project)
    if mode in {"sqlite", "sqlite3"}:
        url = database_url or os.environ.get("NEXUS_DATABASE_URL") or "sqlite:///nexus.db"
        engine = create_db_engine(url)
        # Same as build_project_store: the schema must exist before first use.
        _upgrade_to_head(engine)
        session_factory = create_session_factory(engine)
        sql_project = PostgresProjectStore(session_factory)
        return sql_project, PostgresKernelStore(session_factory, project_store=sql_project)
    raise ValueError(f"Unsupported storage backend: {mode}")
