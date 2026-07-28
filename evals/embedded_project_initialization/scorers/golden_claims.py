"""Claim-matching scoring against golden/adversarial case expectations.

Rather than inspecting the transient model-interpretation stage (which is not
part of the final persisted package), this scorer checks that expected
explicit claims and missing dimensions are actually grounded in the final
project-brief and requirement-set content, and that no forbidden
component-level selection leaked into the brief, requirements, or functional
architecture.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..runners.case_loader import EvalCase


@dataclass(frozen=True)
class ClaimScore:
    passed: bool
    matched_explicit_claims: tuple[str, ...] = field(default_factory=tuple)
    missing_explicit_claims: tuple[str, ...] = field(default_factory=tuple)
    matched_missing_dimensions: tuple[str, ...] = field(default_factory=tuple)
    missing_expected_dimensions: tuple[str, ...] = field(default_factory=tuple)
    forbidden_hits: tuple[str, ...] = field(default_factory=tuple)


def _artifact_content(result: dict[str, Any], artifact_type: str) -> dict[str, Any]:
    for artifact in result.get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("artifactType") == artifact_type:
            content = artifact.get("content")
            return content if isinstance(content, dict) else {}
    return {}


def _grounded_text(result: dict[str, Any]) -> str:
    brief = _artifact_content(result, "project-brief")
    requirements = _artifact_content(result, "requirement-set")
    return json.dumps([brief, requirements], sort_keys=True).casefold()


def _full_package_text(result: dict[str, Any]) -> str:
    architecture = _artifact_content(result, "functional-architecture")
    return _grounded_text(result) + " " + json.dumps(architecture, sort_keys=True).casefold()


def score_claims(case: EvalCase, result: dict[str, Any]) -> ClaimScore:
    """Score claim grounding, missing-dimension propagation, and leakage."""

    grounded_text = _grounded_text(result)
    requirement_set = _artifact_content(result, "requirement-set")
    reported_missing_dimensions = {
        dimension.casefold() for dimension in (requirement_set.get("missingDimensions") or [])
    }

    matched_claims = tuple(
        claim for claim in case.expected_explicit_claims if claim.casefold() in grounded_text
    )
    missing_claims = tuple(
        claim for claim in case.expected_explicit_claims if claim.casefold() not in grounded_text
    )

    matched_dimensions = tuple(
        dimension
        for dimension in case.expected_missing_dimensions
        if dimension.casefold() in reported_missing_dimensions
    )
    missing_dimensions = tuple(
        dimension
        for dimension in case.expected_missing_dimensions
        if dimension.casefold() not in reported_missing_dimensions
    )

    full_text = _full_package_text(result)
    forbidden_hits = tuple(
        token for token in case.forbidden_selections if token.casefold() in full_text
    )

    passed = not missing_claims and not missing_dimensions and not forbidden_hits
    return ClaimScore(
        passed=passed,
        matched_explicit_claims=matched_claims,
        missing_explicit_claims=missing_claims,
        matched_missing_dimensions=matched_dimensions,
        missing_expected_dimensions=missing_dimensions,
        forbidden_hits=forbidden_hits,
    )
