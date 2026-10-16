# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

class Provenance(TypedDict, closed=True):
    generatedBy: NotRequired[Literal['fixture', 'llm', 'user', 'derived']]
    notes: NotRequired[str]

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

class Risk(TypedDict, closed=True):
    category: Literal[
        'electrical',
        'firmware',
        'communication',
        'power',
        'thermal',
        'mechanical',
        'integration',
        'performance',
        'data-quality',
        'safety',
    ]
    description: str
    displayId: str
    evidenceReferences: NotRequired[list[EvidenceReference]]
    likelihood: Literal['rare', 'unlikely', 'possible', 'likely']
    linkedArchitectureRefs: NotRequired[list[str]]
    linkedComponentIds: NotRequired[list[str]]
    linkedRequirementIds: NotRequired[list[str]]
    linkedTestIds: NotRequired[list[str]]
    mitigation: str
    priorityScore: int
    residualRisk: NotRequired[str]
    riskId: str
    severity: Literal['low', 'medium', 'high', 'critical']
    status: Literal['open', 'mitigating', 'mitigated', 'accepted', 'monitoring']
    title: str
    verificationTestIds: NotRequired[list[str]]

class Summary(TypedDict, closed=True):
    highOrCritical: int
    mitigated: int
    openRisks: int
    totalRisks: int
    unverifiedMitigations: int

class RiskRegisterV1(TypedDict, closed=True):
    provenance: NotRequired[Provenance]
    riskRegisterId: str
    risks: list[Risk]
    schemaVersion: Literal['1.0.0']
    summary: Summary
    title: NotRequired[str]

Likelihood: TypeAlias = Literal['rare', 'unlikely', 'possible', 'likely']

RiskCategory: TypeAlias = Literal[
    'electrical',
    'firmware',
    'communication',
    'power',
    'thermal',
    'mechanical',
    'integration',
    'performance',
    'data-quality',
    'safety',
]

class EvidenceReference1(TypedDict, closed=True):
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

class RiskItem(TypedDict, closed=True):
    category: Literal[
        'electrical',
        'firmware',
        'communication',
        'power',
        'thermal',
        'mechanical',
        'integration',
        'performance',
        'data-quality',
        'safety',
    ]
    description: str
    displayId: str
    evidenceReferences: NotRequired[list[EvidenceReference1]]
    likelihood: Literal['rare', 'unlikely', 'possible', 'likely']
    linkedArchitectureRefs: NotRequired[list[str]]
    linkedComponentIds: NotRequired[list[str]]
    linkedRequirementIds: NotRequired[list[str]]
    linkedTestIds: NotRequired[list[str]]
    mitigation: str
    priorityScore: int
    residualRisk: NotRequired[str]
    riskId: str
    severity: Literal['low', 'medium', 'high', 'critical']
    status: Literal['open', 'mitigating', 'mitigated', 'accepted', 'monitoring']
    title: str
    verificationTestIds: NotRequired[list[str]]

RiskStatus: TypeAlias = Literal[
    'open', 'mitigating', 'mitigated', 'accepted', 'monitoring'
]

class RiskSummary(TypedDict, closed=True):
    highOrCritical: int
    mitigated: int
    openRisks: int
    totalRisks: int
    unverifiedMitigations: int

Severity: TypeAlias = Literal['low', 'medium', 'high', 'critical']
