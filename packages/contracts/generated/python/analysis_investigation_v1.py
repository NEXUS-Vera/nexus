# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

class AnalysisInvestigationV1(TypedDict, closed=True):
    investigationId: str
    lifecycleStage: Literal['INPUTS', 'TRANSFORM', 'METRICS', 'VISUALIZATION', 'VERIFY']
    linkedComponentIds: NotRequired[list[str]]
    linkedEvidenceIds: NotRequired[list[str]]
    linkedRequirementIds: NotRequired[list[str]]
    linkedTestPlanIds: NotRequired[list[str]]
    purpose: Literal['exploration', 'verification']
    question: NotRequired[str | None]
    schemaVersion: Literal['1.0.0']
    stageVocabulary: NotRequired[
        list[Literal['INPUTS', 'TRANSFORM', 'METRICS', 'VISUALIZATION', 'VERIFY']]
    ]
    title: str
    verificationCriterion: NotRequired[dict[str, Any] | None]
