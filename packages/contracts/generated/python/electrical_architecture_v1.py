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

class Connection(TypedDict, closed=True):
    connectionId: str
    connectionType: Literal[
        'signal', 'bus', 'power', 'ground', 'communication', 'control', 'other'
    ]
    description: NotRequired[str]
    fromInterfaceId: NotRequired[str]
    fromNodeId: str
    functionalArchitectureEdgeIds: NotRequired[list[str]]
    interfaceType: Literal[
        'analog',
        'gpio',
        'i2c',
        'spi',
        'uart',
        'can',
        'usb',
        'ethernet',
        'pwm',
        'power',
        'ground',
        'other',
        'unknown',
    ]
    provenance: NotRequired[Provenance]
    provisionalReason: NotRequired[str]
    status: Literal['resolved', 'provisional', 'unresolved', 'needs-resolution']
    toInterfaceId: NotRequired[str]
    toNodeId: str

class CoverageSummary(TypedDict, closed=True):
    approvedImplementationCount: int
    coveredFunctionalNodes: int
    preferredImplementationCount: int
    totalFunctionalNodes: int
    uncoveredFunctionalNodeIds: list[str]
    unresolvedConnectionCount: int
    unresolvedImplementationCount: int

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

class Voltage(TypedDict, closed=True):
    schemaVersion: Literal['1.0.0']
    unit: str
    value: float

class Interface(TypedDict, closed=True):
    direction: Literal['in', 'out', 'bidirectional', 'unknown']
    interfaceId: str
    interfaceType: Literal[
        'analog',
        'gpio',
        'i2c',
        'spi',
        'uart',
        'can',
        'usb',
        'ethernet',
        'pwm',
        'power',
        'ground',
        'other',
        'unknown',
    ]
    label: NotRequired[str]
    notes: NotRequired[str]
    provenance: NotRequired[Provenance1]
    status: Literal['resolved', 'unresolved', 'unknown', 'needs-resolution']
    voltage: NotRequired[Voltage]

class Node(TypedDict, closed=True):
    assumptions: NotRequired[list[str]]
    componentCandidateId: NotRequired[str]
    componentRoleIds: list[str]
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    functionalArchitectureNodeIds: list[str]
    implementationStatus: Literal[
        'unresolved', 'preferred', 'approved', 'provisional', 'unsupported'
    ]
    interfaces: NotRequired[list[Interface]]
    name: str
    nodeId: str
    nodeType: Literal[
        'component',
        'power-source',
        'power-regulator',
        'connector',
        'protection',
        'supporting-electronics',
        'external-interface',
        'junction',
    ]
    notes: NotRequired[str]
    requirementIds: NotRequired[list[str]]
    selectionState: NotRequired[Literal['preferred', 'approved', 'unresolved', 'none']]

class NominalVoltage(TypedDict, closed=True):
    schemaVersion: Literal['1.0.0']
    unit: str
    value: float

class SourceReference2(TypedDict, closed=True):
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

class Provenance2(TypedDict, closed=True):
    derivedFromIds: NotRequired[list[str]]
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceReference: NotRequired[SourceReference2 | str]
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

class PowerDomain(TypedDict, closed=True):
    memberNodeIds: NotRequired[list[str]]
    name: str
    nominalVoltage: NotRequired[NominalVoltage]
    notes: NotRequired[str]
    powerDomainId: str
    provenance: NotRequired[Provenance2]
    status: Literal['known', 'unknown', 'needs-resolution']

class UnresolvedDecision(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class Warning(TypedDict, closed=True):
    code: str
    message: str
    relatedNodeIds: NotRequired[list[str]]
    severity: Literal['info', 'warning', 'blocking']

class ElectricalArchitectureV1(TypedDict, closed=True):
    architectureId: str
    assumptions: list[Assumption]
    connections: list[Connection]
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
    powerDomains: list[PowerDomain]
    selectionBasisSummary: str
    summary: str
    unresolvedDecisions: list[UnresolvedDecision]
    warnings: list[Warning]
