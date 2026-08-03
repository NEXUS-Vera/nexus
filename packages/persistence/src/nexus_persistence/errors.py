"""Stable persistence and retrieval errors (no SQL leakage)."""

from __future__ import annotations


class PersistenceError(Exception):
    code: str = "PROJECT_PERSISTENCE_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message


class ProjectNotFoundError(PersistenceError):
    code = "PROJECT_NOT_FOUND"


class ArtifactNotFoundError(PersistenceError):
    code = "ARTIFACT_NOT_FOUND"


class ArtifactVersionNotFoundError(PersistenceError):
    code = "ARTIFACT_VERSION_NOT_FOUND"


class ProjectPersistenceError(PersistenceError):
    code = "PROJECT_PERSISTENCE_FAILED"


class ProjectRetrievalError(PersistenceError):
    code = "PROJECT_RETRIEVAL_FAILED"
