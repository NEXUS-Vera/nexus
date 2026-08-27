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
        'electrical-architecture',
        'physical-architecture',
        'code-scratch',
        'firmware',
        'analysis',
        'test-plan',
        'risk-register',
    ]
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

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
    openQuestionReferences: list[OpenQuestionReference]
    projectId: str
    projectPhase: Literal['concept', 'prototype-planning']
    schemaVersion: Literal['1.0.0']
    title: str
    updatedAt: str
