"""Normalize free-form ComponentCandidate specifications for Electrical Architecture."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Canonical keys Electrical Architecture generation consumes.
NORMALIZED_SPEC_KEYS: frozenset[str] = frozenset(
    {
        "interface",
        "supply-voltage",
        "logic-voltage",
        "current",
        "sample-rate",
        "capacity",
    }
)

_KEY_ALIASES: dict[str, str] = {
    "interface": "interface",
    "bus": "interface",
    "protocol": "interface",
    "comm-interface": "interface",
    "communication-interface": "interface",
    "supply-voltage": "supply-voltage",
    "supply_voltage": "supply-voltage",
    "vsupply": "supply-voltage",
    "vin": "supply-voltage",
    "vcc": "supply-voltage",
    "logic-voltage": "logic-voltage",
    "logic_voltage": "logic-voltage",
    "vio": "logic-voltage",
    "current": "current",
    "active-current": "current",
    "supply-current": "current",
    "iq": "current",
    "sample-rate": "sample-rate",
    "sample_rate": "sample-rate",
    "sampling-rate": "sample-rate",
    "odr": "sample-rate",
    "capacity": "capacity",
    "battery-capacity": "capacity",
}

_INTERFACE_ALIASES: dict[str, str] = {
    "i2c": "i2c",
    "i²c": "i2c",
    "twi": "i2c",
    "spi": "spi",
    "uart": "uart",
    "serial": "uart",
    "usart": "uart",
    "can": "can",
    "usb": "usb",
    "ethernet": "ethernet",
    "eth": "ethernet",
    "gpio": "gpio",
    "digital": "gpio",
    "pwm": "pwm",
    "analog": "analog",
    "adc": "analog",
    "power": "power",
    "ground": "ground",
    "gnd": "ground",
    "unknown": "unknown",
}


def normalize_spec_key(raw_key: str) -> str | None:
    """Return a canonical Electrical-consumed key, or None if unknown."""

    key = raw_key.strip().casefold().replace(" ", "-")
    return _KEY_ALIASES.get(key)


def normalize_interface_value(raw: Any) -> str:
    """Map a free-form interface string to Electrical interfaceType vocabulary."""

    if isinstance(raw, dict) and raw.get("kind") == "unknown":
        return "unknown"
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    token = raw.strip().casefold()
    if token in _INTERFACE_ALIASES:
        return _INTERFACE_ALIASES[token]
    # Handle values like "I2C/SPI"
    for part in token.replace("/", " ").replace(",", " ").split():
        if part in _INTERFACE_ALIASES:
            return _INTERFACE_ALIASES[part]
    return "other"


def is_unknown_value(value: Any) -> bool:
    return isinstance(value, dict) and value.get("kind") == "unknown"


def normalize_candidate_specifications(
    specifications: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Return `{canonicalKey: {value, unit?, operator?, rawKey, unknown}}`.

    Unknown/unrecognized keys are preserved under ``otherSpecs``.
    """

    normalized: dict[str, Any] = {}
    other: list[dict[str, Any]] = []
    for spec in specifications or []:
        if not isinstance(spec, dict):
            continue
        raw_key = spec.get("specKey")
        if not isinstance(raw_key, str) or not raw_key:
            continue
        canonical = normalize_spec_key(raw_key)
        entry = {
            "value": spec.get("value"),
            "unit": spec.get("unit"),
            "operator": spec.get("operator"),
            "rawKey": raw_key,
            "unknown": is_unknown_value(spec.get("value")),
        }
        if canonical is None:
            other.append({"specKey": raw_key, **{k: v for k, v in entry.items() if k != "rawKey"}})
            continue
        # First wins; later duplicates ignored unless first was unknown.
        existing = normalized.get(canonical)
        if existing is None or (existing.get("unknown") and not entry["unknown"]):
            normalized[canonical] = entry
    return {"specs": normalized, "otherSpecs": other}


def get_normalized_interface(specs: dict[str, Any]) -> str:
    interface = (specs.get("specs") or {}).get("interface")
    if not interface or interface.get("unknown"):
        return "unknown"
    return normalize_interface_value(interface.get("value"))


def get_normalized_voltage(
    specs: dict[str, Any], key: str = "supply-voltage"
) -> dict[str, Any] | None:
    entry = (specs.get("specs") or {}).get(key)
    if not entry or entry.get("unknown"):
        return None
    value = entry.get("value")
    if not isinstance(value, int | float):
        return None
    unit = entry.get("unit") if isinstance(entry.get("unit"), str) else "V"
    return {
        "schemaVersion": "1.0.0",
        "value": float(value),
        "unit": unit,
    }


def voltage_domain_key(voltage: dict[str, Any]) -> str:
    """Compare equivalent voltage magnitudes without float formatting differences."""
    value = Decimal(str(voltage["value"]))
    unit = voltage.get("unit") or "V"
    if unit == "mV":
        value /= 1000
        unit = "V"
    magnitude = f"{value.normalize():f}"
    if value.is_finite() and "." not in magnitude:
        magnitude += ".0"
    return f"{magnitude}{unit}"
