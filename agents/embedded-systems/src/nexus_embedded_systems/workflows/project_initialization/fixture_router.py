"""Fixture-phase routing for embedded project initialization.

This classifier is intentionally non-intelligent: it matches explicit keyword
families against the golden fixture packages. It must not invent confidence
or silently pick an unrelated fixture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class FixtureRouteOutcome(StrEnum):
    """Routing outcome. Callers compare members with ``is``; values are stable strings."""

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
    "esp32-imu-circuit-simulation": (
        "golden nexus circuit simulation",
        "esp32-class mcu and an imu",
        "wokwi surrogate simulation",
        "circuit simulation project with an esp32",
        "esp32 imu golden",
    ),
    "esp32-imu-vibration-monitor": (
        "mpu6050",
        "esp32-based vibration monitor",
        "stationary sensor noise",
        "accel_x rms",
        "accel_x rms noise",
    ),
}

# Prefer full-system golden family when ambiguous with broader vibration keywords.
_PRIORITY_FAMILIES: tuple[str, ...] = ("esp32-imu-vibration-monitor",)


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
        for preferred in _PRIORITY_FAMILIES:
            if preferred in matched:
                return FixtureRouteDecision(
                    outcome=FixtureRouteOutcome.MATCHED,
                    family=preferred,
                    matched_families=tuple(matched),
                )
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
