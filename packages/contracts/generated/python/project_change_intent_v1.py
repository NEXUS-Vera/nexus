# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ProjectChangeIntentV1(TypedDict, closed=True):
    ambiguities: list[str]
    confidence: Literal['low', 'medium', 'high']
    operation: Literal[
        'clarify-requirement',
        'add-requirement',
        'change-requirement',
        'remove-proposed-requirement',
        'answer-open-question',
        'change-project-scope',
    ]
    requestedChange: str
    requiresUserConfirmation: bool
    schemaVersion: Literal['1.0.0']
    sourceTurnId: str
    targetArtifactType: (
        Literal[
            'project-brief', 'requirement-set', 'functional-architecture', 'next-action'
        ]
        | None
    )
    targetQuestionId: NotRequired[str]
    targetRequirementId: NotRequired[str]
