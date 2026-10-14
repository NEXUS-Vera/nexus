# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

class EditLease(TypedDict, closed=True):
    acquiredAt: str
    baseDraftVersion: int
    expiresAt: str
    leaseId: str
    leaseToken: str
    ownerActorId: str
    ownerActorType: Literal[
        'user', 'vera', 'embedded-systems-agent', 'shared', 'system'
    ]
    ownerDisplayName: NotRequired[str]

class UpdatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class WorkspaceDraftStateV1(TypedDict, closed=True):
    baseArtifactVersion: int
    baseProjectStateVersion: int
    content: dict[str, Any]
    createdAt: str
    draftVersion: int
    editLease: NotRequired[EditLease]
    schemaVersion: Literal['1.0.0']
    updatedAt: str
    updatedBy: UpdatedBy
    validationState: Literal['unvalidated', 'valid', 'invalid', 'stale']
    workspaceId: str
