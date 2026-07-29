"""Shared project-package persistence for Nexus."""

from __future__ import annotations

from nexus_persistence.errors import (
    ArtifactNotFoundError,
    ArtifactVersionNotFoundError,
    ProjectNotFoundError,
    ProjectPersistenceError,
    ProjectRetrievalError,
)
from nexus_persistence.factory import build_project_store
from nexus_persistence.memory.store import InMemoryProjectStore
from nexus_persistence.protocol import ProjectPackageStore

__all__ = [
    "ArtifactNotFoundError",
    "ArtifactVersionNotFoundError",
    "InMemoryProjectStore",
    "ProjectNotFoundError",
    "ProjectPackageStore",
    "ProjectPersistenceError",
    "ProjectRetrievalError",
    "build_project_store",
]
