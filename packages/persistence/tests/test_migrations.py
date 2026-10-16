"""Migration tests for the project persistence schema."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from nexus_persistence.factory import build_project_store
from nexus_persistence.postgres.models import Base
from sqlalchemy import create_engine, inspect, text

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    # Read through the checked-in file rather than pointed at the scripts
    # directly, so the configuration the tests migrate with is the one
    # `make db-migrate` and CI use.
    return Config(str(PACKAGE_ROOT / "alembic.ini"))


def test_alembic_upgrade_head_on_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'fresh.db'}"
    monkeypatch.setenv("NEXUS_DATABASE_URL", database_url)

    command.upgrade(_alembic_config(), "head")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert set(Base.metadata.tables) <= tables


def test_migrated_sqlite_schema_applies_dependency_created_at_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'fresh.db'}"
    monkeypatch.setenv("NEXUS_DATABASE_URL", database_url)
    command.upgrade(_alembic_config(), "head")

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO artifact_dependencies (dependency_id, project_id, payload) "
                    "VALUES ('dep_TEST', 'proj_TEST', '{}')"
                )
            )
            created_at = connection.execute(
                text(
                    "SELECT created_at FROM artifact_dependencies WHERE dependency_id = 'dep_TEST'"
                )
            ).scalar_one()
    finally:
        engine.dispose()

    assert created_at is not None


def test_store_created_sqlite_database_is_upgradable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'desktop.db'}"
    monkeypatch.setenv("NEXUS_DATABASE_URL", database_url)

    # A shipped desktop app creates the database by opening a store...
    build_project_store(backend="sqlite", database_url=database_url)

    # ...and a later release upgrades that same file.
    command.upgrade(_alembic_config(), "head")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert set(Base.metadata.tables) <= tables


def test_migration_preserves_existing_logger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    logger = logging.getLogger("nexus.persistence.migration_regression")
    assert not logger.disabled
    monkeypatch.setenv("NEXUS_DATABASE_URL", f"sqlite:///{tmp_path / 'logging.db'}")

    command.upgrade(_alembic_config(), "head")

    assert not logger.disabled
    # fileConfig replaces root handlers; attach pytest's capture handler again.
    with caplog.at_level(logging.WARNING, logger=logger.name):
        logging.getLogger().addHandler(caplog.handler)
        logger.warning("logger survived migration")
    assert (logger.name, logging.WARNING, "logger survived migration") in caplog.record_tuples
