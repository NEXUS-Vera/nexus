"""Load component-planning eval cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


@dataclass(frozen=True)
class EvalCase:
    id: str
    suite: str
    category: str
    prompt: str
    expected_outcome: str
    expected_error_code: str | None = None
    expected_maturity: str | None = None
    min_role_count: int = 1
    require_sensor_role: bool = False
    forbidden_selections: tuple[str, ...] = ()
    notes: str | None = None


def _load(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def _to_case(raw: dict[str, Any], *, suite: str) -> EvalCase:
    return EvalCase(
        id=raw["id"],
        suite=suite,
        category=raw.get("category", suite),
        prompt=raw["prompt"],
        expected_outcome=raw.get("expectedOutcome", "supported"),
        expected_error_code=raw.get("expectedErrorCode"),
        expected_maturity=raw.get("expectedMaturity"),
        min_role_count=int(raw.get("minRoleCount") or 1),
        require_sensor_role=bool(raw.get("requireSensorRole")),
        forbidden_selections=tuple(raw.get("forbiddenSelections") or []),
        notes=raw.get("notes"),
    )


def load_all_cases(cases_dir: Path = CASES_DIR) -> list[EvalCase]:
    return [
        *[_to_case(i, suite="golden") for i in _load(cases_dir / "golden.yaml")],
        *[_to_case(i, suite="adversarial") for i in _load(cases_dir / "adversarial.yaml")],
    ]
