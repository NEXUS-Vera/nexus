"""Explicit Wokwi component mappings.

Registry lookup is deliberately exact and case-sensitive. Adding a mapping is
an explicit compatibility decision, not a similarity heuristic.
"""

from __future__ import annotations

from .types import ComponentMapping, MappingType, PinMapping

FIXED_PIN_PROFILE = (
    PinMapping("3V3", "3V3"),
    PinMapping("GND", "GND.1"),
    PinMapping("21", "D21"),
    PinMapping("22", "D22"),
)

WOKWI_ESP32_PROVIDER_PART = "wokwi-esp32-devkit-v1"


def esp32_serial_monitor_connections(mcu_part_id: str) -> tuple[list[object], ...]:
    """Provider-only UART wiring required for Wokwi serial observation.

    Canonical Nexus Electrical Architecture never models `$serialMonitor`.
    This belongs to the Wokwi ESP32 execution profile so UART output can be
    captured by wokwi-cli.
    """
    return (
        [f"{mcu_part_id}:TX0", "$serialMonitor:RX", "", []],
        [f"{mcu_part_id}:RX0", "$serialMonitor:TX", "", []],
    )


EXACT_MAPPING_REGISTRY = (
    ComponentMapping(
        source="fixture",
        manufacturer="Fixture Compute",
        part_number="FX-MCU-32",
        provider_part=WOKWI_ESP32_PROVIDER_PART,
        mapping_type=MappingType.SURROGATE,
        pins=FIXED_PIN_PROFILE,
    ),
    ComponentMapping(
        source="fixture",
        manufacturer="Fixture Motion",
        part_number="FX-IMU-200",
        provider_part="wokwi-mpu6050",
        mapping_type=MappingType.SURROGATE,
        pins=tuple(PinMapping(pin, pin) for pin in ("VCC", "GND", "SDA", "SCL")),
    ),
)

_BY_IDENTITY = {
    (entry.source, entry.manufacturer, entry.part_number): entry for entry in EXACT_MAPPING_REGISTRY
}


def find_mapping(*, source: str, manufacturer: str, part_number: str) -> ComponentMapping | None:
    """Return only an exact source/manufacturer/part-number match."""
    return _BY_IDENTITY.get((source, manufacturer, part_number))
