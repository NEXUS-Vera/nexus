# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Error(TypedDict, closed=True):
    code: str
    message: str

class ProducedArtifactReference(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
    ]
    artifactVersion: int

class ArtifactCommandResultV1(TypedDict, closed=True):
    artifactId: str
    commandId: str
    commandRunId: str
    completedAt: NotRequired[str]
    error: NotRequired[Error]
    evidenceReferences: list[str]
    executionRunId: NotRequired[str]
    issueReferences: list[str]
    outputReferences: list[str]
    producedArtifactReference: NotRequired[ProducedArtifactReference]
    projectId: str
    proposalId: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    snapshotId: NotRequired[str]
    startedAt: str
    status: Literal[
        'accepted',
        'running',
        'completed',
        'completed-with-warnings',
        'rejected',
        'failed',
        'conflicted',
    ]
    workspaceId: NotRequired[str]
