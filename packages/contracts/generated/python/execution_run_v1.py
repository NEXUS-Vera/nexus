# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Error(TypedDict, closed=True):
    code: str
    message: str

class Limits(TypedDict, closed=True):
    cpuMillis: NotRequired[int]
    memoryBytes: NotRequired[int]
    outputFileCount: int
    processCount: NotRequired[int]
    producedOutputBytes: int
    stderrBytes: int
    stdoutBytes: int
    totalLogBytes: int
    wallTimeMs: int
    workspaceBytes: int

class RuntimeIdentity(TypedDict, closed=True):
    commandSpecVersion: Literal['1.0.0']
    executableFingerprint: NotRequired[str]
    imageDigest: NotRequired[str]
    imageReference: NotRequired[str]
    isolationGuarantees: NotRequired[list[str]]
    isolationLimitations: NotRequired[list[str]]
    limits: Limits
    networkPolicy: NotRequired[Literal['none', 'restricted']]
    runtimeKind: Literal['process', 'container']
    runtimeVersion: str
    securityLevel: NotRequired[Literal['limited', 'isolated']]
    workspaceManifestDigest: str
    workspaceSnapshotId: str

class ExecutionRunV1(TypedDict, closed=True):
    artifactId: NotRequired[str]
    baseArtifactVersion: int
    baseProjectStateVersion: int
    capability: Literal[
        'structured-validation',
        'fake-execution',
        'file-workspace',
        'sandbox-execution',
        'embedded-build',
        'python-kernel',
        'circuit-simulation',
        'architecture-export',
    ]
    cleanupWarning: NotRequired[str]
    completedAt: NotRequired[str]
    error: NotRequired[Error]
    evidenceReferences: list[str]
    executionJobId: NotRequired[str]
    executionRequestId: str
    executionRunId: str
    inputSnapshotId: str
    logReference: NotRequired[str]
    outputReferences: list[str]
    projectId: str
    providerId: str
    runtimeIdentity: NotRequired[RuntimeIdentity]
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
