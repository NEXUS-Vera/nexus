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
    artifactId: NotRequired[str]
    artifactType: NotRequired[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'electrical-architecture',
            'physical-architecture',
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
    evidenceStatus: NotRequired[
        Literal[
            'unverified',
            'inferred',
            'partially-grounded',
            'grounded',
            'calculated',
            'tested',
        ]
    ]
    executionRunId: NotRequired[str]
    outputId: NotRequired[str]
    outputType: NotRequired[
        Literal[
            'validation-report',
            'log',
            'structured-result',
            'file-reference',
            'plot-reference',
            'binary-reference',
            'test-report',
        ]
    ]
    proposalId: NotRequired[str]
    questionId: NotRequired[str]
    reason: NotRequired[str]
    resultingArtifactId: NotRequired[str]
    resultingArtifactVersion: NotRequired[int]
    snapshotId: NotRequired[str]
    status: NotRequired[str]
    summary: NotRequired[str]
    supersededBy: NotRequired[str]
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
        'component-plan.created',
        'component-role.identified',
        'component-candidate.proposed',
        'component-candidate.rejected',
        'component-selection.proposed',
        'component-selection.approved',
        'component-selection.rejected',
        'compatibility-check.recorded',
        'component-plan.revised',
        'component-plan.marked-stale',
    ]
    occurredAt: str
    payload: Payload
    projectId: str
    schemaVersion: Literal['1.0.0']
    subject: Subject
