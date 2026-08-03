# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ArtifactRevision(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal[
        'project-brief', 'requirement-set', 'functional-architecture', 'next-action'
    ]
    artifactVersion: int
    createdAt: str
    lifecycleStatus: Literal[
        'drafted', 'ready', 'affected', 'stale', 'blocked', 'superseded', 'archived'
    ]
    sourceTurnId: str
    supersedesArtifactId: NotRequired[str]
    supersedesArtifactVersion: NotRequired[int]

class Turn(TypedDict, closed=True):
    rawUserMessage: str
    timestamp: str
    turnId: str

class VeraResponse(TypedDict, closed=True):
    timestamp: str
    turnId: str
    userFacingMessage: str

class WorkflowRun(TypedDict, closed=True):
    completedAt: NotRequired[str]
    startedAt: str
    status: Literal[
        'pending', 'running', 'completed', 'completed-with-warnings', 'failed'
    ]
    turnId: str
    workflowRunId: str
    workflowType: Literal[
        'embedded-project-initialization', 'embedded-project-modification'
    ]

class ProjectHistoryV1(TypedDict, closed=True):
    artifactRevisions: list[ArtifactRevision]
    projectId: str
    schemaVersion: Literal['1.0.0']
    turns: list[Turn]
    veraResponses: list[VeraResponse]
    workflowRuns: list[WorkflowRun]
