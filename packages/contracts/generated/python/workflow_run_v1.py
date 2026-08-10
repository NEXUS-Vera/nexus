# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

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
        'electrical-architecture',
        'physical-architecture',
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

class WorkflowRunV1(TypedDict, closed=True):
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
    workflowType: Literal[
        'embedded-project-initialization', 'embedded-project-modification'
    ]

class ArtifactReference(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'electrical-architecture',
        'physical-architecture',
    ]
    artifactVersion: int
    contentSchemaVersion: Literal['1.0.0']

class ValidationIssueReference(TypedDict, closed=True):
    issueId: str
