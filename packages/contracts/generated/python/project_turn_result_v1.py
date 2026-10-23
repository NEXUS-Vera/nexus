# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

class ChangeIntent(TypedDict, closed=True):
    ambiguities: list[str]
    confidence: Literal['low', 'medium', 'high']
    operation: Literal[
        'clarify-requirement',
        'add-requirement',
        'change-requirement',
        'remove-proposed-requirement',
        'answer-open-question',
        'change-project-scope',
        'reject-component-candidate',
        'approve-component-selection',
        'change-component-preference',
        'add-component-constraint',
        'change-interface-constraint',
        'request-component-alternatives',
        'answer-component-open-question',
    ]
    requestedChange: str
    requiresUserConfirmation: bool
    schemaVersion: Literal['1.0.0']
    sourceTurnId: str
    targetArtifactType: (
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'component-plan',
            'next-action',
        ]
        | None
    )
    targetQuestionId: NotRequired[str]
    targetRequirementId: NotRequired[str]

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

class CreatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class Artifacts(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['project-brief']
    artifactVersion: int
    content: Content
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

class Artifacts1(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['requirement-set']
    artifactVersion: int
    content: Content1
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

class Artifacts2(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['functional-architecture']
    artifactVersion: int
    content: Content2
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

class Artifacts3(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['next-action']
    artifactVersion: int
    content: Content3
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

class Artifacts4(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['component-plan']
    artifactVersion: int
    content: Content4
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

class Provenance(TypedDict, closed=True):
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

class CoverageSummary1(TypedDict, closed=True):
    approvedImplementationCount: int
    coveredFunctionalNodes: int
    preferredImplementationCount: int
    totalFunctionalNodes: int
    uncoveredFunctionalNodeIds: list[str]
    unresolvedConnectionCount: int
    unresolvedImplementationCount: int

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

class Provenance1(TypedDict, closed=True):
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

class Node1(TypedDict, closed=True):
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

class SourceReference3(TypedDict, closed=True):
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
    sourceReference: NotRequired[SourceReference3 | str]
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

class Warning(TypedDict, closed=True):
    code: str
    message: str
    relatedNodeIds: NotRequired[list[str]]
    severity: Literal['info', 'warning', 'blocking']

class Content5(TypedDict, closed=True):
    architectureId: str
    assumptions: list[Assumption]
    connections: list[Connection]
    coverageSummary: CoverageSummary1
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    maturity: Literal['provisional', 'drafted', 'reviewed', 'approved']
    nodes: list[Node1]
    powerDomains: list[PowerDomain]
    selectionBasisSummary: str
    summary: str
    unresolvedDecisions: list[UnresolvedDecision]
    warnings: list[Warning]

class Artifacts5(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['electrical-architecture']
    artifactVersion: int
    content: Content5
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

class CoverageSummary2(TypedDict, closed=True):
    coveredElectricalNodes: int
    provisionalRelationshipCount: int
    totalElectricalNodes: int
    uncoveredElectricalNodeIds: list[str]
    unresolvedPlacementCount: int

class SourceReference4(TypedDict, closed=True):
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

class Provenance3(TypedDict, closed=True):
    derivedFromIds: NotRequired[list[str]]
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceReference: NotRequired[SourceReference4 | str]
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

class Node2(TypedDict, closed=True):
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
    provenance: NotRequired[Provenance3]
    qualitativePlacement: NotRequired[str]
    zoneId: NotRequired[str]

class SourceReference5(TypedDict, closed=True):
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

class Provenance4(TypedDict, closed=True):
    derivedFromIds: NotRequired[list[str]]
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceReference: NotRequired[SourceReference5 | str]
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
    provenance: NotRequired[Provenance4]
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

class Content6(TypedDict, closed=True):
    architectureId: str
    assumptions: list[Assumption]
    coverageSummary: CoverageSummary2
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    maturity: Literal['provisional', 'drafted', 'reviewed', 'approved']
    nodes: list[Node2]
    relationships: list[Relationship]
    summary: str
    unresolvedDecisions: list[UnresolvedDecision]
    warnings: list[Warning]
    zones: list[Zone]

class Artifacts6(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['physical-architecture']
    artifactVersion: int
    content: Content6
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

class CoverageSummary3(TypedDict, closed=True):
    blockedRequirements: int
    coveredRequirements: int
    failedRequirements: int
    recheckRequiredRequirements: NotRequired[int]
    staleRequirements: NotRequired[int]
    totalRequirements: int
    uncoveredRequirements: int
    unverifiedRequirements: int
    verifiedRequirements: int

class Provenance5(TypedDict, closed=True):
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

class EvidenceReference3(TypedDict, closed=True):
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
    evidenceReferences: NotRequired[list[EvidenceReference3]]
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

class Content7(TypedDict, closed=True):
    coverageSummary: CoverageSummary3
    provenance: NotRequired[Provenance5]
    schemaVersion: Literal['1.0.0']
    summary: NotRequired[str]
    testCases: list[TestCase]
    testPlanId: str
    title: NotRequired[str]

class Artifacts7(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['test-plan']
    artifactVersion: int
    content: Content7
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

class EvidenceReference4(TypedDict, closed=True):
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
    evidenceReferences: NotRequired[list[EvidenceReference4]]
    likelihood: Literal['rare', 'unlikely', 'possible', 'likely']
    linkedArchitectureRefs: NotRequired[list[str]]
    linkedComponentIds: NotRequired[list[str]]
    linkedRequirementIds: NotRequired[list[str]]
    linkedTestIds: NotRequired[list[str]]
    mitigation: str
    mitigationVerificationStatus: NotRequired[
        Literal['proposed', 'evidence-present', 'verified']
    ]
    mitigationVerifiedByTests: NotRequired[list[str]]
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

class Content8(TypedDict, closed=True):
    provenance: NotRequired[Provenance5]
    riskRegisterId: str
    risks: list[Risk]
    schemaVersion: Literal['1.0.0']
    summary: Summary
    title: NotRequired[str]

class Artifacts8(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['risk-register']
    artifactVersion: int
    content: Content8
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

class Component(TypedDict, closed=True):
    candidateId: str
    componentRoleId: str

class I2c(TypedDict, closed=True):
    connectionId: str
    sclPin: Literal[21, 22, 25, 26, 27, 32, 33]
    sdaPin: Literal[21, 22, 25, 26, 27, 32, 33]

class Configuration(TypedDict, closed=True):
    analysisProfileId: Literal['python-analysis-v1']
    buildProfileId: Literal['platformio-arduino-esp32-v1']
    components: list[Component]
    i2c: I2c

class Assumption4(TypedDict, closed=True):
    artifactId: str
    entityId: str

class Component1(TypedDict, closed=True):
    artifactId: str
    entityId: str

class Interface1(TypedDict, closed=True):
    artifactId: str
    entityId: str

class Requirement1(TypedDict, closed=True):
    artifactId: str
    entityId: str

class SourceArtifact(TypedDict, closed=True):
    artifactId: str
    artifactVersion: int

class Step(TypedDict, closed=True):
    dependsOn: list[str]
    objectiveIds: list[str]
    requiresApproval: Literal[True]
    stepId: str
    title: str
    workspaceKeys: list[str]

class VerificationObjective(TypedDict, closed=True):
    acceptanceCriteria: list[str]
    method: str
    objectiveId: str
    requirementId: str
    workspaceKey: str

class Workspace(TypedDict, closed=True):
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
    availability: Literal['artifact-available', 'planned']
    workspaceKey: str

class Plan(TypedDict, closed=True):
    assumptions: list[Assumption4]
    basisProjectStateVersion: int
    components: list[Component1]
    interfaces: list[Interface1]
    openDecisionIds: list[str]
    requirements: list[Requirement1]
    schemaVersion: Literal['1.0.0']
    sourceArtifacts: list[SourceArtifact]
    status: Literal['proposed']
    steps: list[Step]
    verificationObjectives: list[VerificationObjective]
    workspaces: list[Workspace]

class Content9(TypedDict, closed=True):
    configuration: Configuration
    plan: Plan

class Artifacts9(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    artifactId: str
    artifactType: Literal['execution-plan']
    artifactVersion: int
    content: Content9
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

class Artifacts10(TypedDict):
    pass

class Dependency1(TypedDict, closed=True):
    createdAt: str
    dependencyId: str
    dependencyKind: Literal[
        'derives-from', 'constrains', 'covers', 'blocks', 'invalidates'
    ]
    projectId: str
    reason: str
    schemaVersion: Literal['1.0.0']
    sourceArtifactId: NotRequired[str]
    sourceArtifactType: Literal[
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
    targetArtifactId: NotRequired[str]
    targetArtifactType: Literal[
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

class RequestedFrom(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference6(TypedDict, closed=True):
    artifactId: NotRequired[str]
    kind: Literal['artifact', 'requirement']
    requirementId: NotRequired[str]

class OpenQuestion1(TypedDict, closed=True):
    blocks: list[str]
    createdAt: str
    projectId: str
    question: str
    questionId: str
    reason: str
    requestedFrom: RequestedFrom
    schemaVersion: Literal['1.0.0']
    sourceReferences: list[SourceReference6]
    status: Literal['open', 'answered', 'resolved', 'dismissed']
    updatedAt: str

class BlockerOrValidationIssueReference(TypedDict, closed=True):
    issueId: str

class CurrentArtifactReference(TypedDict, closed=True):
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
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class ExecutionPlan(TypedDict, closed=True):
    assumptions: list[Assumption4]
    basisProjectStateVersion: int
    components: list[Component1]
    interfaces: list[Interface1]
    openDecisionIds: list[str]
    requirements: list[Requirement1]
    schemaVersion: Literal['1.0.0']
    sourceArtifacts: list[SourceArtifact]
    status: Literal['proposed']
    steps: list[Step]
    verificationObjectives: list[VerificationObjective]
    workspaces: list[Workspace]

class OpenQuestionReference(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class Project(TypedDict, closed=True):
    autonomyMode: Literal['collaborate', 'delegate']
    blockerOrValidationIssueReferences: list[BlockerOrValidationIssueReference]
    createdAt: str
    currentArtifactReferences: list[CurrentArtifactReference]
    currentStateVersion: int
    domain: Literal['embedded-products']
    executionPlan: NotRequired[ExecutionPlan]
    openQuestionReferences: list[OpenQuestionReference]
    projectId: str
    projectPhase: Literal['concept', 'prototype-planning']
    schemaVersion: Literal['1.0.0']
    title: str
    updatedAt: str

class TurnRoute(TypedDict, closed=True):
    autonomyMode: Literal['collaborate', 'delegate']
    chairmanRequiredEventually: bool
    complexity: Literal['low', 'medium', 'high', 'unknown']
    domain: Literal['embedded-products']
    projectOperation: Literal[
        'create-project',
        'clarify-requirement',
        'add-requirement',
        'change-requirement',
        'remove-proposed-requirement',
        'answer-open-question',
        'change-project-scope',
        'reject-component-candidate',
        'approve-component-selection',
        'change-component-preference',
        'add-component-constraint',
        'change-interface-constraint',
        'request-component-alternatives',
        'answer-component-open-question',
        'none',
    ]
    reasons: list[str]
    routeId: str
    routeType: Literal['project-initialization', 'project-modification', 'unsupported']
    schemaVersion: Literal['1.0.0']
    supported: bool
    turnId: str
    unsupportedReason: NotRequired[str]

class Actor(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class AttachmentReference(TypedDict, closed=True):
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

class UserTurn(TypedDict, closed=True):
    actor: Actor
    attachmentReferences: NotRequired[list[AttachmentReference]]
    parentTurnId: NotRequired[str]
    projectId: str
    rawUserMessage: str
    schemaVersion: Literal['1.0.0']
    timestamp: str
    turnId: str

class ValidationIssue(TypedDict, closed=True):
    artifactId: NotRequired[str]
    blocking: bool
    code: str
    createdAt: str
    issueId: str
    itemId: NotRequired[str]
    message: str
    projectId: str
    resolutionStatus: Literal['open', 'resolved']
    resolutionType: Literal[
        'user-input',
        'artifact-regeneration',
        'manual-review',
        'automatic-fix',
        'not-applicable',
    ]
    resolvedAt: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    severity: Literal['critical', 'high', 'medium', 'low', 'info']
    suggestedResolution: NotRequired[str]

class BlockerIssueReference(TypedDict, closed=True):
    issueId: str

class CreatedArtifactReference(TypedDict, closed=True):
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
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class NextActionArtifactReference(TypedDict, closed=True):
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
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class ProjectStateSummary(TypedDict, closed=True):
    autonomyMode: Literal['collaborate', 'delegate']
    openQuestionCount: int
    projectPhase: Literal['concept', 'prototype-planning']
    validationIssueCount: int

class WarningIssueReference(TypedDict, closed=True):
    issueId: str

class VeraResponse(TypedDict, closed=True):
    blockerIssueReferences: list[BlockerIssueReference]
    completionStatus: Literal['completed', 'completed-with-warnings', 'failed']
    createdArtifactReferences: list[CreatedArtifactReference]
    nextActionArtifactReference: NextActionArtifactReference
    openQuestionReferences: list[OpenQuestionReference]
    projectId: str
    projectStateSummary: ProjectStateSummary
    schemaVersion: Literal['1.0.0']
    turnId: str
    userFacingMessage: str
    warningIssueReferences: list[WarningIssueReference]

class ErrorReference(TypedDict, closed=True):
    issueId: str

class OutputArtifactReference(TypedDict, closed=True):
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
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class StepRecord(TypedDict, closed=True):
    attempt: int
    completedAt: NotRequired[str]
    errorReference: NotRequired[ErrorReference]
    outputArtifactReferences: NotRequired[list[OutputArtifactReference]]
    startedAt: NotRequired[str]
    status: Literal['pending', 'running', 'completed', 'failed']
    stepId: str
    stepType: str

class Warning2(TypedDict, closed=True):
    issueId: str

class WorkflowRun(TypedDict, closed=True):
    completionTime: NotRequired[str]
    errorReferences: list[ErrorReference]
    projectId: str
    runStatus: Literal[
        'pending', 'running', 'completed', 'completed-with-warnings', 'failed'
    ]
    schemaVersion: Literal['1.0.0']
    startTime: str
    stepRecords: list[StepRecord]
    turnId: str
    warnings: list[Warning2]
    workflowRunId: str
    workflowType: Literal[
        'embedded-project-initialization', 'embedded-project-modification'
    ]

class CurrentState(TypedDict, closed=True):
    artifacts: (
        list[
            Artifacts
            | Artifacts1
            | Artifacts2
            | Artifacts3
            | Artifacts4
            | Artifacts5
            | Artifacts6
            | Artifacts7
            | Artifacts8
            | Artifacts9
        ]
        | Artifacts10
    )
    dependencies: NotRequired[list[Dependency1]]
    openQuestions: list[OpenQuestion1]
    previousTurnIds: NotRequired[list[str]]
    project: Project
    schemaVersion: Literal['1.0.0']
    turnRoute: TurnRoute
    userTurn: UserTurn
    validationIssues: list[ValidationIssue]
    veraResponse: VeraResponse
    workflowRun: WorkflowRun

class ReasonByArtifactItem(TypedDict, closed=True):
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
    reason: str

class ImpactAnalysis(TypedDict, closed=True):
    affected: list[
        Literal[
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
    ]
    changed: list[
        Literal[
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
    ]
    reasonByArtifact: list[ReasonByArtifactItem]
    regenerate: list[
        Literal[
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
    ]
    schemaVersion: Literal['1.0.0']
    stale: list[
        Literal[
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
    ]
    unchanged: list[
        Literal[
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
    ]

class ProjectTurnResultV1(TypedDict, closed=True):
    changeIntent: ChangeIntent
    changedArtifactTypes: list[
        Literal[
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
    ]
    currentState: CurrentState
    impactAnalysis: ImpactAnalysis
    regeneratedArtifactTypes: list[
        Literal[
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
    ]
    schemaVersion: Literal['1.0.0']

ArtifactType: TypeAlias = Literal[
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

ArtifactTypeList: TypeAlias = list[
    Literal[
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
]
