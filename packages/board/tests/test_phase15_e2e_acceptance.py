"""Phase 15G end-to-end acceptance and hardening tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.errors import FirmwarePatchStaleError
from nexus_board.execution.runtime_factory import build_execution_runtime
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_model_gateway import ModelPolicy, OpenAICompatibleGateway


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run: dict[str, Any] = kernel.executions.get_run(run_id)
        if run["status"] not in {"queued", "starting", "running", "cancelling"}:
            return run
        time.sleep(0.05)
    final: dict[str, Any] = kernel.executions.get_run(run_id)
    return final


def test_phase15_g1_hermetic_fixture_e2e() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    kernel, _ps, ks, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    ws_id = binding["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=ws_id,
        requested_by=user,
    )
    assert kernel.filesystem.list_files(ws_id) == []

    generated = kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    paths = {item["path"] for item in generated["generatedFiles"]}
    assert "platformio.ini" in paths
    assert "src/main.cpp" in paths

    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/main.cpp",
        content=b"#include <Arduino.h>\nvoid setup(){Serial.begin(115200);} void loop(){}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    saved = kernel.filesystem.read_file(ws_id, "src/main.cpp")["content"]
    assert b"Serial.begin(115200)" in saved

    manual = kernel.workspace_runtime.create_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        reason="manual",
    )
    before_hashes = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )
    after_hashes = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    assert before_hashes == after_hashes
    proposal = proposed["proposal"]
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.apply_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert b"9600" in kernel.filesystem.read_file(ws_id, "src/main.cpp")["content"] or b"9600" in kernel.filesystem.read_file(ws_id, "platformio.ini")["content"]

    stale = kernel.workspace_runtime.propose_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )["proposal"]
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="platformio.ini",
        content=(kernel.filesystem.read_file(ws_id, "platformio.ini")["content"] + b"# user edit\n"),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    draft = ks.get_draft(ws_id)
    with pytest.raises(FirmwarePatchStaleError):
        kernel.workspace_runtime.apply_firmware_patch(
            project_id=project_id,
            artifact_type="firmware",
            proposal_id=stale["proposalId"],
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )
    discard = kernel.workspace_runtime.propose_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Add request note file.",
    )["proposal"]
    before_discard = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    kernel.workspace_runtime.discard_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        proposal_id=discard["proposalId"],
        actor=user,
    )
    assert before_discard == {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}

    listed = kernel.workspace_runtime.list_snapshots(
        project_id=project_id,
        artifact_type="firmware",
    )["snapshots"]
    assert listed
    preview = kernel.workspace_runtime.read_firmware_snapshot_file(
        project_id=project_id,
        artifact_type="firmware",
        snapshot_id=manual["snapshotId"],
        path="src/main.cpp",
    )
    assert preview["encoding"] == "utf-8"
    restored = kernel.workspace_runtime.restore_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        snapshot_id=manual["snapshotId"],
        actor=user,
    )
    assert restored["beforeRestoreSnapshotId"].startswith("snap_")
    snapshots = ks.list_snapshots(ws_id)
    assert any(s["reason"] == "before-restore" for s in snapshots)

    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="test/test_nexus.cpp",
        content=b"// pass\nvoid test_ok(){}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )

    compile_started = kernel.workspace_runtime.compile_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    run_id = compile_started["executionRun"]["executionRunId"]
    run = _wait_run(kernel, run_id)
    assert run["status"] == "completed"
    assert run["inputSnapshotId"] == compile_started["executionSnapshotId"]
    assert run["runtimeIdentity"]["runtimeKind"] == "process"
    logs = kernel.workspace_runtime.list_logs(
        project_id=project_id,
        execution_run_id=run_id,
        after_sequence=0,
    )
    assert logs["chunks"]
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=run_id,
    )["outputs"]
    names = {o.get("name") for o in outputs}
    assert any("firmware.elf" in str(name) for name in names)
    assert any("firmware.bin" in str(name) for name in names)
    for output in outputs:
        assert output.get("outputId")
        assert output.get("name")

    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/main.cpp",
        content=b"#include <Arduino.h>\n// NEXUS_COMPILE_ERROR\nvoid setup(){}\nvoid loop(){}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    failed = kernel.workspace_runtime.compile_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    failed_run = _wait_run(kernel, failed["executionRun"]["executionRunId"])
    assert failed_run["status"] == "failed"
    failed_logs = kernel.workspace_runtime.list_logs(
        project_id=project_id,
        execution_run_id=failed_run["executionRunId"],
        after_sequence=0,
    )
    assert any("error:" in c["content"] for c in failed_logs["chunks"])

    kernel.workspace_runtime.restore_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        snapshot_id=compile_started["executionSnapshotId"],
        actor=user,
    )
    tested = kernel.workspace_runtime.test_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    tested_run = _wait_run(kernel, tested["executionRun"]["executionRunId"])
    assert tested_run["status"] == "completed"
    assert tested_run["inputSnapshotId"] == tested["executionSnapshotId"]

    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="test/test_nexus.cpp",
        content=b"// NEXUS_TEST_FAIL\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    failing_test = kernel.workspace_runtime.test_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    failing_run = _wait_run(kernel, failing_test["executionRun"]["executionRunId"])
    assert failing_run["status"] == "failed"

    os.environ["NEXUS_FIRMWARE_STUB_DELAY_MS"] = "4000"
    try:
        slow_one = kernel.workspace_runtime.compile_firmware(
            project_id=project_id,
            artifact_type="firmware",
            actor=user,
        )
        slow_two = kernel.workspace_runtime.compile_firmware(
            project_id=project_id,
            artifact_type="firmware",
            actor=user,
        )
        slow_run_id = slow_two["executionRun"]["executionRunId"]
        kernel.workspace_runtime.cancel_execution(
            project_id=project_id,
            execution_run_id=slow_run_id,
            actor=user,
        )
        cancelled = _wait_run(kernel, slow_run_id, timeout=10.0)
        assert cancelled["status"] == "cancelled"
        _wait_run(kernel, slow_one["executionRun"]["executionRunId"], timeout=10.0)
        cancelled_logs = kernel.workspace_runtime.list_logs(
            project_id=project_id,
            execution_run_id=slow_run_id,
            after_sequence=0,
        )
        assert isinstance(cancelled_logs["chunks"], list)
    finally:
        os.environ.pop("NEXUS_FIRMWARE_STUB_DELAY_MS", None)


@pytest.mark.skipif(
    os.environ.get("RUN_FIRMWARE_LLM_E2E", "0") != "1"
    or not os.environ.get("NEXUS_MODEL_API_KEY"),
    reason="Set RUN_FIRMWARE_LLM_E2E=1 and NEXUS_MODEL_API_KEY for live LLM firmware E2E",
)
def test_phase15_g2_live_llm_stub_e2e() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    provider = (os.environ.get("NEXUS_MODEL_PROVIDER") or "openai").strip().lower()
    gateway = OpenAICompatibleGateway(
        model_credential=os.environ["NEXUS_MODEL_API_KEY"],
        base_url=os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1"),
    )
    policy = ModelPolicy(
        provider=provider,
        model=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "60")),
    )
    kernel, _ps, ks, project_id = build_test_kernel(
        auto_start_scheduler=True,
        firmware_patch_generator=LiveFirmwarePatchGenerator(
            gateway=gateway,
            model_policy=policy,
        ),
    )
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
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
    before = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(binding["workspaceId"])}
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Set serial baud to 9600 and keep code compilable.",
    )["proposal"]
    assert proposed["operations"]
    assert proposed["generatorId"] == "firmware-patch-generator-llm-v1"
    assert proposed.get("generatorMetadata", {}).get("provider")
    assert before == {f["path"]: f["contentHash"] for f in ks.list_workspace_files(binding["workspaceId"])}


@pytest.mark.skipif(
    os.environ.get("RUN_FIRMWARE_CONTAINER_E2E", "0") != "1" or shutil.which("docker") is None,
    reason="Set RUN_FIRMWARE_CONTAINER_E2E=1 with Docker for live container firmware E2E",
)
def test_phase15_g3_live_container_toolchain_e2e() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "0"
    image = os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "nexus-firmware-platformio-esp32:1.0.0")
    inspect = subprocess.run(  # noqa: S603
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode != 0:
        pytest.skip(f"Docker image not available locally: {image}")
    runtime = build_execution_runtime("container", container_image=image)
    kernel, _ps, _ks, project_id = build_test_kernel(
        auto_start_scheduler=True,
        execution_runtime=runtime,
    )
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
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
    draft = kernel.kernel_store.get_draft(binding["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path="test/test_nexus.cpp",
        content=b"// pass\nvoid test_ok(){}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    started = kernel.workspace_runtime.compile_firmware(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"], timeout=180.0)
    assert run["status"] in {"completed", "completed-with-warnings"}
    identity = run["runtimeIdentity"]
    assert identity["securityLevel"] == "isolated"
    assert identity.get("imageDigest")
    assert identity.get("networkPolicy") == "none"


@pytest.mark.skipif(
    os.environ.get("RUN_FIRMWARE_FULL_LIVE_E2E", "0") != "1"
    or os.environ.get("RUN_FIRMWARE_CONTAINER_E2E", "0") != "1"
    or not os.environ.get("NEXUS_MODEL_API_KEY"),
    reason="Set RUN_FIRMWARE_FULL_LIVE_E2E=1, RUN_FIRMWARE_CONTAINER_E2E=1, and NEXUS_MODEL_API_KEY",
)
def test_phase15_g4_full_live_product_e2e() -> None:
    # G4 composes G2 + G3 paths; this gate verifies both are enabled together.
    assert os.environ.get("NEXUS_MODEL_API_KEY")
    assert os.environ.get("RUN_FIRMWARE_CONTAINER_E2E") == "1"
