"""Durable file-store configuration defaults."""

from pathlib import Path

import pytest
from nexus_api.config import load_settings


@pytest.mark.parametrize("backend", ["sqlite", "sqlite3", "memory"])
@pytest.mark.parametrize("database", ["project.db", ":memory:", ""])
def test_file_store_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, backend: str, database: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEXUS_FILE_STORE_ROOT", raising=False)
    monkeypatch.setenv("NEXUS_STORAGE_BACKEND", backend)
    monkeypatch.setenv("NEXUS_DATABASE_URL", f"sqlite:///{database}" if database else "sqlite://")
    expected = str(tmp_path / "files") if backend != "memory" and database == "project.db" else ""
    assert load_settings().file_store_root == expected
    monkeypatch.setenv("NEXUS_FILE_STORE_ROOT", str(tmp_path / "custom"))
    assert load_settings().file_store_root == str(tmp_path / "custom")


def test_sqlite_without_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEXUS_STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("NEXUS_DATABASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_FILE_STORE_ROOT", raising=False)
    settings = load_settings()
    assert settings.database_url == "sqlite:///nexus.db"
    assert settings.file_store_root == str(tmp_path / "files")


@pytest.mark.parametrize("mode", ["fixture", "llm", "shadow"])
def test_authoring_independent_of_initialization(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from dataclasses import replace

    from nexus_api import main

    monkeypatch.setattr(
        main,
        "settings",
        replace(main.settings, initialization_provider=mode, model_credential="test-only"),
    )
    assert main._build_firmware_patch_generator() is not None
    assert main._build_analysis_patch_generator() is not None
    monkeypatch.setattr(main, "settings", replace(main.settings, model_credential=""))
    assert main._build_firmware_patch_generator() is None
    assert main._build_analysis_patch_generator() is None
