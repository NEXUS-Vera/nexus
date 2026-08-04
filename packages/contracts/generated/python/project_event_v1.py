# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Actor(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class Payload(TypedDict, closed=True):
    artifactType: NotRequired[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
        ]
    ]
    artifactVersion: NotRequired[int]
    capability: NotRequired[
        Literal[
            'structured-validation',
            'fake-execution',
            'file-workspace',
            'embedded-build',
            'python-kernel',
            'circuit-simulation',
            'architecture-export',
        ]
    ]
    decisionId: NotRequired[str]
    evidenceId: NotRequired[str]
    executionRunId: NotRequired[str]
    outputId: NotRequired[str]
    proposalId: NotRequired[str]
    questionId: NotRequired[str]
    reason: NotRequired[str]
    snapshotId: NotRequired[str]
    status: NotRequired[str]
    summary: NotRequired[str]
    workspaceId: NotRequired[str]

class Subject(TypedDict, closed=True):
    subjectId: str
    subjectType: Literal[
        'workspace',
        'artifact',
        'proposal',
        'execution',
        'output',
        'evidence',
        'question',
        'decision',
        'snapshot',
    ]

class ProjectEventV1(TypedDict, closed=True):
    actor: Actor
    causationId: NotRequired[str]
    correlationId: NotRequired[str]
    eventId: str
    eventType: Literal[
        'workspace.created',
        'workspace.snapshot-created',
        'artifact.revision-proposed',
        'artifact.revision-accepted',
        'artifact.revision-rejected',
        'artifact.marked-affected',
        'artifact.superseded',
        'execution.queued',
        'execution.started',
        'execution.completed',
        'execution.failed',
        'output.produced',
        'evidence.attached',
        'evidence.contradicted',
        'evidence.superseded',
        'question.opened',
        'question.resolved',
        'decision.accepted',
        'decision.reversed',
    ]
    occurredAt: str
    payload: Payload
    projectId: str
    schemaVersion: Literal['1.0.0']
    subject: Subject
