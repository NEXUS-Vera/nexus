# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

class CoverageSummary(TypedDict, closed=True):
    blockedRequirements: int
    coveredRequirements: int
    failedRequirements: int
    recheckRequiredRequirements: NotRequired[int]
    staleRequirements: NotRequired[int]
    totalRequirements: int
    uncoveredRequirements: int
    unverifiedRequirements: int
    verifiedRequirements: int

class Provenance(TypedDict, closed=True):
    generatedBy: NotRequired[Literal['fixture', 'llm', 'user', 'derived']]
    notes: NotRequired[str]

class Reason(TypedDict, closed=True):
    eventId: str
    fromVersion: int
    path: list[str]
    reason: str
    toVersion: int
    triggerArtifactId: str
    triggerArtifactType: str

class Applicability(TypedDict, closed=True):
    reasons: list[Reason]
    state: Literal['CURRENT', 'STALE', 'RECHECK_REQUIRED']

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

class Dependency(TypedDict, closed=True):
    artifactId: str
    artifactType: str
    artifactVersion: int
    contentHash: str
    entryId: NotRequired[str]
    snapshotId: NotRequired[str]

class VerificationBasis(TypedDict, closed=True):
    dependencies: list[Dependency]
    executionRunId: str
    inputSnapshotId: str

class TestCase(TypedDict, closed=True):
    actualResult: NotRequired[str]
    applicability: NotRequired[Applicability]
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
    verificationBasis: NotRequired[VerificationBasis]
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

class Applicability1(TypedDict, closed=True):
    reasons: list[Reason]
    state: Literal['CURRENT', 'STALE', 'RECHECK_REQUIRED']

class Applicability2(TypedDict, closed=True):
    reasons: list[Reason]
    state: Literal['CURRENT', 'STALE', 'RECHECK_REQUIRED']

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

class VerificationBasis1(TypedDict, closed=True):
    dependencies: list[Dependency]
    executionRunId: str
    inputSnapshotId: str

class TestCase1(TypedDict, closed=True):
    actualResult: NotRequired[str]
    applicability: NotRequired[Applicability2]
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
    verificationBasis: NotRequired[VerificationBasis1]
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

class VerificationBasis2(TypedDict, closed=True):
    dependencies: list[Dependency]
    executionRunId: str
    inputSnapshotId: str

VerificationMethod: TypeAlias = Literal[
    'inspection',
    'simulation',
    'firmware-test',
    'analysis',
    'execution-output',
    'manual',
]
