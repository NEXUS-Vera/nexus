"""Propose provisional component candidates (fixture table / deterministic)."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import new_id

_FIXTURE_CANDIDATES: dict[str, list[dict[str, Any]]] = {
    "sensor": [
        {
            "manufacturer": "Fixture Semiconductor",
            "partNumber": "FX-ENV-100",
            "displayName": "Fixture environmental sensor",
            "specifications": [
                {"specKey": "interface", "value": "I2C", "operator": "eq"},
                {"specKey": "supply-voltage", "value": 3.3, "unit": "V", "operator": "eq"},
            ],
            "advantages": ["Common digital interface", "Suitable for early prototypes"],
            "limitations": ["Datasheet grounding deferred", "Exact accuracy unknown"],
        },
        {
            "manufacturer": "Fixture Motion",
            "partNumber": "FX-IMU-200",
            "displayName": "Fixture IMU-class motion sensor",
            "specifications": [
                {"specKey": "interface", "value": "I2C", "operator": "eq"},
                {"specKey": "sample-rate", "value": {"kind": "unknown"}, "unit": "Hz", "operator": "unknown"},
            ],
            "advantages": ["Covers tremor/vibration sensing roles"],
            "limitations": ["Noise floor not grounded"],
        },
        {
            "manufacturer": "Fixture Sensing",
            "partNumber": "FX-SOIL-10",
            "displayName": "Fixture soil-moisture probe class",
            "specifications": [
                {"specKey": "interface", "value": "analog", "operator": "eq"},
                {"specKey": "supply-voltage", "value": 3.3, "unit": "V", "operator": "eq"},
            ],
            "advantages": ["Useful for greenhouse moisture roles"],
            "limitations": ["Calibration curve not grounded"],
        },
    ],
    "compute": [
        {
            "manufacturer": "Fixture Compute",
            "partNumber": "FX-MCU-32",
            "displayName": "Fixture microcontroller class",
            "specifications": [
                {"specKey": "logic-voltage", "value": 3.3, "unit": "V", "operator": "eq"},
                {"specKey": "interface", "value": "I2C", "operator": "eq"},
            ],
            "advantages": ["Adequate for early firmware prototypes"],
            "limitations": ["Pinmux and peripheral fit not verified"],
        },
        {
            "manufacturer": "Fixture Compute",
            "partNumber": "FX-MCU-WIFI",
            "displayName": "Fixture Wi-Fi MCU class",
            "specifications": [
                {"specKey": "logic-voltage", "value": 3.3, "unit": "V", "operator": "eq"},
                {"specKey": "interface", "value": "UART", "operator": "eq"},
            ],
            "advantages": ["On-module connectivity for connected nodes"],
            "limitations": ["Power budget impact not grounded"],
        },
    ],
    "power": [
        {
            "manufacturer": "Fixture Power",
            "partNumber": "FX-REG-33",
            "displayName": "Fixture 3.3V regulator class",
            "specifications": [
                {"specKey": "supply-voltage", "value": 3.3, "unit": "V", "operator": "eq"},
            ],
            "advantages": ["Matches common sensor rails"],
            "limitations": ["Efficiency and dropout not grounded"],
        },
        {
            "manufacturer": "Fixture Power",
            "partNumber": "FX-LIPO-1S",
            "displayName": "Fixture LiPo cell class (estimate)",
            "specifications": [
                {"specKey": "supply-voltage", "value": 3.7, "unit": "V", "operator": "eq"},
                {"specKey": "capacity", "value": {"kind": "unknown"}, "unit": "mAh", "operator": "unknown"},
            ],
            "advantages": ["Common wearable/portable energy source"],
            "limitations": ["Capacity/runtime estimates unverified"],
        },
    ],
    "communication": [
        {
            "manufacturer": "Fixture Radio",
            "partNumber": "FX-BLE-1",
            "displayName": "Fixture BLE module class",
            "specifications": [
                {"specKey": "interface", "value": "UART", "operator": "eq"},
            ],
            "advantages": ["Fits simple connected prototypes"],
            "limitations": ["Link budget not grounded"],
        },
        {
            "manufacturer": "Fixture Radio",
            "partNumber": "FX-WIFI-1",
            "displayName": "Fixture Wi-Fi module class",
            "specifications": [
                {"specKey": "interface", "value": "SPI", "operator": "eq"},
            ],
            "advantages": ["Higher bandwidth remote reporting"],
            "limitations": ["Power and antenna constraints unknown"],
        },
    ],
    "storage": [
        {
            "manufacturer": "Fixture Memory",
            "partNumber": "FX-FLASH-8",
            "displayName": "Fixture flash storage class",
            "specifications": [
                {"specKey": "interface", "value": "SPI", "operator": "eq"},
            ],
            "advantages": ["Supports local logging roles"],
            "limitations": ["Endurance not grounded"],
        },
        {
            "manufacturer": "Fixture Memory",
            "partNumber": "FX-FRAM-1",
            "displayName": "Fixture FRAM class",
            "specifications": [
                {"specKey": "interface", "value": "I2C", "operator": "eq"},
            ],
            "advantages": ["Lower-power logging for wearables"],
            "limitations": ["Capacity tradeoffs not grounded"],
        },
    ],
}


def propose_candidates_for_roles(
    roles: list[dict[str, Any]],
    *,
    max_per_role: int = 2,
    source: str = "fixture",
    prefer_first: bool = True,
) -> list[dict[str, Any]]:
    """Return provisional unverified candidates from a deterministic fixture table."""

    candidates: list[dict[str, Any]] = []
    for role in roles:
        role_id = role.get("componentRoleId")
        category = str(role.get("category") or "sensor")
        if not isinstance(role_id, str):
            continue
        templates = list(_FIXTURE_CANDIDATES.get(category) or _FIXTURE_CANDIDATES["sensor"])
        for index, template in enumerate(templates[:max_per_role]):
            state = "preferred" if prefer_first and index == 0 else "proposed"
            candidates.append(
                {
                    "candidateId": new_id("cand_"),
                    "componentRoleId": role_id,
                    "manufacturer": template["manufacturer"],
                    "partNumber": template["partNumber"],
                    "displayName": template["displayName"],
                    "candidateCategory": category if category in _FIXTURE_CANDIDATES else "sensor",
                    "candidateState": state,
                    "evidenceStatus": "unverified",
                    "specifications": list(template["specifications"]),
                    "advantages": list(template["advantages"]),
                    "limitations": list(template["limitations"]),
                    "compatibilityCheckIds": [],
                    "evidenceReferences": [],
                    "source": source,
                    "confidence": "low",
                    "notes": "Provisional fixture candidate pending datasheet retrieval.",
                }
            )
    return candidates
