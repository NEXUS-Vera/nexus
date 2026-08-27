"""Shared project-package persistence for Nexus."""

from __future__ import annotations

from nexus_persistence.errors import (
    ArtifactNotFoundError,
    ArtifactVersionConflictError,
    ArtifactVersionNotFoundError,
    ExecutionNotFoundError,
    LedgerImmutableError,
    ProjectNotFoundError,
    ProjectPersistenceError,
    ProjectRetrievalError,
    ProjectStateConflictError,
    ProposalNotFoundError,
    SnapshotImmutableError,
    SnapshotNotFoundError,
    WorkspaceNotFoundError,
)
from nexus_persistence.factory import build_kernel_store, build_project_store, build_stores
from nexus_persistence.file_store import (
    FileStore,
    InMemoryFileStore,
    LocalFileStore,
    blob_digest,
    opaque_content_reference,
)
from nexus_persistence.memory.kernel_store import InMemoryKernelStore
from nexus_persistence.memory.store import InMemoryProjectStore
from nexus_persistence.protocol import ProjectKernelStore, ProjectPackageStore

__all__ = [
    "ArtifactNotFoundError",
    "ArtifactVersionConflictError",
    "ArtifactVersionNotFoundError",
    "ExecutionNotFoundError",
    "FileStore",
    "InMemoryFileStore",
    "InMemoryKernelStore",
    "InMemoryProjectStore",
    "LedgerImmutableError",
    "LocalFileStore",
    "ProjectKernelStore",
    "ProjectNotFoundError",
    "ProjectPackageStore",
    "ProjectPersistenceError",
    "ProjectRetrievalError",
    "ProjectStateConflictError",
    "ProposalNotFoundError",
    "SnapshotImmutableError",
    "SnapshotNotFoundError",
    "WorkspaceNotFoundError",
    "blob_digest",
    "build_kernel_store",
    "build_project_store",
    "build_stores",
    "opaque_content_reference",
]
