# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class EntityReference(TypedDict, closed=True):
    artifactId: str
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
    artifactVersion: NotRequired[int]
    displayLabel: NotRequired[str]
    entityId: str
    entityType: Literal[
        'requirement',
        'functional-node',
        'functional-edge',
        'component-role',
        'component-candidate',
        'selection-decision',
        'electrical-node',
        'electrical-connection',
        'electrical-interface',
        'power-domain',
        'physical-node',
        'physical-relationship',
        'physical-zone',
        'open-question',
        'other',
    ]
    schemaVersion: Literal['1.0.0']

class Finding(TypedDict, closed=True):
    entityReference: NotRequired[EntityReference]
    findingId: str
    mappingType: Literal['exact', 'equivalent', 'surrogate', 'unsupported']
    message: str
    reasonCode: str

class CircuitSimulationSupportAssessmentV1(TypedDict, closed=True):
    capabilityId: Literal['circuit-simulation']
    findings: list[Finding]
    firmwareRequired: bool
    providerId: str
    schemaVersion: Literal['1.0.0']
    status: Literal[
        'SUPPORTED',
        'PARTIALLY_SUPPORTED',
        'UNSUPPORTED',
        'SURROGATE_REQUIRED',
        'FIRMWARE_REQUIRED',
    ]
    surrogateUsed: bool
