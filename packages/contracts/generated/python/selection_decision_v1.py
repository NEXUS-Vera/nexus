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

class ApprovedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ProposedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SelectionDecisionV1(TypedDict, closed=True):
    approvalRequirement: ApprovalRequirement
    approvedAt: NotRequired[str]
    approvedBy: NotRequired[ApprovedBy]
    componentRoleId: str
    createdAt: str
    proposedBy: ProposedBy
    rationale: str
    selectedCandidateId: str
    selectionDecisionId: str
    selectionState: Literal[
        'not-started',
        'proposed',
        'awaiting-user',
        'approved',
        'rejected',
        'superseded',
        'blocked',
    ]
    source: Literal['user-explicit', 'agent-proposed', 'fixture', 'inferred']
    supersedesSelectionDecisionId: NotRequired[str]
    tradeoffs: list[str]
