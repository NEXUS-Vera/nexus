# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Error(TypedDict, closed=True):
    code: str
    message: str

class ExecutionResultV1(TypedDict, closed=True):
    completedAt: str
    error: NotRequired[Error]
    evidenceReferences: list[str]
    executionRunId: str
    outputReferences: list[str]
    schemaVersion: Literal['1.0.0']
    status: Literal[
        'completed',
        'completed-with-warnings',
        'failed',
        'cancelled',
        'timed-out',
        'stale',
    ]
    summary: NotRequired[str]
