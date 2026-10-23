"""W6 scripted gateway regression evidence for current authoring context versions."""

from typing import Any

import pytest
from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
from nexus_board.analysis.patch import assemble_analysis_generation_context
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_board.firmware.patch import assemble_firmware_generation_context
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from nexus_persistence.errors import ArtifactNotFoundError


@pytest.mark.parametrize("kind", ["firmware", "analysis"])
def test_authoring_names_current_versions_and_snapshot_inputs(kind):
    # An approved plan may cite an older requirement; both reviewed and current
    # context must be visible, rather than silently replacing either one.
    artifacts = {
        name: {
            "artifactType": name,
            "artifactId": name + "-current",
            "artifactVersion": 3,
            "content": {"value": name + " current"},
        }
        for name in ("requirement-set", "component-plan", "electrical-architecture", "test-plan")
    }
    reviewed = {
        **artifacts["requirement-set"],
        "artifactId": "reviewed",
        "artifactVersion": 1,
        "content": {"value": "reviewed requirement"},
    }
    artifacts["execution-plan"] = {
        "artifactType": "execution-plan",
        "artifactId": "plan-current",
        "artifactVersion": 2,
        "approvalStatus": "user-approved",
        "content": {
            "plan": {"sourceArtifacts": [{"artifactId": "reviewed", "artifactVersion": 1}]}
        },
    }

    class Store:
        def get_artifact(
            self, project_id: str, artifact_type: str, *, version: int | None = None
        ) -> dict[str, Any]:
            name = artifact_type
            if name == "requirement-set" and version == 1:
                return reviewed
            if name in artifacts and version is None:
                return artifacts[name]
            raise ArtifactNotFoundError("missing")

    class Files:
        def get(self, content_hash: str) -> bytes:
            raise AssertionError("No source file reads expected")

    snapshot = {
        "snapshotId": "snapshot-current",
        "content": {
            "kind": "filesystem",
            "filesystemManifest": {
                "entries": [
                    {
                        "path": "data/serial.log",
                        "contentHash": "sha256:observation",
                        "sizeBytes": 3,
                        "generatedFrom": "imported-output:out_current",
                    }
                ]
            },
        },
    }
    assembler = (
        assemble_firmware_generation_context
        if kind == "firmware"
        else assemble_analysis_generation_context
    )
    context = assembler(
        project_store=Store(),
        project_id="project",
        base_snapshot=snapshot,
        requested_change="author current workspace",
        file_store=Files(),
    )
    refs = context["inputArtifactReferences"]
    for artifact in artifacts.values():
        assert {k: artifact[k] for k in ("artifactType", "artifactId", "artifactVersion")} in refs
    gateway = FakeModelGateway()

    def reply(task, payload, schema):
        assert payload["inputArtifactReferences"] == refs
        assert payload["baseSnapshotId"] == "snapshot-current"
        current = payload["currentArtifacts"] if kind == "firmware" else payload["artifacts"]
        assert current["requirement-set"] == artifacts["requirement-set"]["content"]
        if kind == "analysis":
            assert payload["snapshotFiles"][0]["generatedFrom"] == "imported-output:out_current"
        else:
            assert payload["artifacts"]["requirement-set"] == reviewed["content"]
        return {
            "operations": [
                {
                    "operationType": "create-file",
                    "path": "src/main.cpp" if kind == "firmware" else "analysis.py",
                    "content": "// regression" if kind == "firmware" else "print(1)",
                }
            ]
        }

    gateway.set_script(kind + ".patch-proposal", reply)
    generator = LiveFirmwarePatchGenerator if kind == "firmware" else LiveAnalysisPatchGenerator
    result = generator(
        gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
    ).generate(
        context=context,
        base_snapshot=snapshot,
    )
    assert result["generatorMetadata"]["mode"] == "regression"

    from nexus_board.errors import AnalysisPatchGenerationError, FirmwarePatchGenerationError

    artifacts["requirement-set"]["content"] = {"oversized": "x" * 131_073}
    with pytest.raises(
        (AnalysisPatchGenerationError, FirmwarePatchGenerationError), match="context exceeds"
    ):
        assembler(
            project_store=Store(),
            project_id="project",
            base_snapshot=snapshot,
            requested_change="author current workspace",
            file_store=Files(),
        )
