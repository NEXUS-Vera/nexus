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

class Value(TypedDict, closed=True):
    kind: Literal['unknown']

class Specification(TypedDict, closed=True):
    operator: NotRequired[
        Literal['eq', 'neq', 'gte', 'lte', 'gt', 'lt', 'in', 'contains', 'unknown']
    ]
    specKey: str
    unit: NotRequired[str]
    value: float | str | Value

class ComponentCandidateV1(TypedDict, closed=True):
    advantages: list[str]
    candidateCategory: Literal[
        'sensor',
        'compute',
        'power',
        'communication',
        'storage',
        'interface',
        'actuation',
        'protection',
        'mechanical',
        'supporting-electronics',
    ]
    candidateId: str
    candidateState: Literal[
        'discovered',
        'proposed',
        'shortlisted',
        'preferred',
        'selected',
        'rejected',
        'blocked',
        'superseded',
    ]
    compatibilityCheckIds: list[str]
    componentRoleId: str
    confidence: Literal['low', 'medium', 'high']
    displayName: str
    evidenceReferences: list[EvidenceReference]
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    limitations: list[str]
    manufacturer: str
    notes: NotRequired[str]
    partNumber: str
    source: Literal[
        'fixture',
        'agent-inference',
        'user-provided',
        'future-datasheet',
        'future-tool-output',
    ]
    specifications: list[Specification]
