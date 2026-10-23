# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class DecidedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class InputArtifactReference(TypedDict, closed=True):
    artifactId: NotRequired[str]
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
        'firmware',
        'electrical-architecture',
        'physical-architecture',
        'analysis',
        'test-plan',
        'risk-register',
        'execution-plan',
    ]
    artifactVersion: int

class Operations(TypedDict, closed=True):
    content: str
    contentHash: str
    operationType: Literal['create-file']
    path: str

class Operations1(TypedDict, closed=True):
    content: str
    contentHash: str
    expectedBaseHash: str
    operationType: Literal['replace-file']
    path: str

class Operations2(TypedDict, closed=True):
    expectedBaseHash: str
    operationType: Literal['delete-file']
    path: str

class RequestedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class AnalysisPatchProposalV1(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal['analysis']
    baseSnapshotId: str
    decidedAt: NotRequired[str]
    decidedBy: NotRequired[DecidedBy]
    generatorId: str
    generatorVersion: str
    inputArtifactReferences: list[InputArtifactReference]
    operations: list[Operations | Operations1 | Operations2]
    projectId: str
    proposalId: str
    requestedAt: str
    requestedBy: RequestedBy
    requestedChange: str
    schemaVersion: Literal['1.0.0']
    status: Literal['proposed', 'applied', 'discarded']
    workspaceId: str
