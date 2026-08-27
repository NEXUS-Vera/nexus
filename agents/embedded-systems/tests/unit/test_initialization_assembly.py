"""Unit tests for project-initialization assembly helpers."""

from __future__ import annotations

from nexus_embedded_systems.workflows.project_initialization.assembly import (
    normalize_architecture_draft,
)


def test_normalize_architecture_backfills_unsatisfied_requirements() -> None:
    draft = {
        "systemBoundary": "wearable boundary",
        "nodes": [
            {
                "localNodeKey": "node-a",
                "name": "Sensing and processing",
                "functionalType": "compute",
                "responsibilities": ["Measure motion and process data."],
                "satisfiesLocalRequirementKeys": ["req-a"],
            },
            {
                "localNodeKey": "node-b",
                "name": "Power management",
                "functionalType": "power",
                "responsibilities": ["Supply stable power."],
                "satisfiesLocalRequirementKeys": [],
            },
        ],
        "edges": [],
        "assumptions": [],
        "unresolvedDecisionStatements": [],
        "requirementCoverageLocalKeys": ["req-a", "req-b", "req-c"],
    }
    local_key_to_req_id = {
        "req-a": "req_AAAAAAAAAAAAAAAA",
        "req-b": "req_BBBBBBBBBBBBBBBB",
        "req-c": "req_CCCCCCCCCCCCCCCC",
    }

    content = normalize_architecture_draft(
        draft,
        local_key_to_req_id,
        open_questions=[],
        project_id="proj_TESTTESTTESTTEST",
        artifact_id="art_TESTTESTTESTTEST",
        now="2026-08-04T00:00:00Z",
    )

    satisfied = {
        rid
        for node in content["nodes"]
        for rid in node.get("satisfiesRequirementIds", [])
        if isinstance(rid, str)
    }
    assert satisfied == set(local_key_to_req_id.values())


def test_normalize_architecture_scrubs_user_named_components() -> None:
    draft = {
        "systemBoundary": "ESP32 vibration monitor boundary",
        "nodes": [
            {
                "localNodeKey": "node-sense",
                "name": "MPU6050 Sensing",
                "functionalType": "sensing",
                "responsibilities": [
                    "Sample accel_x from the MPU6050 over I2C.",
                    "Stream telemetry from the ESP32 UART.",
                ],
                "satisfiesLocalRequirementKeys": ["req-a"],
            }
        ],
        "edges": [],
        "assumptions": [],
        "unresolvedDecisionStatements": [],
        "requirementCoverageLocalKeys": ["req-a"],
    }
    content = normalize_architecture_draft(
        draft,
        {"req-a": "req_AAAAAAAAAAAAAAAA"},
        open_questions=[],
        project_id="proj_TESTTESTTESTTEST",
        artifact_id="art_TESTTESTTESTTEST",
        now="2026-08-04T00:00:00Z",
    )
    node = content["nodes"][0]
    blob = f"{node['name']} {' '.join(node['responsibilities'])}"
    assert "MPU6050" not in blob
    assert "ESP32" not in blob
    assert "inertial sensor" in blob.lower()
    assert "application microcontroller" in blob.lower()
