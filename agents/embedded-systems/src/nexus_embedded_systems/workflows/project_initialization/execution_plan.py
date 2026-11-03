"""Derive a review proposal from canonical initialization artifacts, without executing it."""

from __future__ import annotations

from typing import Any

PLATFORM_MPU_READY_MARKER = "NEXUS_MPU_READY"
# Evidence emitted by approved IMU analysis, firmware and wiring promotion.
EVALUABLE_EVIDENCE = {
    "metricIds": [
        "sampling_hz",
        "accel_x_rms_noise_g",
        "mean_accel_x_g",
        "mean_accel_y_g",
        "mean_accel_z_g",
        "sampleCount",
    ],
    "markers": [PLATFORM_MPU_READY_MARKER, "time_s", "accel_x_g", "accel_y_g", "accel_z_g"],
    "outputNames": ["summary.json", "processed.csv", "accel_plot.png", "results.json"],
    "signals": ["SDA", "SCL"],
}


def evaluable_criterion_proposal(criterion: Any, method: str | None = None) -> bool:
    """Accept definitions only for evidence the platform can promote."""
    from nexus_contracts.validation.execution_plan_validator import valid_criterion_proposal

    if not valid_criterion_proposal(criterion):
        return False
    kind = criterion["criterionType"]
    if kind in {"numeric-comparison", "range"}:
        return (
            method in {None, "analysis"}
            and criterion.get("metricId") in EVALUABLE_EVIDENCE["metricIds"]
        )
    if kind == "existence":
        return method in {None, "analysis"} and all(
            name.strip() in EVALUABLE_EVIDENCE["outputNames"]
            for name in criterion.get("outputName", "").split(",")
        )
    if kind in {"contains", "exact-match"}:
        return (
            method in {None, "simulation", "execution-output", "firmware-test"}
            and criterion.get("marker", criterion.get("expectedValue"))
            in EVALUABLE_EVIDENCE["markers"]
        )
    if kind == "structural-mapping":
        return (
            method in {None, "inspection"}
            and criterion.get("signal") in EVALUABLE_EVIDENCE["signals"]
        )
    return False


def compose_execution_plan(package: dict[str, Any]) -> dict[str, Any]:
    artifacts = package["artifacts"]
    by_type = {a["artifactType"]: a for a in artifacts}

    def entities(artifact_type: str, collection: str, key: str) -> list[dict[str, str]]:
        artifact = by_type.get(artifact_type)
        if artifact is None:
            return []
        return [
            {"artifactId": artifact["artifactId"], "entityId": item[key]}
            for item in artifact["content"].get(collection, [])
        ]

    requirements = by_type["requirement-set"]["content"]["requirements"]
    workspaces = [
        {
            "workspaceKey": kind,
            "artifactType": kind,
            "availability": "artifact-available" if kind in by_type else "planned",
        }
        for kind in [
            "requirement-set",
            "component-plan",
            "electrical-architecture",
            "firmware",
            "analysis",
            "test-plan",
        ]
    ]
    objectives = [
        {
            "objectiveId": f"objective-{index}",
            "requirementId": req["requirementId"],
            "workspaceKey": "requirement-set",
            "method": req.get("verificationMethod") or "Verification method requires review.",
            "acceptanceCriteria": list(req.get("acceptanceCriteria") or []),
        }
        for index, req in enumerate(requirements, 1)
    ]
    # An ordered review checklist, not tool commands or an approval record.
    sequence = [
        ("review", "Review requirements, assumptions and open decisions", ["requirement-set"]),
        (
            "interfaces",
            "Review component candidates and provisional interfaces",
            ["component-plan", "electrical-architecture"],
        ),
        ("firmware", "Approve and prepare firmware workspace", ["firmware"]),
        ("build", "Build the approved firmware and retain output identities", ["firmware"]),
        ("simulation", "Run supported surrogate tests using the build outputs", ["test-plan"]),
        ("analysis", "Analyze actual observations against verification objectives", ["analysis"]),
    ]
    return {
        "schemaVersion": "1.0.0",
        "status": "proposed",
        "basisProjectStateVersion": package["project"]["currentStateVersion"],
        "sourceArtifacts": [
            {"artifactId": a["artifactId"], "artifactVersion": a["artifactVersion"]}
            for a in artifacts
        ],
        "requirements": entities("requirement-set", "requirements", "requirementId"),
        "assumptions": [
            {"artifactId": a["artifactId"], "entityId": item["assumptionId"]}
            for a in artifacts
            for item in a["content"].get("assumptions", [])
            if isinstance(item, dict) and "assumptionId" in item
        ],
        "components": entities("component-plan", "componentRoles", "componentRoleId"),
        "interfaces": entities("electrical-architecture", "connections", "connectionId"),
        "openDecisionIds": [
            q["questionId"] for q in package["openQuestions"] if q["status"] == "open"
        ],
        "workspaces": workspaces,
        "verificationObjectives": objectives,
        "steps": [
            {
                "stepId": key,
                "title": title,
                "dependsOn": [sequence[index - 1][0]] if index else [],
                "workspaceKeys": targets,
                "objectiveIds": [o["objectiveId"] for o in objectives],
                "requiresApproval": True,
            }
            for index, (key, title, targets) in enumerate(sequence)
        ],
    }


