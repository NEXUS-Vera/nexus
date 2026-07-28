# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

class QuantityV1(TypedDict, closed=True):
    schemaVersion: Literal['1.0.0']
    unit: str
    value: float
