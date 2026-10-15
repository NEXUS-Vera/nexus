# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Assumption(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str

class CoverageSummary(TypedDict, closed=True):
    coveredElectricalNodes: int
    provisionalRelationshipCount: int
    totalElectricalNodes: int
    uncoveredElectricalNodeIds: list[str]
    unresolvedPlacementCount: int

class Attribution(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference(TypedDict, closed=True):
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

class Provenance(TypedDict, closed=True):
    derivedFromIds: NotRequired[list[str]]
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceReference: NotRequired[SourceReference | str]
    sourceType: Literal[
        'fixture',
        'component-plan',
        'user',
        'llm-derived',
        'manufacturer-datasheet',
        'external-provider',
        'runtime-output',
        'derived',
        'unknown',
    ]

class Node(TypedDict, closed=True):
    constraints: NotRequired[list[str]]
    electricalNodeIds: list[str]
    name: str
    nodeId: str
    nodeType: Literal[
        'assembly',
        'board',
        'module',
        'sensor',
        'actuator',
        'power-source',
        'connector',
        'enclosure',
        'mount',
        'external-system',
        'zone',
    ]
    notes: NotRequired[str]
    placementStatus: Literal['placed', 'unresolved', 'provisional', 'unknown']
    provenance: NotRequired[Provenance]
    qualitativePlacement: NotRequired[str]
    zoneId: NotRequired[str]

class SourceReference1(TypedDict, closed=True):
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

class Provenance1(TypedDict, closed=True):
    derivedFromIds: NotRequired[list[str]]
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceReference: NotRequired[SourceReference1 | str]
    sourceType: Literal[
        'fixture',
        'component-plan',
        'user',
        'llm-derived',
        'manufacturer-datasheet',
        'external-provider',
        'runtime-output',
        'derived',
        'unknown',
    ]

class Relationship(TypedDict, closed=True):
    fromNodeId: str
    provenance: NotRequired[Provenance1]
    relationshipId: str
    relationshipType: Literal[
        'mounted-on',
        'inside',
        'attached-to',
        'adjacent-to',
        'connected-to',
        'exposed-to',
        'isolated-from',
    ]
    status: Literal['resolved', 'provisional', 'unresolved']
    toNodeId: str

class UnresolvedDecision(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class Warning(TypedDict, closed=True):
    code: str
    message: str
    relatedNodeIds: NotRequired[list[str]]
    severity: Literal['info', 'warning', 'blocking']

class Zone(TypedDict, closed=True):
    memberNodeIds: NotRequired[list[str]]
    name: str
    notes: NotRequired[str]
    zoneId: str
    zoneKind: Literal[
        'enclosure',
        'chassis',
        'external-sensing',
        'power',
        'user-interface',
        'other',
        'unknown',
    ]

class PhysicalArchitectureV1(TypedDict, closed=True):
    architectureId: str
    assumptions: list[Assumption]
    coverageSummary: CoverageSummary
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    maturity: Literal['provisional', 'drafted', 'reviewed', 'approved']
    nodes: list[Node]
    relationships: list[Relationship]
    summary: str
    unresolvedDecisions: list[UnresolvedDecision]
    warnings: list[Warning]
    zones: list[Zone]
