# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

class TargetValue(TypedDict, closed=True):
    kind: Literal['unknown']

class SelectionConstraintV1(TypedDict, closed=True):
    componentRoleId: str
    confirmationStatus: Literal['confirmed', 'inferred', 'proposed', 'unknown']
    constraintId: str
    constraintType: Literal[
        'measurement-range',
        'accuracy',
        'resolution',
        'sample-rate',
        'bandwidth',
        'latency',
        'supply-voltage',
        'logic-voltage',
        'active-current',
        'sleep-current',
        'peak-current',
        'interface',
        'bus-bandwidth',
        'operating-temperature',
        'humidity-rating',
        'size',
        'weight',
        'cost',
        'availability',
        'driver-support',
        'platform-support',
        'environment',
        'mechanical-mounting',
    ]
    importance: Literal['required', 'preferred', 'nice-to-have']
    operator: Literal[
        'eq', 'neq', 'gte', 'lte', 'gt', 'lt', 'in', 'contains', 'unknown'
    ]
    rationale: str
    sourceArchitectureNodeIds: list[str]
    sourceRequirementIds: list[str]
    targetValue: float | str | bool | TargetValue
    unit: str | None
