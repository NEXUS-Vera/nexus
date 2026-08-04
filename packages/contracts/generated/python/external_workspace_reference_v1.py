# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ExternalWorkspaceReferenceV1(TypedDict, closed=True):
    createdAt: str
    displayLabel: NotRequired[str]
    externalReferenceId: str
    lastSyncedAt: NotRequired[str]
    providerId: Literal['fake', 'wokwi', 'flux', 'jupyter', 'github', 'kicad']
    schemaVersion: Literal['1.0.0']
    syncStatus: Literal['unbound', 'bound', 'stale', 'error']
    updatedAt: str
