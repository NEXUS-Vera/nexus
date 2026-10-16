# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

class CoverageSummary(TypedDict, closed=True):
    blockedRequirements: int
    coveredRequirements: int
    failedRequirements: int
    totalRequirements: int
    uncoveredRequirements: int
    unverifiedRequirements: int
    verifiedRequirements: int

class Provenance(TypedDict, closed=True):
    generatedBy: NotRequired[Literal['fixture', 'llm', 'user', 'derived']]
    notes: NotRequired[str]

class Criterion(TypedDict, closed=True):
    criterionType: Literal[
        'numeric-comparison',
        'exact-match',
        'contains',
        'existence',
        'structural-mapping',
        'range',
    ]
    expectedMapping: NotRequired[str]
    expectedValue: NotRequired[Any]
    marker: NotRequired[str]
    maxValue: NotRequired[float]
    metricId: NotRequired[str]
    minValue: NotRequired[float]
    operator: NotRequired[Literal['<', '<=', '>', '>=', '==', '!=']]
    outputName: NotRequired[str]
    signal: NotRequired[str]
    tolerance: NotRequired[float]
    toleranceUnit: NotRequired[Literal['absolute', 'percent']]
    unit: NotRequired[str]

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

class TestCase(TypedDict, closed=True):
    actualResult: NotRequired[str]
    assessment: NotRequired[Literal['PASS', 'FAIL', 'INCONCLUSIVE']]
    assessmentAuthority: NotRequired[Literal['deterministic-code', 'manual', 'none']]
    criterion: NotRequired[Criterion]
    description: NotRequired[str]
    displayId: str
    evidenceReferences: NotRequired[list[EvidenceReference]]
    executionRunId: NotRequired[str]
    expectedResult: str
    finding: NotRequired[str]
    inputs: NotRequired[list[str]]
    linkedArchitectureRefs: NotRequired[list[str]]
    linkedComponentIds: NotRequired[list[str]]
    linkedRequirementIds: list[str]
    preconditions: NotRequired[list[str]]
    procedure: NotRequired[list[str]]
    producedOutputIds: NotRequired[list[str]]
    status: Literal[
        'planned', 'ready', 'running', 'passed', 'failed', 'blocked', 'inconclusive'
    ]
    testId: str
    title: str
    verificationMethod: Literal[
        'inspection',
        'simulation',
        'firmware-test',
        'analysis',
        'execution-output',
        'manual',
    ]

class TestPlanV1(TypedDict, closed=True):
    coverageSummary: CoverageSummary
    provenance: NotRequired[Provenance]
    schemaVersion: Literal['1.0.0']
    summary: NotRequired[str]
    testCases: list[TestCase]
    testPlanId: str
    title: NotRequired[str]

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

class TestCase1(TypedDict, closed=True):
    actualResult: NotRequired[str]
    assessment: NotRequired[Literal['PASS', 'FAIL', 'INCONCLUSIVE']]
    assessmentAuthority: NotRequired[Literal['deterministic-code', 'manual', 'none']]
    criterion: NotRequired[Criterion]
    description: NotRequired[str]
    displayId: str
    evidenceReferences: NotRequired[list[EvidenceReference1]]
    executionRunId: NotRequired[str]
    expectedResult: str
    finding: NotRequired[str]
    inputs: NotRequired[list[str]]
    linkedArchitectureRefs: NotRequired[list[str]]
    linkedComponentIds: NotRequired[list[str]]
    linkedRequirementIds: list[str]
    preconditions: NotRequired[list[str]]
    procedure: NotRequired[list[str]]
    producedOutputIds: NotRequired[list[str]]
    status: Literal[
        'planned', 'ready', 'running', 'passed', 'failed', 'blocked', 'inconclusive'
    ]
    testId: str
    title: str
    verificationMethod: Literal[
        'inspection',
        'simulation',
        'firmware-test',
        'analysis',
        'execution-output',
        'manual',
    ]

TestStatus: TypeAlias = Literal[
    'planned', 'ready', 'running', 'passed', 'failed', 'blocked', 'inconclusive'
]

VerificationMethod: TypeAlias = Literal[
    'inspection',
    'simulation',
    'firmware-test',
    'analysis',
    'execution-output',
    'manual',
]
