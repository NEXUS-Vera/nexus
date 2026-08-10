# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ApprovalRequirement(TypedDict, closed=True):
    allowedApproverKinds: list[Literal['user', 'agent', 'system']]
    autoAcceptAllowed: NotRequired[bool]
    consequenceLevel: Literal['low', 'medium', 'high', 'safety-critical']
    reason: str
    required: bool
    schemaVersion: Literal['1.0.0']

class DecidedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ProposedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ArtifactProposalV1(TypedDict, closed=True):
    approvalRequirement: ApprovalRequirement
    artifactId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'electrical-architecture',
        'physical-architecture',
    ]
    baseArtifactVersion: int
    baseProjectStateVersion: int
    consequenceLevel: Literal['low', 'medium', 'high', 'safety-critical']
    decidedAt: NotRequired[str]
    decidedBy: NotRequired[DecidedBy]
    decisionReason: NotRequired[str]
    projectId: str
    proposalId: str
    proposedAt: str
    proposedBy: ProposedBy
    resultingArtifactId: NotRequired[str]
    resultingArtifactVersion: NotRequired[int]
    schemaVersion: Literal['1.0.0']
    snapshotId: str
    status: Literal[
        'proposed',
        'awaiting-approval',
        'accepted',
        'rejected',
        'superseded',
        'conflicted',
    ]
    workspaceId: str
