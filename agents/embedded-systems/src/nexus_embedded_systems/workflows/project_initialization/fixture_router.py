"""Fixture-phase routing for embedded project initialization.

This classifier is intentionally non-intelligent: it matches explicit keyword
families against the five golden fixture packages. It must not invent confidence
or silently pick an unrelated fixture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FixtureRouteOutcome(str, Enum):
    MATCHED = "matched"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class FixtureRouteDecision:
    outcome: FixtureRouteOutcome
    family: str | None
    matched_families: tuple[str, ...]


FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "indoor-environmental-rover": (
        "rover",
        "room mapping",
        "air quality",
        "temperature map",
        "humidity map",
        "indoor environmental",
        "environmental mapping",
    ),
    "wearable-tremor-monitor": (
        "tremor",
        "wrist-worn",
        "wrist worn",
        "wearable motion",
        "hand motion",
        "hand tremors",
        "hand tremor",
    ),
    "greenhouse-sensing-node": (
        "greenhouse",
        "soil moisture",
        "plant monitoring",
        "remote greenhouse",
    ),
    "vibration-monitoring-device": (
        "vibration",
        "machine vibration",
        "machine condition",
        "equipment monitoring",
    ),
    "robot-obstacle-detection-module": (
        "obstacle",
        "collision avoidance",
        "detect objects",
        "robot reaction",
        "obstacle-detection",
        "obstacle detection",
    ),
}

SUPPORTED_FAMILIES: tuple[str, ...] = tuple(FAMILY_KEYWORDS.keys())


def normalize_prompt(message: str) -> str:
    lowered = message.casefold()
    cleaned = re.sub(r"[^\w\s-]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def route_fixture_family(message: str) -> FixtureRouteDecision:
    """Deterministic fixture-phase router. Not production NLP."""

    normalized = normalize_prompt(message)
    if not normalized:
        return FixtureRouteDecision(
            outcome=FixtureRouteOutcome.UNSUPPORTED,
            family=None,
            matched_families=(),
        )

    matched: list[str] = []
    for family, keywords in FAMILY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            matched.append(family)

    if len(matched) == 1:
        return FixtureRouteDecision(
            outcome=FixtureRouteOutcome.MATCHED,
            family=matched[0],
            matched_families=tuple(matched),
        )
    if len(matched) > 1:
        return FixtureRouteDecision(
            outcome=FixtureRouteOutcome.AMBIGUOUS,
            family=None,
            matched_families=tuple(matched),
        )
    return FixtureRouteDecision(
        outcome=FixtureRouteOutcome.UNSUPPORTED,
        family=None,
        matched_families=(),
    )
