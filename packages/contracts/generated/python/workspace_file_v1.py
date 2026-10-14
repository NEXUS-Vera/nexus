# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class UpdatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class WorkspaceFileV1(TypedDict, closed=True):
    contentHash: str
    contentReference: str
    createdAt: str
    generatedFrom: NotRequired[str]
    mediaType: NotRequired[str]
    modifiedByUser: bool
    origin: Literal['USER', 'GENERATED', 'SYSTEM', 'RUNTIME_OUTPUT']
    path: str
    schemaVersion: Literal['1.0.0']
    sizeBytes: int
    updatedAt: str
    updatedBy: NotRequired[UpdatedBy]
    workspaceId: str
    writePolicy: Literal[
        'USER_EDITABLE', 'REGENERATION_MANAGED', 'READ_ONLY', 'EPHEMERAL'
    ]
