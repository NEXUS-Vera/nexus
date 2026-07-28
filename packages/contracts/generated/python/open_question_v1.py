# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class RequestedFrom(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference(TypedDict, closed=True):
    artifactId: NotRequired[str]
    kind: Literal['artifact', 'requirement']
    requirementId: NotRequired[str]

class OpenQuestionV1(TypedDict, closed=True):
    blocks: list[str]
    createdAt: str
    projectId: str
    question: str
    questionId: str
    reason: str
    requestedFrom: RequestedFrom
    schemaVersion: Literal['1.0.0']
    sourceReferences: list[SourceReference]
    status: Literal['open', 'answered', 'resolved', 'dismissed']
    updatedAt: str
