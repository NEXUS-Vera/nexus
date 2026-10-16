# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ComputedMetric(TypedDict, closed=True):
    executionRunId: NotRequired[str | None]
    metricId: str
    outputId: NotRequired[str | None]
    rmsNoiseDefinition: NotRequired[Literal['demeaned', 'about-zero']]
    unit: str
    value: float

class VerificationCriterion(TypedDict, closed=True):
    linkedRequirementId: str
    metricId: str
    operator: Literal['<', '<=', '>', '>=', '==', '!=']
    threshold: float
    unit: str

class AnalysisVerificationAssessmentV1(TypedDict, closed=True):
    assessment: Literal['PASS', 'FAIL', 'INCONCLUSIVE']
    authority: Literal['deterministic-code']
    computedMetric: ComputedMetric
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    verificationCriterion: VerificationCriterion