class DefaultConfigurationError(ValueError):
    """The package has no unique supported prototype binding."""


def derive_default_configuration(package: dict[str, Any]) -> dict[str, Any]:
    """Select the supported prototype pair from its current electrical binding.

    Other architecture roles remain in the review plan, outside materialization.
    Ambiguous or unresolved bindings require explicit user configuration.
    """
    by_type = {a["artifactType"]: a["content"] for a in package["artifacts"]}
    candidates = {
        c["candidateId"]: c
        for c in by_type["component-plan"]["candidates"]
        if isinstance(c, dict)
        and all(
            isinstance(c.get(k), str) for k in ("candidateId", "candidateState", "componentRoleId")
        )
        and c["candidateState"] not in {"blocked", "rejected", "superseded"}
        and isinstance(c.get("partNumber"), str)
        and isinstance(c.get("specifications"), list)
    }
    electrical = by_type.get("electrical-architecture", {})
    nodes = {
        n["nodeId"]: n
        for n in electrical.get("nodes", [])
        if isinstance(n, dict)
        and isinstance(n.get("nodeId"), str)
        and isinstance(n.get("componentCandidateId"), str)
    }
    options: dict[tuple[str, str], dict[str, Any]] = {}
    for connection in electrical.get("connections", []):
        if not isinstance(connection, dict) or not all(
            isinstance(connection.get(k), str)
            for k in ("interfaceType", "status", "fromNodeId", "toNodeId", "connectionId")
        ):
            continue
        if connection["interfaceType"] != "i2c" or connection["status"] in {
            "unresolved",
            "needs-resolution",
        }:
            continue
        pair = [
            candidates.get(nodes.get(connection[key], {}).get("componentCandidateId"))
            for key in ("fromNodeId", "toNodeId")
        ]
        if any(c is None for c in pair):
            continue
        selected = [c for c in pair if c is not None]
        if {c.get("partNumber", "").upper() for c in selected} != {"ESP32-DEVKIT-V1", "MPU6050"}:
            continue
        compute = next(c for c in selected if c.get("partNumber", "").upper() == "ESP32-DEVKIT-V1")
        specs = {
            s["specKey"]: s["value"]
            for s in compute.get("specifications", [])
            if isinstance(s, dict) and isinstance(s.get("specKey"), str) and "value" in s
        }
        sensor = next(c for c in selected if c.get("partNumber", "").upper() == "MPU6050")
        selected = [compute, sensor]
        pair_key = (compute["candidateId"], sensor["candidateId"])
        # Parallel functional flows share one physical bus. Preserve the electrical
        # records and choose a stable representative independent of edge ordering.
        if pair_key in options and (
            options[pair_key]["i2c"]["connectionId"] <= connection["connectionId"]
        ):
            continue
        options[pair_key] = {
            "buildProfileId": "platformio-arduino-esp32-v1",
            "analysisProfileId": "python-analysis-v1",
            "components": [
                {"componentRoleId": c["componentRoleId"], "candidateId": c["candidateId"]}
                for c in selected
            ],
            "i2c": {
                "connectionId": connection["connectionId"],
                "sdaPin": specs.get("gpio-sda", 21),
                "sclPin": specs.get("gpio-scl", 22),
            },
        }
    if len(options) != 1:
        raise DefaultConfigurationError(
            "Default configuration requires one usable ESP32-DEVKIT-V1 + MPU6050 I2C binding; "
            "provide an explicit configuration."
        )
    return next(iter(options.values()))


