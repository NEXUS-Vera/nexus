"""Physical I2C pair selection is independent of functional flow records."""

import copy
from typing import Any

import pytest
from nexus_board.errors import CommandValidationError
from nexus_embedded_systems.workflows.project_modification.execution_plan import (
    derive_default_configuration,
)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("opposite", [False, True])
@pytest.mark.parametrize(
    "kinds", [("control", "signal"), ("signal", "signal"), ("control", "control")]
)
@pytest.mark.parametrize("distinct", [False, True])
def test_parallel_i2c_pairs(
    reverse: bool, opposite: bool, kinds: tuple[str, str], distinct: bool
) -> None:
    candidates: list[dict[str, Any]] = [
        {
            "candidateId": part,
            "partNumber": part,
            "componentRoleId": part,
            "candidateState": "proposed",
            "specifications": [],
        }
        for part in ("ESP32-DEVKIT-V1", "MPU6050")
    ]
    nodes = [
        {"nodeId": c["candidateId"], "componentCandidateId": c["candidateId"]} for c in candidates
    ]
    connections = []
    for index, kind in enumerate(kinds):
        endpoints = [c["candidateId"] for c in candidates[:2]]
        if distinct and index:
            for candidate in copy.deepcopy(candidates[:2]):
                candidate["candidateId"] += "-second"
                candidates.append(candidate)
                nodes.append(
                    {
                        "nodeId": candidate["candidateId"],
                        "componentCandidateId": candidate["candidateId"],
                    }
                )
            endpoints = [c["candidateId"] for c in candidates[2:]]
        if reverse != (opposite and bool(index)):
            endpoints.reverse()
        connections.append(
            {
                "connectionId": f"bus-{1 - index}",
                "interfaceType": "i2c",
                "status": "provisional",
                "connectionType": kind,
                "fromNodeId": endpoints[0],
                "toNodeId": endpoints[1],
            }
        )
    package = {
        "artifacts": [
            {"artifactType": "component-plan", "content": {"candidates": candidates}},
            {
                "artifactType": "electrical-architecture",
                "content": {"nodes": nodes, "connections": connections},
            },
        ]
    }
    original = copy.deepcopy(package)
    if distinct:
        with pytest.raises(CommandValidationError, match="requires one usable"):
            derive_default_configuration(package)
    else:
        result = derive_default_configuration(package)
        assert result["i2c"]["connectionId"] == "bus-0"
        assert [c["candidateId"] for c in result["components"]] == [
            "ESP32-DEVKIT-V1",
            "MPU6050",
        ]
        connections.reverse()
        assert derive_default_configuration(package) == result
        connections.reverse()
    assert package == original
