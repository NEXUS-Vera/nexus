"""Phase 16G end-to-end acceptance and hardening tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
from nexus_board.errors import AnalysisPatchStaleError, WorkspacePathError
from nexus_board.execution.runtime_factory import build_execution_runtime
from nexus_model_gateway import ModelPolicy, OpenAICompatibleGateway

SENSOR_CSV = b"""time_s,accel_x
0,0.1
1,0.4
2,0.2
3,0.8
4,0.5
"""

ANALYSIS_REQUEST = (
    "Analyze data/sensor.csv. Compute summary statistics for accel_x, "
    "write them to outputs/summary.json, write a row-wise processed CSV to "
    "outputs/processed.csv, and save a plot of accel_x versus time_s to "
    "outputs/accel_plot.png."
)


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 20.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = kernel.executions.get_run(run_id)
        if run["status"] not in {"queued", "starting", "running", "cancelling"}:
            return run
        time.sleep(0.05)
    return kernel.executions.get_run(run_id)


def _setup_analysis(kernel: Any, project_id: str, user: dict[str, Any]) -> dict[str, Any]:
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    return dict(binding)


def test_phase16_g1_hermetic_fixture_e2e() -> None:
    """Mandatory hermetic G1: fixture generation + ProcessRuntime + analysis stub."""
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
    os.environ.pop("NEXUS_ANALYSIS_STUB_DELAY_MS", None)
    kernel, _ps, ks, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    binding = _setup_analysis(kernel, project_id, user)
    ws_id = binding["workspaceId"]
    assert kernel.filesystem.list_files(ws_id) == []

    # Scaffold
    generated = kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    paths = {item["path"] for item in generated["generatedFiles"]}
    assert "analysis.py" in paths
    assert "README.md" in paths
    scaffold_hashes = {item["path"]: item["contentHash"] for item in generated["generatedFiles"]}
    again = kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=int(ks.get_draft(ws_id)["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert again.get("status") in {"already-generated", "generated", None} or again.get(
        "generatedFiles"
    )
    for item in again.get("generatedFiles") or []:
        if item["path"] in scaffold_hashes:
            assert item["contentHash"] == scaffold_hashes[item["path"]]

    # Upload CSV
    draft = ks.get_draft(ws_id)
    upload = kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/sensor.csv",
        content=SENSOR_CSV,
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    assert upload["file"]["path"] == "data/sensor.csv"
    sensor = kernel.filesystem.read_file(ws_id, "data/sensor.csv")
    assert sensor["content"] == SENSOR_CSV
    assert upload["file"].get("origin") == "USER"

    # Path traversal rejected
    draft = ks.get_draft(ws_id)
    with pytest.raises(WorkspacePathError):
        kernel.workspace_runtime.write_analysis_input_file(
            project_id=project_id,
            artifact_type="analysis",
            path="../etc/passwd",
            content=b"x",
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )

    # Import ProducedOutput from a firmware compile (cross-artifact)
    fw_binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=fw_binding["artifactId"],
        workspace_id=fw_binding["workspaceId"],
        requested_by=user,
    )
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(fw_binding["baseArtifactVersion"]),
        base_project_state_version=int(fw_binding["baseProjectStateVersion"]),
    )
    compiled = kernel.workspace_runtime.compile_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    fw_run = _wait_run(kernel, compiled["executionRun"]["executionRunId"])
    assert fw_run["status"] == "completed"
    fw_outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=fw_run["executionRunId"],
    )["outputs"]
    assert fw_outputs
    import_source = fw_outputs[0]
    draft = ks.get_draft(ws_id)
    imported = kernel.workspace_runtime.import_produced_output_into_analysis_input(
        project_id=project_id,
        artifact_type="analysis",
        output_id=import_source["outputId"],
        path="data/imported.bin",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert imported["file"]["path"] == "data/imported.bin"
    assert imported["file"].get("origin") == "RUNTIME_OUTPUT"
    assert "imported-output:" in str(imported["file"].get("generatedFrom") or "")

    # Edit + manual snapshot
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=kernel.filesystem.read_file(ws_id, "analysis.py")["content"]
        + b"\n# edited for phase16\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    manual = kernel.workspace_runtime.create_snapshot(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        reason="manual",
    )
    assert manual["snapshotId"].startswith("snap_")

    # Patch propose (immutable) / apply / stale / discard
    before_hashes = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    proposed = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change=ANALYSIS_REQUEST,
    )
    after_propose = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    assert before_hashes == after_propose
    proposal = proposed["proposal"]
    assert proposal["baseSnapshotId"].startswith("snap_")
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.apply_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )

    stale = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change="Add a note about analysis.",
    )["proposal"]
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="README.md",
        content=kernel.filesystem.read_file(ws_id, "README.md")["content"] + b"\n# user edit\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    draft = ks.get_draft(ws_id)
    with pytest.raises(AnalysisPatchStaleError):
        kernel.workspace_runtime.apply_analysis_patch(
            project_id=project_id,
            artifact_type="analysis",
            proposal_id=stale["proposalId"],
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )

    discard = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change="Add request note file.",
    )["proposal"]
    before_discard = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    kernel.workspace_runtime.discard_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=discard["proposalId"],
        actor=user,
    )
    assert before_discard == {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}

    # Run current
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    assert started["operation"] == "analysis.run"
    snap_id = started["executionSnapshotId"]
    snapshots = ks.list_snapshots(ws_id)
    assert any(
        s["snapshotId"] == snap_id and s["reason"] == "before-analysis-run" for s in snapshots
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"])
    assert run["status"] == "completed"
    assert run["inputSnapshotId"] == snap_id
    assert run["runtimeIdentity"]["runtimeKind"] == "process"
    logs = kernel.workspace_runtime.list_logs(
        project_id=project_id,
        execution_run_id=run["executionRunId"],
        after_sequence=0,
    )
    assert logs["chunks"]
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=run["executionRunId"],
    )["outputs"]
    names = {o.get("name") for o in outputs}
    assert "outputs/results.json" in names
    assert "outputs/summary.json" in names
    assert "outputs/processed.csv" in names
    assert "outputs/accel_plot.png" in names
    assert "outputs/note.txt" in names
    for output in outputs:
        preview = kernel.workspace_runtime.preview_analysis_output(
            project_id=project_id,
            output_id=output["outputId"],
        )
        assert preview["previewKind"] in {"json", "csv", "image-png", "text", "unknown"}
        assert output.get("provenance")

    # Failure + traceback
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=b"# NEXUS_RUN_ERROR\nraise RuntimeError('boom')\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    failed = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    failed_run = _wait_run(kernel, failed["executionRun"]["executionRunId"])
    assert failed_run["status"] == "failed"
    failed_logs = kernel.workspace_runtime.list_logs(
        project_id=project_id,
        execution_run_id=failed_run["executionRunId"],
        after_sequence=0,
    )
    text = "".join(c["content"] for c in failed_logs["chunks"])
    assert "NEXUS_RUN_ERROR" in text or "Traceback" in text or "RuntimeError" in text
    failed_outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=failed_run["executionRunId"],
    )["outputs"]
    assert failed_outputs == []

    # Cancellation
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=b'print("ok")\n',
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    os.environ["NEXUS_ANALYSIS_STUB_DELAY_MS"] = "4000"
    try:
        slow = kernel.workspace_runtime.run_analysis(
            project_id=project_id,
            artifact_type="analysis",
            actor=user,
        )
        slow_id = slow["executionRun"]["executionRunId"]
        kernel.workspace_runtime.cancel_execution(
            project_id=project_id,
            execution_run_id=slow_id,
            actor=user,
        )
        cancelled = _wait_run(kernel, slow_id, timeout=10.0)
        assert cancelled["status"] == "cancelled"
        cancelled_logs = kernel.workspace_runtime.list_logs(
            project_id=project_id,
            execution_run_id=slow_id,
            after_sequence=0,
        )
        assert isinstance(cancelled_logs["chunks"], list)
    finally:
        os.environ.pop("NEXUS_ANALYSIS_STUB_DELAY_MS", None)

    # History / preview / restore safety
    preview = kernel.workspace_runtime.read_analysis_snapshot_file(
        project_id=project_id,
        artifact_type="analysis",
        snapshot_id=manual["snapshotId"],
        path="analysis.py",
    )
    assert preview["encoding"] == "utf-8"
    restored = kernel.workspace_runtime.restore_analysis_snapshot(
        project_id=project_id,
        artifact_type="analysis",
        snapshot_id=snap_id,
        actor=user,
    )
    assert restored["beforeRestoreSnapshotId"].startswith("snap_")
    assert any(s["reason"] == "before-analysis-restore" for s in ks.list_snapshots(ws_id))

    # Valid run again + modify + historical rerun + hash compare
    started2 = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    baseline_run = _wait_run(kernel, started2["executionRun"]["executionRunId"])
    assert baseline_run["status"] == "completed"
    baseline_snap = started2["executionSnapshotId"]
    baseline_outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=baseline_run["executionRunId"],
    )["outputs"]

    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=b'print("mutated live workspace")\n',
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    live_py = kernel.filesystem.read_file(ws_id, "analysis.py")["content"]
    assert b"mutated live workspace" in live_py

    rerun = kernel.workspace_runtime.rerun_analysis(
        project_id=project_id,
        artifact_type="analysis",
        snapshot_id=baseline_snap,
        actor=user,
    )
    assert rerun["rerun"] is True
    assert rerun["executionSnapshotId"] == baseline_snap
    rerun_run = _wait_run(kernel, rerun["executionRun"]["executionRunId"])
    assert rerun_run["status"] == "completed"
    assert rerun_run["inputSnapshotId"] == baseline_snap
    # Live workspace remains mutated (rerun did not restore)
    assert b"mutated live workspace" in kernel.filesystem.read_file(ws_id, "analysis.py")["content"]

    compared = kernel.workspace_runtime.compare_analysis_run_outputs(
        project_id=project_id,
        baseline_execution_run_id=baseline_run["executionRunId"],
        rerun_execution_run_id=rerun_run["executionRunId"],
    )
    assert compared["comparisons"]
    statuses = {row["status"] for row in compared["comparisons"]}
    assert statuses <= {"match", "different", "not-comparable"}
    assert "match" in statuses or "different" in statuses
    _ = baseline_outputs  # used for provenance of first successful run

    # Phase 15 regression: firmware still works
    fw_listed = kernel.workspace_runtime.list_snapshots(
        project_id=project_id,
        artifact_type="firmware",
    )["snapshots"]
    assert fw_listed


@pytest.mark.skipif(
    os.environ.get("RUN_ANALYSIS_LLM_INTEGRATION", "0") != "1"
    or not os.environ.get("NEXUS_MODEL_API_KEY"),
    reason="Set RUN_ANALYSIS_LLM_INTEGRATION=1 and NEXUS_MODEL_API_KEY for G2",
)
def test_phase16_g2_live_llm_stub_e2e() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
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
        analysis_patch_generator=LiveAnalysisPatchGenerator(
            gateway=gateway,
            model_policy=policy,
        ),
    )
    user = actor("user")
    binding = _setup_analysis(kernel, project_id, user)
    ws_id = binding["workspaceId"]
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/sensor.csv",
        content=SENSOR_CSV,
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    before = {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    proposed = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change=ANALYSIS_REQUEST,
    )
    assert before == {f["path"]: f["contentHash"] for f in ks.list_workspace_files(ws_id)}
    proposal = proposed["proposal"]
    assert proposal["operations"]
    assert any("analysis.py" in op.get("path", "") for op in proposal["operations"])
    meta = proposal.get("generatorMetadata") or proposed.get("generatorMetadata") or {}
    assert meta.get("mode") == "llm" or proposal.get("generatorId", "").endswith("llm-v1")
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.apply_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    analysis_py = kernel.filesystem.read_file(ws_id, "analysis.py")["content"].decode("utf-8")
    assert "sensor.csv" in analysis_py or "outputs/" in analysis_py


@pytest.mark.skipif(
    os.environ.get("RUN_ANALYSIS_DOCKER_INTEGRATION", "0") != "1"
    or shutil.which(os.environ.get("NEXUS_EXEC_DOCKER", "docker")) is None,
    reason="Set RUN_ANALYSIS_DOCKER_INTEGRATION=1 with Docker for G3",
)
def test_phase16_g3_live_python_container_e2e() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "0"
    image = os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "nexus-python-analysis:1.0.0")
    runtime = build_execution_runtime("container", container_image=image)
    kernel, _ps, ks, project_id = build_test_kernel(
        auto_start_scheduler=True,
        execution_runtime=runtime,
    )
    user = actor("user")
    binding = _setup_analysis(kernel, project_id, user)
    ws_id = binding["workspaceId"]
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/sensor.csv",
        content=SENSOR_CSV,
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    real_py = b"""import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main() -> None:
    df = pd.read_csv("data/sensor.csv")
    out = Path("outputs")
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "count": int(len(df)),
        "mean_accel_x": float(df["accel_x"].mean()),
        "numpy_ok": float(np.mean(df["accel_x"].to_numpy())),
    }
    (out / "results.json").write_text(
        json.dumps({"status": "ok"}, indent=2) + "\\n", encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\\n", encoding="utf-8"
    )
    processed = df.copy()
    processed["accel_x_sq"] = processed["accel_x"] ** 2
    processed.to_csv(out / "processed.csv", index=False)
    fig, ax = plt.subplots()
    ax.plot(df["time_s"], df["accel_x"])
    fig.savefig(out / "accel_plot.png")
    plt.close(fig)
    (out / "note.txt").write_text("real container analysis\\n", encoding="utf-8")

