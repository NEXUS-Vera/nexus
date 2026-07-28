# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Assumption(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low', 'high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
    ]
    sourceType: Literal[
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
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
    projectStage: Literal[
        'concept', 'prototype-planning', 'concept', 'prototype-planning'
    ]
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]

class Assumption1(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str

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
    assumptions: list[Assumption1]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement]

class Assumption2(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low', 'high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
    ]
    sourceType: Literal[
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
    ]
    statement: str

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
    assumptions: list[Assumption2]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]
    architectureId: str
    architectureMaturity: Literal['functional']
    edges: list[Edge]
    nodes: list[Node]
    requirementCoverage: RequirementCoverage
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]

class Assumption3(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str

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
    assumptions: list[Assumption3]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]
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
    content: Content | Content1 | Content2 | Content3
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

class Requirement1(TypedDict, closed=True):
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
    sourceReference: SourceReference1
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Content4(TypedDict, closed=True):
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement1]
    assumptions: list[Assumption3]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]

class Attribution2(TypedDict, closed=True):
    actorId: str
    actorType: Literal[
        'user',
        'vera',
        'embedded-systems-agent',
        'shared',
        'system',
        'user',
        'vera',
        'embedded-systems-agent',
        'shared',
        'system',
    ]
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference2(TypedDict, closed=True):
    attribution: NotRequired[Attribution2]
    evidenceId: str
    evidenceStrength: Literal[
        'direct',
        'supporting',
        'inferred',
        'contradicting',
        'direct',
        'supporting',
        'inferred',
        'contradicting',
    ]
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
        'user-turn',
        'project-policy',
        'document',
        'external-source',
        'calculation',
        'test-result',
        'agent-inference',
    ]
    supportedClaim: NotRequired[str]

class Requirement2(TypedDict, closed=True):
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
    confidence: Literal['high', 'medium', 'low', 'high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
    ]
    dependencyReferences: NotRequired[list[str]]
    displayId: str
    priority: Literal[
        'must',
        'should',
        'could',
        'unclassified',
        'must',
        'should',
        'could',
        'unclassified',
    ]
    rationale: NotRequired[str]
    requirementId: str
    sourceReference: SourceReference2
    sourceType: Literal[
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Content5(TypedDict, closed=True):
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement2]

class Attribution3(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference3(TypedDict, closed=True):
    attribution: NotRequired[Attribution3]
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

class Requirement3(TypedDict, closed=True):
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
    sourceReference: SourceReference3
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Node1(TypedDict, closed=True):
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

class RequirementCoverage1(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class Content6(TypedDict, closed=True):
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement3]
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption3]
    edges: list[Edge]
    nodes: list[Node1]
    requirementCoverage: RequirementCoverage1
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]

class SourceReference4(TypedDict, closed=True):
    attribution: NotRequired[Attribution3]
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

class Requirement4(TypedDict, closed=True):
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
    sourceReference: SourceReference4
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Content7(TypedDict, closed=True):
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement4]
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
    content: Content4 | Content5 | Content6 | Content7
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

class Assumption6(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low', 'high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
    ]
    sourceType: Literal[
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
    ]
    statement: str

class Node2(TypedDict, closed=True):
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

class RequirementCoverage2(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class Content8(TypedDict, closed=True):
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption6]
    edges: list[Edge]
    nodes: list[Node2]
    requirementCoverage: RequirementCoverage2
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]

class Assumption7(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str

class Node3(TypedDict, closed=True):
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

class RequirementCoverage3(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class SourceReference5(TypedDict, closed=True):
    attribution: NotRequired[Attribution3]
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

class Requirement5(TypedDict, closed=True):
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
    sourceReference: SourceReference5
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Content9(TypedDict, closed=True):
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption7]
    edges: list[Edge]
    nodes: list[Node3]
    requirementCoverage: RequirementCoverage3
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement5]

class Assumption8(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low', 'high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
        'confirmed',
        'proposed',
        'needs-confirmation',
        'rejected',
    ]
    sourceType: Literal[
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
        'user-explicit',
        'user-implied',
        'system-inferred',
        'project-policy',
    ]
    statement: str

class Edge4(TypedDict, closed=True):
    description: str
    edgeId: str
    flowType: Literal[
        'data',
        'control',
        'power',
        'user-input',
        'physical-output',
        'data',
        'control',
        'power',
        'user-input',
        'physical-output',
    ]
    fromNodeId: str
    toNodeId: str

class Node4(TypedDict, closed=True):
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

