"""Version compatibility and referential integrity for initialization review plans."""

from copy import deepcopy
from pathlib import Path

import pytest
from nexus_contracts.validation.execution_plan_validator import validate_execution_plan
from nexus_contracts.validation.project_package_validator import load_project_package_bundle
from nexus_contracts.validation.schema_validator import validate_against_schema_id


@pytest.fixture
def package():
    folder = Path(__file__).parents[1] / "examples/valid/esp32-imu-circuit-simulation"
    bundle = load_project_package_bundle(folder)
    artifacts = bundle["artifact_envelopes"]
    req_art = next(a for a in artifacts if a["artifactType"] == "requirement-set")
    comp_art = next(a for a in artifacts if a["artifactType"] == "component-plan")
    reqs = req_art["content"]["requirements"]
    plan = {
        "schemaVersion": "1.0.0",
        "status": "proposed",
        "basisProjectStateVersion": 1,
        "sourceArtifacts": [
            {"artifactId": a["artifactId"], "artifactVersion": a["artifactVersion"]}
            for a in artifacts
        ],
        "requirements": [
            {"artifactId": req_art["artifactId"], "entityId": r["requirementId"]} for r in reqs
        ],
        "assumptions": [
            {"artifactId": a["artifactId"], "entityId": item["assumptionId"]}
            for a in artifacts
            for item in a["content"].get("assumptions", [])
            if isinstance(item, dict) and "assumptionId" in item
        ],
        "interfaces": [],
        "components": [
            {"artifactId": comp_art["artifactId"], "entityId": role["componentRoleId"]}
            for role in comp_art["content"]["componentRoles"]
        ],
        "openDecisionIds": [
            q["questionId"] for q in bundle["open_questions"] if q["status"] == "open"
        ],
        "workspaces": [
            {
                "workspaceKey": "requirements",
                "artifactType": "requirement-set",
                "availability": "artifact-available",
            },
            {"workspaceKey": "firmware", "artifactType": "firmware", "availability": "planned"},
        ],
        "verificationObjectives": [
            {
                "objectiveId": f"objective-{i}",
                "requirementId": r["requirementId"],
                "workspaceKey": "requirements",
                "method": "Review",
                "acceptanceCriteria": [],
            }
            for i, r in enumerate(reqs)
        ],
        "steps": [
            {
                "stepId": "review",
                "title": "Review plan",
                "dependsOn": [],
                "workspaceKeys": ["requirements"],
                "objectiveIds": ["objective-0"],
                "requiresApproval": True,
            }
        ],
    }
    project = deepcopy(bundle["project"])
    project["executionPlan"] = plan
    return {"project": project, "artifacts": artifacts, "openQuestions": bundle["open_questions"]}


def test_plan_and_legacy_project_compatibility(package):
    project = package["project"]
    assert not validate_execution_plan(
        project["executionPlan"], package["artifacts"], package["openQuestions"]
    )
    schema = "https://nexus.local/schemas/project/project.v1.schema.json"
    assert not validate_against_schema_id(project, schema)
    legacy = deepcopy(project)
    del legacy["executionPlan"]
    assert not validate_against_schema_id(legacy, schema)
    assert all(s["requiresApproval"] for s in project["executionPlan"]["steps"])
    assert (
        next(w for w in project["executionPlan"]["workspaces"] if w["artifactType"] == "firmware")[
            "availability"
        ]
        == "planned"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "requirement",
        "workspace",
        "dependency",
        "objective",
        "artifact",
        "entity",
        "decision",
        "version",
        "duplicate",
        "assumption",
        "interface",
        "omitted-requirement",
    ],
)
def test_rejects_invalid_execution_plan(package, mutation):
    plan = deepcopy(package["project"]["executionPlan"])
    if mutation == "requirement":
        plan["verificationObjectives"][0]["requirementId"] = "missing"
    elif mutation == "workspace":
        plan["verificationObjectives"][0]["workspaceKey"] = "missing"
    elif mutation == "dependency":
        plan["steps"][0]["dependsOn"] = ["analysis"]
    elif mutation == "objective":
        plan["steps"][0]["objectiveIds"] = ["missing"]
    elif mutation == "artifact":
        plan["sourceArtifacts"][0]["artifactVersion"] += 1
    elif mutation == "entity":
        plan["components"][0]["entityId"] = "missing"
    elif mutation == "decision":
        plan["openDecisionIds"] = ["missing"]
    elif mutation in {"assumption", "interface"}:
        field = "assumptions" if mutation == "assumption" else "interfaces"
        plan[field].append(
            {"artifactId": plan["sourceArtifacts"][0]["artifactId"], "entityId": "missing"}
        )
    elif mutation == "omitted-requirement":
        plan["requirements"].pop()
    elif mutation == "version":
        plan["schemaVersion"] = "2.0.0"
    else:
        plan["steps"].append(plan["steps"][0])
    assert validate_execution_plan(plan, package["artifacts"], package["openQuestions"])


def test_old_golden_project_still_valid():
    import json

    path = Path(__file__).parents[1] / "examples/valid/esp32-imu-circuit-simulation/project.json"
    assert not validate_against_schema_id(
        json.loads(path.read_text()), "https://nexus.local/schemas/project/project.v1.schema.json"
    )
