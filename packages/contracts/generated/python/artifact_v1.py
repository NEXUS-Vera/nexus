# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias

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

class CreatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ArtifactV11(TypedDict, closed=True):
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

class ArtifactV12(TypedDict, closed=True):
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

class ArtifactV13(TypedDict, closed=True):
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

class ArtifactV14(TypedDict, closed=True):
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

ArtifactV1: TypeAlias = ArtifactV11 | ArtifactV12 | ArtifactV13 | ArtifactV14