async def propose_execution_plan_criteria(
    plan: dict[str, Any], package: dict[str, Any], gateway: Any, model_policy: Any
) -> None:
    """Optional live definitions; invalid/missing proposals leave platform fallback intact."""
    from nexus_contracts.validation.schema_validator import load_schemas_by_id
    from nexus_model_gateway import ModelGatewayError

    from .prompts.catalog import EXECUTION_PLAN_CRITERIA

    prompt = EXECUTION_PLAN_CRITERIA
    criterion_fields = load_schemas_by_id()[
        "https://nexus.local/schemas/artifacts/content/test-plan.v1.schema.json"
    ]["$defs"]["criterion"]["properties"]
    variants = []
    for kind, fields in {
        "numeric-comparison": ["metricId", "operator", "expectedValue", "unit"],
        "range": ["metricId", "minValue", "maxValue", "unit"],
        "exact-match": ["expectedValue"],
        "contains": ["marker"],
        "existence": ["outputName"],
        "structural-mapping": ["signal", "expectedMapping"],
    }.items():
        properties = {key: criterion_fields[key] for key in fields}
        properties["criterionType"] = {"type": "string", "enum": [kind]}
        if "expectedValue" in properties:
            properties["expectedValue"] = {
                "type": "number"
                if kind == "numeric-comparison"
                else ["string", "number", "boolean"]
            }
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": [key for key in properties if key != "unit"],
            }
        )
    try:
        generated = await gateway.generate_structured(
            task_name="propose-execution-plan-criteria",
            system_instructions=prompt.system_instructions,
            input_payload={
                "evaluableEvidence": EVALUABLE_EVIDENCE,
                "criterionSchema": load_schemas_by_id()[
                    "https://nexus.local/schemas/artifacts/content/test-plan.v1.schema.json"
                ]["$defs"]["criterion"],
                "objectives": plan["verificationObjectives"],
                "requirements": next(
                    a["content"]["requirements"]
                    for a in package["artifacts"]
                    if a["artifactType"] == "requirement-set"
                ),
            },
            output_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["objectives"],
                "properties": {
                    "objectives": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["objectiveId", "criterion", "verificationMethod"],
                            "properties": {
                                "objectiveId": {"type": "string"},
                                "criterion": {"anyOf": variants},
                                "verificationMethod": {"type": "string"},
                            },
                        },
                    }
                },
            },
            model_policy=model_policy,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
        )
    except ModelGatewayError:
        return
    if not isinstance(generated.parsed_output, dict) or set(generated.parsed_output) != {
        "objectives"
    }:
        return
    proposals = generated.parsed_output["objectives"]
    if not isinstance(proposals, list):
        return
    for objective in plan["verificationObjectives"]:
        matches = [
            p
            for p in proposals
            if isinstance(p, dict) and p.get("objectiveId") == objective["objectiveId"]
        ]
        if len(matches) != 1:
            continue
        proposal = matches[0]
        if (
            set(proposal) != {"objectiveId", "criterion", "verificationMethod"}
            or proposal.get("verificationMethod")
            not in {"analysis", "simulation", "execution-output", "firmware-test", "inspection"}
            or not evaluable_criterion_proposal(
                proposal.get("criterion"), proposal.get("verificationMethod")
            )
        ):
            continue
        objective.update({k: proposal[k] for k in ("criterion", "verificationMethod")})
