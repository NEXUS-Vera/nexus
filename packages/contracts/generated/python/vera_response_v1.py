# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

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

class OpenQuestionReference(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class ProjectStateSummary(TypedDict, closed=True):
    autonomyMode: Literal['collaborate', 'delegate']
    openQuestionCount: int
    projectPhase: Literal['concept', 'prototype-planning']
    validationIssueCount: int

class WarningIssueReference(TypedDict, closed=True):
    issueId: str

class VeraResponseV1(TypedDict, closed=True):
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
