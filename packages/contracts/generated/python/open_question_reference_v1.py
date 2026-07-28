# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class OpenQuestionReferenceV1(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']
