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

class Unknown(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class Content(TypedDict, closed=True):
    assumptions: list[Assumption]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]

class OpenQuestionId(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

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

class TargetQuantity(TypedDict, closed=True):
    schemaVersion: Literal['1.0.0']
    unit: str
    value: float

class Requirement(TypedDict, closed=True):
    acceptanceCriteria: NotRequired[list[str]]
    category: Literal[
        'functional',
        'performance',
        'interface',
        'environmental',
        'resource',
        'physical',
        'usability',
        'safety',
        'verification',
        'project-constraint',
    ]
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    dependencyReferences: NotRequired[list[str]]
    displayId: str
    priority: Literal['must', 'should', 'could', 'unclassified']
    rationale: NotRequired[str]
    requirementId: str
    sourceReference: SourceReference
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Content1(TypedDict, closed=True):
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement]

class Edge(TypedDict, closed=True):
    description: str
    edgeId: str
    flowType: Literal['data', 'control', 'power', 'user-input', 'physical-output']
    fromNodeId: str
    toNodeId: str

class Input(TypedDict, closed=True):
    dataType: str
    description: str

class Output(TypedDict, closed=True):
    dataType: str
    description: str

class Node(TypedDict, closed=True):
    functionalType: Literal[
        'input',
        'sensing',
        'processing',
        'control',
        'storage',
        'communication',
        'power',
        'output',
        'actuation',
        'analysis',
        'user-interface',
        'external-system',
    ]
    inputs: NotRequired[list[Input]]
    name: str
    nodeId: str
    outputs: NotRequired[list[Output]]
    responsibilities: list[str]
    satisfiesRequirementIds: list[str]

class RequirementCoverage(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class UnresolvedDecision(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class Content2(TypedDict, closed=True):
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption]
    edges: list[Edge]
    nodes: list[Node]
    requirementCoverage: RequirementCoverage
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]

class Block(TypedDict, closed=True):
    issueId: str

class CompletionCondition(TypedDict, closed=True):
    completionCriteria: str
    conditionType: Literal[
        'validation-issues-cleared', 'unknowns-resolved', 'requirements-confirmed'
    ]

class Prerequisite(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class Content3(TypedDict, closed=True):
    actionId: str
    blocks: list[Block]
    completionCondition: CompletionCondition
    description: str
    owner: Literal['user', 'vera', 'embedded-systems-agent', 'shared']
    prerequisites: list[Prerequisite]
    priority: Literal['critical', 'high', 'medium', 'low']
    rationale: str
    sourceIssueIds: list[str]
    sourceQuestionIds: list[str]
    title: str

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

class Candidate(TypedDict, closed=True):
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

class PerformedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class CompatibilityCheck(TypedDict, closed=True):
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
    evidenceReferences: list[EvidenceReference1]
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

class ComponentRole(TypedDict, closed=True):
    architectureNodeIds: list[str]
    category: Literal[
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
    componentRoleId: str
    description: str
    displayId: str
    name: str
    openQuestionIds: NotRequired[list[str]]
    priority: Literal['low', 'medium', 'high', 'blocking']
    rationale: str
    requiredCapabilities: list[str]
    requirementIds: list[str]
    source: Literal['user-explicit', 'inferred', 'agent-proposed', 'fixture']
    status: Literal[
        'identified',
        'needs-clarification',
        'ready-for-candidates',
        'candidate-review',
        'selection-proposed',
        'selected',
        'blocked',
        'superseded',
    ]

class CoverageSummary(TypedDict, closed=True):
    coveredArchitectureNodes: int
    coveredRequirementIds: list[str]
    rolesAwaitingApproval: int
    rolesWithBlockedSelection: int
    rolesWithoutArchitectureMapping: int
    rolesWithoutCandidates: int
    rolesWithoutRequirementMapping: int
    totalArchitectureNodes: int
    totalRelevantRequirements: int
    uncoveredArchitectureNodeIds: list[str]
    uncoveredRequirementIds: list[str]

class EvidenceReference2(TypedDict, closed=True):
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

class OpenQuestion(TypedDict, closed=True):
    questionId: str
    summary: NotRequired[str]

class TargetValue(TypedDict, closed=True):
    kind: Literal['unknown']

class SelectionConstraint(TypedDict, closed=True):
    componentRoleId: str
    confirmationStatus: Literal['confirmed', 'inferred', 'proposed', 'unknown']
    constraintId: str
    constraintType: Literal[
        'measurement-range',
        'accuracy',
        'resolution',
        'sample-rate',
        'bandwidth',
        'latency',
        'supply-voltage',
        'logic-voltage',
        'active-current',
        'sleep-current',
        'peak-current',
        'interface',
        'bus-bandwidth',
        'operating-temperature',
        'humidity-rating',
        'size',
        'weight',
        'cost',
        'availability',
        'driver-support',
        'platform-support',
        'environment',
        'mechanical-mounting',
    ]
    importance: Literal['required', 'preferred', 'nice-to-have']
    operator: Literal[
        'eq', 'neq', 'gte', 'lte', 'gt', 'lt', 'in', 'contains', 'unknown'
    ]
    rationale: str
    sourceArchitectureNodeIds: list[str]
    sourceRequirementIds: list[str]
    targetValue: float | str | bool | TargetValue
    unit: str | None

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

class SelectionDecision(TypedDict, closed=True):
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

class ValidationSummary(TypedDict, closed=True):
    blockingIssueCount: int
    issueCount: int
    status: Literal['ok', 'warnings', 'blocking']
    warningCount: int

class Content4(TypedDict, closed=True):
    assumptions: list[str]
    candidates: list[Candidate]
    compatibilityChecks: list[CompatibilityCheck]
    componentPlanId: NotRequired[str]
    componentRoles: list[ComponentRole]
    coverageSummary: CoverageSummary
    evidenceReferences: list[EvidenceReference2]
    maturity: Literal[
        'roles-defined',
        'candidates-proposed',
        'candidates-grounded',
        'compatibility-checked',
        'selection-proposed',
        'selection-approved',
        'validated',
    ]
    openQuestions: list[OpenQuestion]
    selectionConstraints: list[SelectionConstraint]
    selectionDecisions: list[SelectionDecision]
    summary: str
    validationSummary: ValidationSummary

class CreatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ArtifactEnvelopeV1(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
    ]
    artifactVersion: int
    content: Content | Content1 | Content2 | Content3 | Content4
    contentSchemaVersion: Literal['1.0.0']
    createdAt: str
    createdBy: CreatedBy
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    lifecycleStatus: Literal[
        'drafted', 'ready', 'affected', 'stale', 'blocked', 'superseded', 'archived'
    ]
    projectId: str
    schemaVersion: Literal['1.0.0']
    sourceTurnId: str
    supersedesArtifactId: NotRequired[str]
    supersedesArtifactVersion: NotRequired[int]
    updatedAt: str
    workflowRunId: str
