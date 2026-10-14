# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ExecutionLogChunkV1(TypedDict, closed=True):
    content: str
    executionJobId: str
    schemaVersion: Literal['1.0.0']
    sequence: int
    stream: Literal['stdout', 'stderr', 'system']
    timestamp: str
    truncated: NotRequired[bool]
