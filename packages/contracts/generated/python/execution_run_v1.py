# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Error(TypedDict, closed=True):
    code: str
    message: str

class ExecutionRunV1(TypedDict, closed=True):
    artifactId: NotRequired[str]
    baseArtifactVersion: int
    baseProjectStateVersion: int
    capability: Literal[
        'structured-validation',
        'fake-execution',
        'file-workspace',
        'embedded-build',
        'python-kernel',
        'circuit-simulation',
        'architecture-export',
    ]
    completedAt: NotRequired[str]
    error: NotRequired[Error]
    evidenceReferences: list[str]
    executionRequestId: str
    executionRunId: str
    inputSnapshotId: str
    logReference: NotRequired[str]
    outputReferences: list[str]
    projectId: str
    providerId: str
    schemaVersion: Literal['1.0.0']
    startedAt: str
    status: Literal[
        'queued',
        'starting',
        'running',
        'completed',
        'completed-with-warnings',
        'failed',
        'cancelled',
        'timed-out',
        'stale',
    ]
    workspaceId: NotRequired[str]
