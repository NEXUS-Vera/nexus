"""Load YAML eval cases into typed `EvalCase` records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


@dataclass(frozen=True)
class EvalCase:
    """A single scripted eval scenario.

    `expected_outcome` is either `"supported"` (the workflow should produce a
    valid initialization package) or `"unsupported"` (the workflow should
    reject the prompt with `expected_error_code`).
    """

    id: str
    suite: str
    category: str
    prompt: str
    expected_outcome: str
    expected_error_code: str | None = None
    expected_explicit_claims: tuple[str, ...] = ()
    expected_missing_dimensions: tuple[str, ...] = ()
    forbidden_selections: tuple[str, ...] = ()
    notes: str | None = None


def _load_yaml_list(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of cases in {path}, got {type(data).__name__}.")
    return data


def _to_case(raw: dict[str, Any], *, suite: str) -> EvalCase:
    return EvalCase(
        id=raw["id"],
        suite=suite,
        category=raw.get("category", suite),
        prompt=raw["prompt"],
        expected_outcome=raw.get("expectedOutcome", "supported"),
        expected_error_code=raw.get("expectedErrorCode"),
        expected_explicit_claims=tuple(raw.get("expectedExplicitClaims") or []),
        expected_missing_dimensions=tuple(raw.get("expectedMissingDimensions") or []),
        forbidden_selections=tuple(raw.get("forbiddenSelections") or []),
        notes=raw.get("notes"),
    )


def load_golden_cases(cases_dir: Path = CASES_DIR) -> list[EvalCase]:
    return [_to_case(item, suite="golden") for item in _load_yaml_list(cases_dir / "golden.yaml")]


def load_adversarial_cases(cases_dir: Path = CASES_DIR) -> list[EvalCase]:
    return [
        _to_case(item, suite="adversarial")
        for item in _load_yaml_list(cases_dir / "adversarial.yaml")
    ]


def load_all_cases(cases_dir: Path = CASES_DIR) -> list[EvalCase]:
    return load_golden_cases(cases_dir) + load_adversarial_cases(cases_dir)
