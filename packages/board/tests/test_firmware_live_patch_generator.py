from __future__ import annotations

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
