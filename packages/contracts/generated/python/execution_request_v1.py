# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class RequestedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ResourceLimits(TypedDict, closed=True):
    maxDurationMs: int
    maxOutputBytes: NotRequired[int]

class ExecutionRequestV1(TypedDict, closed=True):
    artifactId: str
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
    executionRequestId: str
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    resourceLimits: ResourceLimits
    schemaVersion: Literal['1.0.0']
    snapshotId: str
    workspaceId: str
