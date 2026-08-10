# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

class Input(TypedDict, closed=True):
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'electrical-architecture',
        'physical-architecture',
    ]
    initialContent: NotRequired[dict[str, Any]]

class RequestedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ArtifactCommandV11(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.create']
    input: Input
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: NotRequired[str]

class Input1(TypedDict, closed=True):
    content: dict[str, Any]
    expectedDraftVersion: int

class ArtifactCommandV12(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.update-draft']
    input: Input1
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input2(TypedDict, closed=True):
    reason: str

class ArtifactCommandV13(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.create-snapshot']
    input: Input2
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input3(TypedDict, closed=True):
    snapshotId: str

class ArtifactCommandV14(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.restore-snapshot']
    input: Input3
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class ArtifactCommandV15(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['artifact.validate-draft']
    input: Input3
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input5(TypedDict, closed=True):
    consequenceLevel: Literal['low', 'medium', 'high', 'safety-critical']
    snapshotId: str
    summary: NotRequired[str]

class ArtifactCommandV16(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['artifact.propose-revision']
    input: Input5
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input6(TypedDict, closed=True):
    proposalId: str
    reason: NotRequired[str]

class ArtifactCommandV17(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['artifact.accept-revision']
    input: Input6
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input7(TypedDict, closed=True):
    proposalId: str
    reason: str

class ArtifactCommandV18(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['artifact.reject-revision']
    input: Input7
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input8(TypedDict, closed=True):
    capability: Literal[
        'structured-validation',
        'fake-execution',
        'file-workspace',
        'embedded-build',
        'python-kernel',
        'circuit-simulation',
        'architecture-export',
    ]
    executionMode: NotRequired[Literal['validate', 'simulate']]
    expectedText: NotRequired[str]
    maxDurationMs: NotRequired[int]
    maxOutputBytes: NotRequired[int]
    requestedOutputs: NotRequired[
        list[
            Literal[
                'serial-log',
                'logic-trace',
                'simulation-screenshot',
                'provider-workspace',
            ]
        ]
    ]
    snapshotId: str

class ArtifactCommandV19(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['artifact.execute']
    input: Input8
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input9(TypedDict, closed=True):
    ttlSeconds: NotRequired[int]

class ArtifactCommandV110(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.acquire-edit-lease']
    input: Input9
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input10(TypedDict, closed=True):
    leaseToken: NotRequired[str]

class ArtifactCommandV111(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.release-edit-lease']
    input: Input10
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input11(TypedDict, closed=True):
    expectedDraftVersion: int
    refreshLease: NotRequired[bool]

class ArtifactCommandV112(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['workspace.discard-draft']
    input: Input11
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: str

class Input12(TypedDict, closed=True):
    entityId: str
    entityType: Literal['functional-node']

class ArtifactCommandV113(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    commandId: str
    commandType: Literal['artifact.inspect-deletion-impact']
    input: Input12
    projectId: str
    requestedAt: str
    requestedBy: RequestedBy
    schemaVersion: Literal['1.0.0']
    workspaceId: NotRequired[str]

ArtifactCommandV1: TypeAlias = (
    ArtifactCommandV11
    | ArtifactCommandV12
    | ArtifactCommandV13
    | ArtifactCommandV14
    | ArtifactCommandV15
    | ArtifactCommandV16
    | ArtifactCommandV17
    | ArtifactCommandV18
    | ArtifactCommandV19
    | ArtifactCommandV110
    | ArtifactCommandV111
    | ArtifactCommandV112
    | ArtifactCommandV113
)
