from __future__ import annotations

import pytest
from nexus_embedded_systems.workflows.project_initialization.fixture_router import (
    FixtureRouteOutcome,
    route_fixture_family,
)


@pytest.mark.parametrize(
    ("message", "family"),
    [
        (
            "I want to build a small indoor rover that drives around a room and maps "
            "temperature, humidity, and air quality.",
            "indoor-environmental-rover",
        ),
        (
            "I want to build a wrist-worn device that measures hand tremors "
            "and records the motion data for later analysis.",
            "wearable-tremor-monitor",
        ),
        (
            "I want to build a greenhouse monitoring node that measures temperature, "
            "humidity, soil moisture, and light, and reports the readings remotely.",
            "greenhouse-sensing-node",
        ),
        (
            "I want to build a device that attaches to a machine and records vibration "
            "so I can detect changes in how the machine is operating.",
            "vibration-monitoring-device",
        ),
        (
            "I want to build an obstacle-detection module for a small indoor robot "
            "so it can detect objects in front of it and react before it hits them.",
            "robot-obstacle-detection-module",
        ),
        (
            "I want a golden Nexus circuit simulation project with an ESP32-class MCU "
            "and an IMU motion sensor for Wokwi surrogate simulation.",
            "esp32-imu-circuit-simulation",
        ),
        (
            "Build an ESP32-based vibration monitor using an MPU6050. "
            "It should stream acceleration telemetry and analyze stationary sensor noise "
            "to verify that accel_x RMS noise stays below 0.10 g.",
            "esp32-imu-vibration-monitor",
        ),
    ],
)
def test_fixture_router_maps_each_family(message: str, family: str) -> None:
    decision = route_fixture_family(message)
    assert decision.outcome is FixtureRouteOutcome.MATCHED
    assert decision.family == family


def test_fixture_router_ignores_casing_and_punctuation() -> None:
    decision = route_fixture_family("WRIST-WORN!!! tremor??? monitor")
    assert decision.outcome is FixtureRouteOutcome.MATCHED
    assert decision.family == "wearable-tremor-monitor"


def test_fixture_router_unsupported() -> None:
    decision = route_fixture_family("I want a desktop weather widget for my kitchen.")
    assert decision.outcome is FixtureRouteOutcome.UNSUPPORTED
    assert decision.family is None


def test_fixture_router_ambiguous() -> None:
    decision = route_fixture_family(
        "Build a greenhouse rover with vibration sensing and tremor monitoring"
    )
    assert decision.outcome is FixtureRouteOutcome.AMBIGUOUS
    assert decision.family is None
    assert len(decision.matched_families) >= 2


def test_fixture_router_prefers_golden_vibration_monitor_over_generic() -> None:
    decision = route_fixture_family(
        "Build an ESP32-based vibration monitor using an MPU6050 for accel_x RMS noise"
    )
    assert decision.outcome is FixtureRouteOutcome.MATCHED
    assert decision.family == "esp32-imu-vibration-monitor"
    assert "vibration-monitoring-device" in decision.matched_families


def test_fixture_route_outcome_values_are_stable_strings() -> None:
    # StrEnum: members are plain strings with stable values (issue #55).
    assert [o.value for o in FixtureRouteOutcome] == ["matched", "unsupported", "ambiguous"]
    assert FixtureRouteOutcome.MATCHED == "matched"
    assert str(FixtureRouteOutcome.AMBIGUOUS) == "ambiguous"
    assert FixtureRouteOutcome("unsupported") is FixtureRouteOutcome.UNSUPPORTED
