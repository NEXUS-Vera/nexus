"""Contract tests for the project store factory."""

from __future__ import annotations

from nexus_persistence.factory import build_project_store

# Declared on ProjectPackageStore in nexus_persistence/protocol.py.
PROTOCOL_METHODS = (
    "save_initialization_package",
    "save_modification_package",
    "get_current_state",
    "get_artifacts",
    "get_artifact",
    "get_history",
    "list_dependencies",
)


def test_build_project_store_returns_store_for_sqlite_backend() -> None:
    store = build_project_store(backend="sqlite", database_url="sqlite://")

    for method_name in PROTOCOL_METHODS:
        assert callable(getattr(store, method_name, None)), method_name
