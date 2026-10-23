"""Derive a review proposal from canonical initialization artifacts, without executing it."""

from __future__ import annotations

from typing import Any


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
