"""Bounded, provider-independent plan review and scaffold materialization.

Uses artifact revision governance; never interprets arbitrary follow-up prose or
runs tools. Candidate selection authorizes a prototype, not physical validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nexus_board.analysis.scaffold import get_analysis_scaffold_profile
from nexus_board.errors import (
    ArtifactVersionConflictError,
    CommandValidationError,
    DraftEditLeaseHeldError,
    ProjectStateConflictError,
)
from nexus_board.firmware.scaffold import get_firmware_scaffold_profile
from nexus_board.ids import content_digest, new_id, utc_now_iso
from nexus_board.services.draft_lease import is_lease_active
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)
from nexus_contracts.validation.execution_plan_validator import validate_execution_plan
from nexus_contracts.validation.schema_validator import validate_against_schema_id
from nexus_persistence.errors import ArtifactNotFoundError
from nexus_persistence.file_store.hashing import blob_digest

from nexus_embedded_systems.workflows.project_initialization.execution_plan import (
    compose_execution_plan,
)

CONTENT_SCHEMA = (
    "https://nexus.local/schemas/artifacts/content/actionable-execution-plan.v1.schema.json"
)


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
        raise CommandValidationError(
            "Default configuration requires one usable ESP32-DEVKIT-V1 + MPU6050 I2C binding; "
            "provide an explicit configuration."
        )
    return next(iter(options.values()))


class ExecutionPlanWorkflow:
    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel
        self.projects = kernel.project_store

    def propose(
        self,
        project_id: str,
        actor: dict[str, Any],
        base: int,
        plan_version: int,
        configuration: Any,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = self.projects.get_current_state(project_id)
        if current["project"]["currentStateVersion"] != base:
            raise ProjectStateConflictError("Stale plan basis.")
        previous = next(
            (a for a in current["artifacts"] if a["artifactType"] == "execution-plan"), None
        )
        if plan_version != (previous["artifactVersion"] if previous else 0):
            raise ArtifactVersionConflictError("Stale plan version.")
        current["artifacts"] = [
            a for a in current["artifacts"] if a["artifactType"] != "execution-plan"
        ]
        content = {
            "plan": plan or compose_execution_plan(current),
            "configuration": (
                derive_default_configuration(current) if configuration is None else configuration
            ),
        }
        self.validate_revision(project_id, "execution-plan", content, False, actor)
        created = self.kernel.workspaces.create_if_missing(
            project_id=project_id,
            artifact_type="execution-plan",
            actor=actor,
            initial_content=content,
        )
        workspace = created["workspace"]
        self.kernel.workspaces.acquire_edit_lease(
            workspace_id=workspace["workspaceId"], actor=actor
        )
        updated = self.kernel.workspaces.update_draft(
            workspace_id=workspace["workspaceId"],
            content=content,
            expected_draft_version=created["draft"]["draftVersion"],
            actor=actor,
            base_artifact_version=workspace["baseArtifactVersion"],
            base_project_state_version=base,
        )
        snapshot = self.kernel.workspaces.create_snapshot(
            workspace_id=workspace["workspaceId"],
            reason="execution-plan-review",
            actor=actor,
        )
        result = self.kernel.dispatch(
            {
                "schemaVersion": "1.0.0",
                "commandId": new_id("cmd"),
                "commandType": "artifact.propose-revision",
                "projectId": project_id,
                "workspaceId": workspace["workspaceId"],
                "artifactId": workspace["artifactId"],
                "baseArtifactVersion": workspace["baseArtifactVersion"],
                "baseProjectStateVersion": base,
                "requestedBy": actor,
                "requestedAt": snapshot["createdAt"],
                "input": {"snapshotId": snapshot["snapshotId"], "consequenceLevel": "high"},
            }
        )
        return {
            "schemaVersion": "1.0.0",
            "content": content,
            "commandResult": result,
            "workspace": updated["workspace"],
        }

    def retry_materialization(
        self, project_id: str, actor: dict[str, Any], plan_artifact_id: Any, base: int
    ) -> dict[str, Any]:
        artifact = self.projects.get_artifact(project_id, "execution-plan")
        project = self.projects.get_project(project_id)
        materialized_state = artifact["content"]["plan"]["basisProjectStateVersion"] + 1
        try:
            test_plan = self.projects.get_artifact(project_id, "test-plan")
        except ArtifactNotFoundError:
            test_plan = None
        if test_plan and (test_plan["content"].get("provenance") or {}).get("notes") == (
            f"Seeded from approved plan {artifact['artifactId']}"
        ):
            materialized_state += 1
        if (
            plan_artifact_id != artifact["artifactId"]
            or base != project["currentStateVersion"]
            or project["currentStateVersion"] != materialized_state
        ):
            raise ProjectStateConflictError("Approved plan is stale.")
        self.materialize(project_id, artifact, actor)
        return {
            "schemaVersion": "1.0.0",
            "status": "materialized",
            "planArtifactId": artifact["artifactId"],
            "executionMode": "deterministic-scaffold",
        }

    def validate_revision(
        self,
        project_id: str,
        kind: str,
        content: dict[str, Any],
        accepting: bool,
        actor: dict[str, Any],
    ) -> None:
        if kind != "execution-plan":
            return
        errors = validate_against_schema_id(content, CONTENT_SCHEMA)
        if errors:
            raise CommandValidationError("Invalid actionable execution plan: " + errors[0].message)
        current = self.projects.get_current_state(project_id)
        plan = content["plan"]
        if plan["basisProjectStateVersion"] != current["project"]["currentStateVersion"]:
            raise ProjectStateConflictError(
                "Execution plan basis is stale; review a refreshed plan."
            )
        artifacts = [a for a in current["artifacts"] if a["artifactType"] != "execution-plan"]
        errors = validate_execution_plan(plan, artifacts, current["openQuestions"])
        if errors:
            raise CommandValidationError(errors[0].message)
        by_type = {a["artifactType"]: a["content"] for a in artifacts}
        config = content["configuration"]
        candidates = {c["candidateId"]: c for c in by_type["component-plan"]["candidates"]}
        chosen = []
        roles = set()
        for selection in config["components"]:
            candidate = candidates.get(selection["candidateId"])
            if (
                candidate is None
                or candidate["componentRoleId"] != selection["componentRoleId"]
                or candidate["candidateState"] in {"blocked", "rejected", "superseded"}
                or selection["componentRoleId"] in roles
            ):
                raise CommandValidationError(
                    "Selection must name distinct current, usable candidates."
                )
            roles.add(selection["componentRoleId"])
            chosen.append(candidate)
        # Exact documented fixture surrogates; never rewrite candidate provenance.
        fixture_equivalents = {
            ("fixture", "Fixture Compute", "FX-MCU-32"): "ESP32-DEVKIT-V1",
            ("fixture", "Fixture Motion", "FX-IMU-200"): "MPU6050",
        }
        supported_parts = {
            fixture_equivalents.get(
                (c.get("source"), c.get("manufacturer"), c["partNumber"]),
                c["partNumber"].upper(),
            )
            for c in chosen
        }
        if supported_parts != {"ESP32-DEVKIT-V1", "MPU6050"}:
            raise CommandValidationError(
                "Only ESP32-DEVKIT-V1 + MPU6050 materialization is supported."
            )
        electrical = by_type.get("electrical-architecture", {})
        connection = next(
            (
                c
                for c in electrical.get("connections", [])
                if c["connectionId"] == config["i2c"]["connectionId"]
            ),
            None,
        )
        if (
            connection is None
            or connection["interfaceType"] != "i2c"
            or connection["status"] in {"unresolved", "needs-resolution"}
        ):
            raise CommandValidationError(
                "Select an existing I2C connection; unresolved buses cannot be scaffolded."
            )
        nodes = {n["nodeId"]: n for n in electrical["nodes"]}
        endpoint_roles = set()
        for key in ("fromNodeId", "toNodeId"):
            endpoint_roles.update(nodes.get(connection[key], {}).get("componentRoleIds", []))
        endpoint_candidates = {
            nodes.get(connection[key], {}).get("componentCandidateId")
            for key in ("fromNodeId", "toNodeId")
        }
        if endpoint_candidates != {c["candidateId"] for c in chosen}:
            raise CommandValidationError("Electrical endpoints must bind the selected candidates.")
        for candidate in chosen:
            specs = {spec["specKey"]: spec["value"] for spec in candidate["specifications"]}
            for spec_key, pin_key in (("gpio-sda", "sdaPin"), ("gpio-scl", "sclPin")):
                if spec_key in specs and specs[spec_key] != config["i2c"][pin_key]:
                    raise CommandValidationError(
                        "Plan pins conflict with component specifications."
                    )
        if not roles <= endpoint_roles:
            raise CommandValidationError("I2C connection must link the selected component roles.")
        if config["i2c"]["sdaPin"] == config["i2c"]["sclPin"]:
            raise CommandValidationError("SDA and SCL must use distinct pins.")
        if not {"firmware", "analysis"} <= {w["artifactType"] for w in plan["workspaces"]}:
            raise CommandValidationError("Plan must include firmware and analysis workspaces.")
        requirements = {r["requirementId"]: r for r in by_type["requirement-set"]["requirements"]}
        for objective in plan["verificationObjectives"]:
            req = requirements[objective["requirementId"]]
            if objective["acceptanceCriteria"] != (
                req.get("acceptanceCriteria") or []
            ) or objective["method"] != (
                req.get("verificationMethod") or "Verification method requires review."
            ):
                raise CommandValidationError(
                    "Objectives must match the current requirement criteria and methods."
                )
        if accepting:
            self._preflight(project_id, self.render(content), content)
            self._check_leases(project_id, actor)

    def render(self, content: dict[str, Any]) -> dict[str, dict[str, bytes]]:
        config = content["configuration"]
        firmware = {
            f.path: f.content for f in get_firmware_scaffold_profile(config["buildProfileId"]).files
        }
        analysis = {
            f.path: f.content
            for f in get_analysis_scaffold_profile(config["analysisProfileId"]).files
        }
        # Validation bounds approved plans to ESP32-DEVKIT-V1 + MPU6050.
        # Generic scaffold generation keeps python-analysis-v1 unchanged.
        analysis["analysis.py"] = Path(__file__).with_name("imu_analysis.py").read_bytes()
        # This is deterministic workspace preparation, not sensor firmware generation (W3).
        firmware["include/nexus_plan.h"] = (
            "#pragma once\n"
            f"constexpr int NEXUS_SDA_PIN = {config['i2c']['sdaPin']};\n"
            f"constexpr int NEXUS_SCL_PIN = {config['i2c']['sclPin']};\n"
        ).encode()
        firmware["src/main.cpp"] = (
            b'#include <Arduino.h>\n#include <Wire.h>\n#include "nexus_plan.h"\n\n'
            b"void setup() {\n    Serial.begin(115200);\n"
            b"    Wire.begin(NEXUS_SDA_PIN, NEXUS_SCL_PIN);\n}\n\nvoid loop() {\n}\n"
        )
        context = json.dumps(content, sort_keys=True, indent=2).encode() + b"\n"
        firmware["nexus/approved-plan.json"] = context
        analysis["nexus/approved-plan.json"] = context
        return {"firmware": firmware, "analysis": analysis}

    def _is_unmodified_scaffold(
        self, kind: str, record: dict[str, Any], content: dict[str, Any]
    ) -> bool:
        config = content["configuration"]
        profile = (
            get_firmware_scaffold_profile(config["buildProfileId"])
            if kind == "firmware"
            else get_analysis_scaffold_profile(config["analysisProfileId"])
        )
        return (
            record.get("origin") == "GENERATED"
            and record.get("generatedFrom") == profile.generated_from
            and not record.get("modifiedByUser", True)
            and any(
                spec.path == record["path"] and spec.content_hash == record["contentHash"]
                for spec in profile.files
            )
        )

    def _preflight(
        self, project_id: str, files: dict[str, dict[str, bytes]], content: dict[str, Any]
    ) -> None:
        for kind, expected in files.items():
            existing = self.kernel.workspaces.get_or_none(project_id, kind)
            if existing is None:
                continue
            for record in self.kernel.filesystem.list_files(existing["workspace"]["workspaceId"]):
                if record["path"] not in expected or record["contentHash"] != blob_digest(
                    expected[record["path"]]
                ):
                    if self._is_unmodified_scaffold(kind, record, content):
                        continue
                    raise CommandValidationError(
                        f"Materialization conflicts with {kind}/{record['path']}. "
                        f"Open the {kind} workspace, copy the file contents to a safe "
                        "location, then delete the conflicting file and retry plan approval. "
                        "User-edited files are never overwritten."
                    )

    def _check_leases(self, project_id: str, actor: dict[str, Any]) -> None:
        for kind in ("firmware", "analysis"):
            existing = self.kernel.workspaces.get_or_none(project_id, kind)
            if existing:
                lease = existing["draft"].get("editLease")
                if is_lease_active(lease) and lease["ownerActorId"] != actor["actorId"]:
                    raise DraftEditLeaseHeldError("Workspace lease is held by another actor.")

    def _seed_test_plan(self, project_id: str, artifact: dict[str, Any]) -> None:
        try:
            self.projects.get_artifact(project_id, "test-plan")
            return
        except ArtifactNotFoundError:
            pass
        requirements = self.projects.get_artifact(project_id, "requirement-set")["content"][
            "requirements"
        ]
        methods = {
            "inspection",
            "simulation",
            "firmware-test",
            "analysis",
            "execution-output",
            "manual",
        }
        cases = [
            {
                "testId": new_id("test"),
                "displayId": f"T{index}",
                "title": objective["objectiveId"],
                "linkedRequirementIds": [objective["requirementId"]],
                "verificationMethod": objective["method"]
                if objective["method"] in methods
                else "manual",
                "description": objective["method"],
                "expectedResult": "\n".join(objective["acceptanceCriteria"])
                or "Acceptance criteria require review.",
                "status": "planned",
            }
            for index, objective in enumerate(
                artifact["content"]["plan"]["verificationObjectives"], 1
            )
        ]
        content = {
            "schemaVersion": "1.0.0",
            "testPlanId": new_id("tplan"),
            "testCases": cases,
            "coverageSummary": compute_test_plan_coverage_summary(
                compute_requirement_coverage(requirements=requirements, test_cases=cases)
            ),
            "provenance": {
                "generatedBy": "derived",
                "notes": f"Seeded from approved plan {artifact['artifactId']}",
            },
        }
        seeded = {
            key: artifact[key]
            for key in ("schemaVersion", "projectId", "sourceTurnId", "workflowRunId", "createdBy")
        }
        now = utc_now_iso()
        seeded.update(
            artifactId=new_id("art"),
            artifactType="test-plan",
            artifactVersion=1,
            contentSchemaVersion="1.0.0",
            lifecycleStatus="ready",
            evidenceStatus="unverified",
            approvalStatus="not-required",
            createdAt=now,
            updatedAt=now,
            content=content,
        )
        errors = validate_against_schema_id(
            seeded, "https://nexus.local/schemas/artifacts/artifact.v1.schema.json"
        )
        if errors:
            raise CommandValidationError("Invalid seeded Test Plan: " + errors[0].message)
        project = self.projects.get_project(project_id)
        # The derived artifact advances state once; retries retain the existing plan.
        self.projects.apply_accepted_artifact_revision(
            project_id=project_id,
            new_artifact=seeded,
            next_state_version=project["currentStateVersion"] + 1,
            updated_at=now,
            expected_project_state_version=project["currentStateVersion"],
        )

    def materialize(self, project_id: str, artifact: dict[str, Any], actor: dict[str, Any]) -> None:
        """Retry-safe approved writes, replacing only verified, unmodified scaffold output."""
        if actor.get("actorType") != "user" or artifact.get("approvalStatus") != "user-approved":
            raise CommandValidationError("User-approved plan required for materialization.")
        content = artifact["content"]
        files = self.render(content)
        self._preflight(project_id, files, content)
        self._check_leases(project_id, actor)
        for kind, expected in files.items():
            binding = self.kernel.workspace_runtime.resolve_binding(
                project_id=project_id, artifact_type=kind, actor=actor
            )
            workspace_id = binding["workspaceId"]
            self.kernel.workspaces.acquire_edit_lease(workspace_id=workspace_id, actor=actor)
            for path, data in expected.items():
                record = self.kernel.kernel_store.get_workspace_file(workspace_id, path)
                if record is not None and not self._is_unmodified_scaffold(kind, record, content):
                    continue
                draft = self.kernel.kernel_store.get_draft(workspace_id)
                self.kernel.filesystem.write_file(
                    workspace_id=workspace_id,
                    path=path,
                    content=data,
                    actor=actor,
                    expected_draft_version=draft["draftVersion"],
                    base_artifact_version=binding["baseArtifactVersion"],
                    base_project_state_version=self.projects.get_project(project_id)[
                        "currentStateVersion"
                    ],
                    origin="GENERATED",
                    write_policy="USER_EDITABLE",
                    generated_from=f"execution-plan:{artifact['artifactId']}",
                    media_type="application/json" if path.endswith(".json") else "text/plain",
                )
            self.kernel.workspaces.release_edit_lease(workspace_id=workspace_id, actor=actor)
        self._seed_test_plan(project_id, artifact)
        self.kernel.ledger.append(
            project_id=project_id,
            event_type="workspace.plan-materialized",
            actor=actor,
            subject_type="artifact",
            subject_id=artifact["artifactId"],
            payload={
                "planArtifactId": artifact["artifactId"],
                "contentDigest": content_digest(content),
                "executionMode": "deterministic-scaffold",
                "workspaceTypes": list(files),
            },
        )
