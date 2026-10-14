"""File-store errors."""

from __future__ import annotations

from nexus_persistence.errors import ProjectPersistenceError


class FileStoreError(ProjectPersistenceError):
    code = "FILE_STORE_ERROR"


class FileStoreNotFoundError(FileStoreError):
    code = "FILE_STORE_NOT_FOUND"


class FileStoreIntegrityError(FileStoreError):
    code = "FILE_STORE_INTEGRITY"