class RequirementCoverage4(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class Content10(TypedDict, closed=True):
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption8]
    edges: list[Edge4]
    nodes: list[Node4]
    requirementCoverage: RequirementCoverage4
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]

class Assumption9(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str

class Edge5(TypedDict, closed=True):
    description: str
    edgeId: str
    flowType: Literal['data', 'control', 'power', 'user-input', 'physical-output']
    fromNodeId: str
    toNodeId: str

class Node5(TypedDict, closed=True):
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

class RequirementCoverage5(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class Content11(TypedDict, closed=True):
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption9]
    edges: list[Edge5]
    nodes: list[Node5]
    requirementCoverage: RequirementCoverage5
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]
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
    content: Content8 | Content9 | Content10 | Content11
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

class Content12(TypedDict, closed=True):
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
    assumptions: list[Assumption9]
    goal: str
    intendedContext: str
    outOfScope: list[str]
    problemStatement: str
    projectStage: Literal['concept', 'prototype-planning']
    scope: list[str]
    successCriteria: list[str]
    unknowns: list[Unknown]

class SourceReference6(TypedDict, closed=True):
    attribution: NotRequired[Attribution3]
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

class Requirement6(TypedDict, closed=True):
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
    sourceReference: SourceReference6
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str
    targetQuantity: NotRequired[TargetQuantity]
    verificationMethod: str

class Content13(TypedDict, closed=True):
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
    missingDimensions: NotRequired[list[str]]
    openQuestionIds: NotRequired[list[OpenQuestionId]]
    requirementSummary: str
    requirements: list[Requirement6]

class Node6(TypedDict, closed=True):
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

class RequirementCoverage6(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class Content14(TypedDict, closed=True):
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
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption9]
    edges: list[Edge5]
    nodes: list[Node6]
    requirementCoverage: RequirementCoverage6
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]

class CompletionCondition6(TypedDict, closed=True):
    completionCriteria: str
    conditionType: Literal[
        'validation-issues-cleared',
        'unknowns-resolved',
        'requirements-confirmed',
        'validation-issues-cleared',
        'unknowns-resolved',
        'requirements-confirmed',
    ]

class Content15(TypedDict, closed=True):
    actionId: str
    blocks: list[Block]
    completionCondition: CompletionCondition6
    description: str
    owner: Literal[
        'user',
        'vera',
        'embedded-systems-agent',
        'shared',
        'user',
        'vera',
        'embedded-systems-agent',
        'shared',
    ]
    prerequisites: list[Prerequisite]
    priority: Literal[
        'critical', 'high', 'medium', 'low', 'critical', 'high', 'medium', 'low'
    ]
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
    content: Content12 | Content13 | Content14 | Content15
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

class Artifacts4(TypedDict):
    pass

class RequestedFrom(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference7(TypedDict, closed=True):
    artifactId: NotRequired[str]
    kind: Literal['artifact', 'requirement']
    requirementId: NotRequired[str]

class OpenQuestion(TypedDict, closed=True):
    blocks: list[str]
    createdAt: str
    projectId: str
    question: str
    questionId: str
    reason: str
    requestedFrom: RequestedFrom
    schemaVersion: Literal['1.0.0']
    sourceReferences: list[SourceReference7]
    status: Literal['open', 'answered', 'resolved', 'dismissed']
    updatedAt: str

class BlockerOrValidationIssueReference(TypedDict, closed=True):
    issueId: str

class CurrentArtifactReference(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal[
        'project-brief', 'requirement-set', 'functional-architecture', 'next-action'
    ]
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

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
    projectOperation: Literal['create-project', 'none']
    reasons: list[str]
    routeId: str
    routeType: Literal['project-initialization', 'unsupported']
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
    attribution: NotRequired[Attribution3]
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
        'project-brief', 'requirement-set', 'functional-architecture', 'next-action'
    ]
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class NextActionArtifactReference(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal[
        'project-brief', 'requirement-set', 'functional-architecture', 'next-action'
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
        'project-brief', 'requirement-set', 'functional-architecture', 'next-action'
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

class Warning(TypedDict, closed=True):
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
    warnings: list[Warning]
    workflowRunId: str
    workflowType: Literal['embedded-project-initialization']

class ProjectInitializationResultV1(TypedDict, closed=True):
    artifacts: list[Artifacts | Artifacts1 | Artifacts2 | Artifacts3] | Artifacts4
    openQuestions: list[OpenQuestion]
    project: Project
    schemaVersion: Literal['1.0.0']
    turnRoute: TurnRoute
    userTurn: UserTurn
    validationIssues: list[ValidationIssue]
    veraResponse: VeraResponse
    workflowRun: WorkflowRun
