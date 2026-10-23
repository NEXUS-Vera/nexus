from __future__ import annotations

from typing import Any

from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_board.firmware.patch import assemble_firmware_generation_context
from nexus_model_gateway import FakeModelGateway, ModelPolicy


def test_live_generator_materializes_replace_operation() -> None:
    kernel, project_store, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    snap = kernel.workspace_runtime.create_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        reason="test",
    )
    base_snapshot = kernel.kernel_store.get_snapshot(snap["snapshotId"])
    context = assemble_firmware_generation_context(
        project_store=project_store,
        project_id=project_id,
        base_snapshot=base_snapshot,
        requested_change="Set serial baud to 9600",
        file_store=kernel.filesystem.file_store,
    )
    gateway = FakeModelGateway()
    gateway.set_script(
        "firmware.patch-proposal",
        lambda _task, _payload, _schema: {
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "platformio.ini",
                    "content": "[env:nexus]\nmonitor_speed = 9600\n",
                }
            ]
        },
    )
    generator = LiveFirmwarePatchGenerator(
        gateway=gateway,
        model_policy=ModelPolicy(provider="fake", model="fake-model"),
    )
    out = generator.generate(context=context, base_snapshot=base_snapshot)
    assert out["generatorId"] == "firmware-patch-generator-llm-v1"
    assert out["operations"][0]["operationType"] == "replace-file"
    assert out["operations"][0]["expectedBaseHash"].startswith("sha256:")
    assert out["operations"][0]["contentHash"].startswith("sha256:")


def test_context_rejects_oversized_approved_artifacts_and_missing_sources() -> None:
    """Do not silently truncate approved decisions or substitute unreviewed context."""
    import pytest
    from nexus_board.errors import FirmwarePatchGenerationError
    from nexus_board.firmware.patch import MAX_CONTEXT_ARTIFACT_BYTES
    from nexus_persistence.errors import ArtifactNotFoundError

    class Store:
        def __init__(self):
            self.plan: dict[str, Any] = {
                "artifactType": "execution-plan",
                "artifactVersion": 1,
                "artifactId": "plan",
                "approvalStatus": "user-approved",
                "content": {"plan": {"sourceArtifacts": []}},
            }

        def get_artifact(self, project_id, artifact_type, *, version=None):
            if artifact_type == "execution-plan":
                return self.plan
            if artifact_type == "requirement-set" and version == 1:
                return {
                    "artifactType": artifact_type,
                    "artifactVersion": 1,
                    "artifactId": "reviewed-requirements",
                    "content": {"requirement": "reviewed"},
                }
            raise ArtifactNotFoundError("missing")

    class Files:
        def get(self, content_hash: str) -> bytes:
            raise AssertionError("No file reads expected")

    store = Store()
    snapshot = {
        "snapshotId": "base",
        "content": {"kind": "filesystem", "filesystemManifest": {"entries": []}},
    }

    def assemble(change="author firmware"):
        return assemble_firmware_generation_context(
            project_store=store,
            project_id="project",
            base_snapshot=snapshot,
            requested_change=change,
            file_store=Files(),
        )

    store.plan["content"]["plan"]["sourceArtifacts"] = [
        {"artifactId": "reviewed-requirements", "artifactVersion": 1}
    ]
    assert assemble()["artifacts"]["requirement-set"] == {"requirement": "reviewed"}
    store.plan["content"]["padding"] = "x" * MAX_CONTEXT_ARTIFACT_BYTES
    with pytest.raises(FirmwarePatchGenerationError, match="artifact context exceeds"):
        assemble()
    del store.plan["content"]["padding"]
    store.plan["content"]["plan"]["sourceArtifacts"] = [
        {"artifactId": "missing", "artifactVersion": 1}
    ]
    with pytest.raises(FirmwarePatchGenerationError, match="source artifact is unavailable"):
        assemble()
    store.plan["approvalStatus"] = "pending"
    with pytest.raises(FirmwarePatchGenerationError, match="user-approved"):
        assemble()
    with pytest.raises(FirmwarePatchGenerationError, match="request exceeds"):
        assemble("x" * 8193)

    store.plan["approvalStatus"] = "user-approved"
    store.plan["content"]["plan"]["sourceArtifacts"] = []
    snapshot["content"]["filesystemManifest"]["entries"] = [
        {"path": f"src/file_{index}.cpp"} for index in range(257)
    ]
    with pytest.raises(FirmwarePatchGenerationError, match="snapshot exceeds"):
        assemble()
