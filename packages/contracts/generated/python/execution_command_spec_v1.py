# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

class DeclaredOutput(TypedDict, closed=True):
    kind: Literal['result', 'artifact', 'log']
    path: str

class EnvironmentItem(TypedDict, closed=True):
    name: str
    value: str

class ExecutionCommandSpecV1(TypedDict, closed=True):
    arguments: list[str]
    declaredOutputs: list[DeclaredOutput]
    environment: list[EnvironmentItem]
    executable: str
    schemaVersion: Literal['1.0.0']
    workingDirectory: str
