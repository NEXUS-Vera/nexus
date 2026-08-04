# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ProjectGraphEdgeV1(TypedDict, closed=True):
    createdByEventId: str
    edgeId: str
    edgeType: Literal[
        'depends-on',
        'derives-from',
        'constrains',
        'covers',
        'blocks',
        'invalidates',
        'supports',
        'contradicts',
        'supersedes',
        'produced-by',
        'belongs-to',
        'answers',
    ]
    projectId: str
    reason: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceNodeId: str
    targetNodeId: str
    validFrom: str
    validUntil: NotRequired[str]
