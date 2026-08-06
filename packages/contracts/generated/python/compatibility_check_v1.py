# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Attribution(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class EvidenceReference(TypedDict, closed=True):
    attribution: NotRequired[Attribution]
    evidenceId: str
    evidenceStrength: Literal['direct', 'supporting', 'inferred', 'contradicting']
    schemaVersion: Literal['1.0.0']
    sourceId: str
    sourceLocator: NotRequired[str]
    sourceType: Literal[
        'user-turn',
        'project-policy',
        'document',
        'external-source',
        'calculation',
        'test-result',
        'agent-inference',
    ]
    supportedClaim: NotRequired[str]

class PerformedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class CompatibilityCheckV1(TypedDict, closed=True):
    candidateId: str
    checkType: Literal[
        'requirement-fit',
        'architecture-fit',
        'electrical-supply',
        'logic-level',
        'interface-type',
        'interface-bandwidth',
        'bus-address',
        'pin-availability',
        'performance',
        'sample-rate',
        'bandwidth',
        'power-budget',
        'environmental',
        'mechanical',
        'firmware-support',
        'driver-availability',
        'cost',
        'availability',
        'documentation-quality',
    ]
    compatibilityCheckId: str
    componentRoleId: str
    evidenceReferences: list[EvidenceReference]
    inputReferences: list[str]
    performedAt: NotRequired[str]
    performedBy: NotRequired[PerformedBy]
    reason: str
    severity: Literal['info', 'warning', 'blocking']
    status: Literal[
        'not-checked',
        'unknown',
        'pass',
        'conditional',
        'warning',
        'fail',
        'not-applicable',
    ]
