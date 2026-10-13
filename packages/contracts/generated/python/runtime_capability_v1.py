# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class RuntimeCapabilityV1(TypedDict, closed=True):
    available: bool
    capabilityId: Literal[
        'structured-validation',
        'fake-execution',
        'file-workspace',
        'embedded-build',
        'python-kernel',
        'circuit-simulation',
        'architecture-export',
    ]
    description: NotRequired[str]
    displayName: str
    providerId: str
    schemaVersion: Literal['1.0.0']
