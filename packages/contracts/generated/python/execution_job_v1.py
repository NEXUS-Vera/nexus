# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class DeclaredOutput(TypedDict, closed=True):
    kind: Literal['result', 'artifact', 'log']
    path: str

class EnvironmentItem(TypedDict, closed=True):
    name: str
    value: str

class CommandSpec(TypedDict, closed=True):
    arguments: list[str]
    declaredOutputs: list[DeclaredOutput]
    environment: list[EnvironmentItem]
    executable: str
    schemaVersion: Literal['1.0.0']
    workingDirectory: str

class Failure(TypedDict, closed=True):
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

class RuntimeHandle(TypedDict, closed=True):
    containerId: NotRequired[str]
    pid: NotRequired[int]

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

class ExecutionJobV1(TypedDict, closed=True):
    cleanupWarning: NotRequired[str]
    commandSpec: CommandSpec
    completedAt: NotRequired[str]
    createdAt: str
    executionJobId: str
    executionRunId: str
    exitCode: NotRequired[int]
    failure: NotRequired[Failure]
    limits: Limits
    logTruncated: NotRequired[bool]
    projectId: str
    queuePosition: NotRequired[int]
    runtimeHandle: NotRequired[RuntimeHandle]
    runtimeIdentity: RuntimeIdentity
    runtimeKind: Literal['process', 'container']
    schemaVersion: Literal['1.0.0']
    startedAt: NotRequired[str]
    status: Literal[
        'queued',
        'starting',
        'running',
        'cancelling',
        'succeeded',
        'failed',
        'timed-out',
        'cancelled',
    ]
    workspaceSnapshotId: str
