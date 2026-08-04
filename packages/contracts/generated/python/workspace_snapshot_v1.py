# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

class Content(TypedDict, closed=True):
    kind: Literal['structured']
    structuredContent: dict[str, Any]

class Content1(TypedDict, closed=True):
    contentDigest: str
    kind: Literal['storage-reference']
    storageKind: Literal['postgres-jsonb', 'object-store', 'file-store']
    uri: str

class CreatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class WorkspaceSnapshotV1(TypedDict, closed=True):
    artifactId: str
    baseArtifactVersion: int
    baseProjectStateVersion: int
    content: Content | Content1
    contentDigest: str
    createdAt: str
    createdBy: CreatedBy
    projectId: str
    reason: str
    schemaVersion: Literal['1.0.0']
    snapshotId: str
    snapshotVersion: int
    workspaceId: str