if __name__ == "__main__":
    main()
"""
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=real_py,
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"], timeout=60.0)
    assert run["status"] == "completed", run
    assert run["runtimeIdentity"]["runtimeKind"] == "container"
    assert run["runtimeIdentity"].get("networkPolicy") in {None, "none"}
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=run["executionRunId"],
    )["outputs"]
    names = {o.get("name") for o in outputs}
    assert "outputs/summary.json" in names
    assert "outputs/processed.csv" in names
    assert "outputs/accel_plot.png" in names

    # Real failure
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=b"raise RuntimeError('container-fail')\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    failed = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    failed_run = _wait_run(kernel, failed["executionRun"]["executionRunId"], timeout=60.0)
    assert failed_run["status"] == "failed"

    # Cancellation cleans container
    draft = ks.get_draft(ws_id)
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="analysis.py",
        content=b"import time\ntime.sleep(30)\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    slow = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    slow_id = slow["executionRun"]["executionRunId"]
    time.sleep(0.5)
    kernel.workspace_runtime.cancel_execution(
        project_id=project_id,
        execution_run_id=slow_id,
        actor=user,
    )
    cancelled = _wait_run(kernel, slow_id, timeout=30.0)
    assert cancelled["status"] == "cancelled"
    # Best-effort: no long-lived nexus analysis containers remain
    docker = os.environ.get("NEXUS_EXEC_DOCKER", "docker")
    listed = subprocess.run(
        [docker, "ps", "--format", "{{.Names}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert listed.returncode == 0
    for name in listed.stdout.splitlines():
        assert "nexus-exec" not in name or slow_id[-8:] not in name


@pytest.mark.skipif(
    os.environ.get("RUN_ANALYSIS_FULL_LIVE", "0") != "1"
    or not os.environ.get("NEXUS_MODEL_API_KEY")
    or shutil.which(os.environ.get("NEXUS_EXEC_DOCKER", "docker")) is None,
    reason="Set RUN_ANALYSIS_FULL_LIVE=1 with model key + Docker for G4",
)
def test_phase16_g4_full_live_product_e2e() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "0"
    image = os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "nexus-python-analysis:1.0.0")
    provider = (os.environ.get("NEXUS_MODEL_PROVIDER") or "openai").strip().lower()
    gateway = OpenAICompatibleGateway(
        model_credential=os.environ["NEXUS_MODEL_API_KEY"],
        base_url=os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1"),
    )
    policy = ModelPolicy(
        provider=provider,
        model=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "90")),
    )
    runtime = build_execution_runtime("container", container_image=image)
    kernel, _ps, ks, project_id = build_test_kernel(
        auto_start_scheduler=True,
        execution_runtime=runtime,
        analysis_patch_generator=LiveAnalysisPatchGenerator(
            gateway=gateway,
            model_policy=policy,
        ),
    )
    user = actor("user")
    binding = _setup_analysis(kernel, project_id, user)
    ws_id = binding["workspaceId"]
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/sensor.csv",
        content=SENSOR_CSV,
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    proposed = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change=ANALYSIS_REQUEST,
    )
    proposal = proposed["proposal"]
    draft = ks.get_draft(ws_id)
    kernel.workspace_runtime.apply_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"], timeout=90.0)
    assert run["status"] == "completed", (
        f"G4 live run status={run['status']}; "
        f"do not substitute fixture code — report actual model outcome"
    )
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id,
        execution_run_id=run["executionRunId"],
    )["outputs"]
    names = {o.get("name") for o in outputs}
    assert any(str(n).endswith(".json") for n in names)
    rerun = kernel.workspace_runtime.rerun_analysis(
        project_id=project_id,
        artifact_type="analysis",
        snapshot_id=started["executionSnapshotId"],
        actor=user,
    )
    rerun_run = _wait_run(kernel, rerun["executionRun"]["executionRunId"], timeout=90.0)
    assert rerun_run["inputSnapshotId"] == started["executionSnapshotId"]
    assert rerun_run["status"] == "completed"
