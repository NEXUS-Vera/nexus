# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class TurnRouteV1(TypedDict, closed=True):
    autonomyMode: Literal['collaborate', 'delegate']
    chairmanRequiredEventually: bool
    complexity: Literal['low', 'medium', 'high', 'unknown']
    domain: Literal['embedded-products']
    projectOperation: Literal['create-project', 'none']
    reasons: list[str]
    routeId: str
    routeType: Literal['project-initialization', 'unsupported']
    schemaVersion: Literal['1.0.0']
    supported: bool
    turnId: str
    unsupportedReason: NotRequired[str]
