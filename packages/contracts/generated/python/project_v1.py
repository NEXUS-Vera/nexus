# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

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
    ]
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class Assumption(TypedDict, closed=True):
    artifactId: str
    entityId: str

class Component(TypedDict, closed=True):
    artifactId: str
    entityId: str

class Interface(TypedDict, closed=True):
    artifactId: str
    entityId: str

class Requirement(TypedDict, closed=True):
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
    ]
    availability: Literal['artifact-available', 'planned']
    workspaceKey: str

class ExecutionPlan(TypedDict, closed=True):
    assumptions: list[Assumption]
    basisProjectStateVersion: int
    components: list[Component]
    interfaces: list[Interface]
    openDecisionIds: list[str]
    requirements: list[Requirement]
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

class ProjectV1(TypedDict, closed=True):
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
