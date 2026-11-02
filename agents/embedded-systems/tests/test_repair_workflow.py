"""W5 regression evidence: scripted gateway, actual Python jobs and guarded review."""

import copy
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, seed_approved_firmware_plan
from nexus_api import main
from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
from nexus_board.errors import BoardError
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_board.kernel import build_project_kernel
from nexus_circuit_simulation import RunnerResult, WokwiProvider
from nexus_embedded_systems.workflows.layered_architecture import (
    ensure_layered_architecture_artifacts,
)
from nexus_embedded_systems.workflows.project_initialization.materializer import (
    materialize_fixture_package,
)
from nexus_embedded_systems.workflows.repair import RepairWorkflow
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from nexus_persistence.factory import build_stores

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "packages/board/tests/golden/esp32_imu_vibration_monitor"


def wait(kernel, run_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        run = kernel.executions.get_run(run_id)
        if run["status"] not in {"queued", "starting", "running", "cancelling"}:
            return run
        time.sleep(0.02)
    pytest.fail("regression job did not terminate")


@pytest.fixture
def repair_env(monkeypatch, tmp_path, request):
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    ps, ks = build_stores("sqlite", f"sqlite:///{tmp_path}/repair.db")
    package, _ = materialize_fixture_package(
        ROOT / "packages/contracts/examples/valid/esp32-imu-vibration-monitor",
        message="IMU monitor",
        autonomy_mode="collaborate",
    )
    ensured = ensure_layered_architecture_artifacts(
        project_id=package["project"]["projectId"],
        artifacts=package["artifacts"],
        actor=package["artifacts"][0]["createdBy"],
    )
    package["artifacts"] = ensured["artifacts"]
    package["project"]["currentArtifactReferences"] = [
        {k: a[k] for k in ("artifactType", "artifactId", "artifactVersion", "contentSchemaVersion")}
        for a in package["artifacts"]
    ]
    live = getattr(request, "param", None) == "live"
    if live:
        package["artifacts"] = [a for a in package["artifacts"] if a["artifactType"] != "test-plan"]
        package["project"]["currentArtifactReferences"] = [
            r
            for r in package["project"]["currentArtifactReferences"]
            if r["artifactType"] != "test-plan"
        ]
    ps.save_initialization_package(package)
    kernel = build_project_kernel(ks, project_store=ps)
    user = actor()
    pid = package["project"]["projectId"]
    if live:
        from nexus_board.ids import new_id, utc_now_iso
        from nexus_embedded_systems.workflows.project_modification.execution_plan import (
            ExecutionPlanWorkflow,
        )

        workflow = ExecutionPlanWorkflow(kernel)
        kernel.commands.revision_validator = workflow.validate_revision
        kernel.commands.revision_materializer = workflow.materialize
        cp = ps.get_artifact(pid, "component-plan")["content"]
        electrical = ps.get_artifact(pid, "electrical-architecture")["content"]
        config = {
            "buildProfileId": "platformio-arduino-esp32-v1",
            "analysisProfileId": "python-analysis-v1",
            "components": [
                {"componentRoleId": c["componentRoleId"], "candidateId": c["candidateId"]}
                for c in cp["candidates"]
            ],
            "i2c": {
                "connectionId": next(
                    c["connectionId"]
                    for c in electrical["connections"]
                    if c["interfaceType"] == "i2c"
                ),
                "sdaPin": 21,
                "sclPin": 22,
            },
        }
        proposed = workflow.propose(
            pid, user, ps.get_project(pid)["currentStateVersion"], 0, config
        )
        ws = proposed["workspace"]
        result = kernel.dispatch(
            {
                "schemaVersion": "1.0.0",
                "commandId": new_id("cmd"),
                "commandType": "artifact.accept-revision",
                "projectId": pid,
                "workspaceId": ws["workspaceId"],
                "artifactId": ws["artifactId"],
                "baseArtifactVersion": ws["baseArtifactVersion"],
                "baseProjectStateVersion": ps.get_project(pid)["currentStateVersion"],
                "requestedBy": user,
                "requestedAt": utc_now_iso(),
                "input": {"proposalId": proposed["commandResult"]["proposalId"]},
            }
        )
        assert result["status"] == "completed", result
        seeded = ps.get_artifact(pid, "test-plan")
        assert all(
            c["status"] == "planned" and "criterion" in c and "assessment" not in c
            for c in seeded["content"]["testCases"]
        )
        golden_cases = json.loads(
            (
                ROOT
                / "packages/contracts/examples/valid/esp32-imu-vibration-monitor"
                / "test-plan-artifact.json"
            ).read_text()
        )["content"]["testCases"]
        assert len(seeded["content"]["testCases"]) == len(golden_cases)
        for case, golden_case in zip(seeded["content"]["testCases"], golden_cases, strict=True):
            assert case["criterion"] == golden_case["criterion"]
            assert case["verificationMethod"] == golden_case["verificationMethod"]
        workflow.retry_materialization(
            pid,
            user,
            ps.get_artifact(pid, "execution-plan")["artifactId"],
            ps.get_project(pid)["currentStateVersion"],
        )
        assert ps.get_artifact(pid, "test-plan") == seeded
        binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
        record = next(
            f
            for f in kernel.filesystem.list_files(binding["workspaceId"])
            if f["path"] == "analysis.py"
        )
        assert (
            kernel.filesystem.file_store.get(record["contentHash"])
            == workflow.render(ps.get_artifact(pid, "execution-plan")["content"])["analysis"][
                "analysis.py"
            ]
        )
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=pid, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=pid,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    if not live:
        kernel.workspace_runtime.generate_analysis_scaffold(
            project_id=pid,
            artifact_type="analysis",
            actor=user,
            expected_draft_version=1,
            base_artifact_version=binding["baseArtifactVersion"],
            base_project_state_version=binding["baseProjectStateVersion"],
        )

    def write(path, data):
        binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
        kernel.filesystem.write_file(
            workspace_id=binding["workspaceId"],
            path=path,
            content=data,
            actor=user,
            expected_draft_version=binding["draft"]["draftVersion"],
            base_artifact_version=binding["baseArtifactVersion"],
            base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
            origin="USER",
            write_policy="USER_EDITABLE",
        )

    source = (
        (GOLDEN / "analysis.py")
        .read_text()
        .replace(
            '"sampleCount": len(xs),',
            '"sampleCount": len(xs), "sampling_hz": (len(ts) - 1) / (ts[-1] - ts[0]),',
        )
    )
    write("analysis.py", (source + '\nraise RuntimeError("INJECTED_DEFECT")\n').encode())
    write("data/stationary_imu.csv", (GOLDEN / "stationary_imu.csv").read_bytes())
    started = kernel.workspace_runtime.run_analysis(
        project_id=pid, artifact_type="analysis", actor=user
    )
    failed = wait(kernel, started["executionRun"]["executionRunId"])
    assert failed["status"] == "failed"
    gateway = FakeModelGateway()
    requests = []

    def reply(_task, payload, _schema):
        requests.append(copy.deepcopy(payload))
        assert "INJECTED_DEFECT" in payload["requestedChange"]
        for kind in (
            ("requirement-set", "electrical-architecture")
            if live
            else ("requirement-set", "electrical-architecture", "test-plan")
        ):
            current = ps.get_artifact(pid, kind)
            assert {
                k: current[k] for k in ("artifactType", "artifactId", "artifactVersion")
            } in payload["inputArtifactReferences"]
        return {
            "operations": [
                {"operationType": "replace-file", "path": "analysis.py", "content": source}
            ]
        }

    gateway.set_script("analysis.patch-proposal", reply)
    kernel.workspace_runtime._analysis_patch_generator = LiveAnalysisPatchGenerator(
        gateway=gateway,
        model_policy=ModelPolicy(provider="fake", model="regression"),
    )
    yield kernel, pid, user, failed, requests, write
    kernel.jobs.shutdown()


def advance(workflow, state, user, **kwargs):
    return workflow.advance(
        state["projectId"], state["repairId"], user, state["revision"], **kwargs
    )


def apply(kernel, pid, user, state):
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
    return kernel.workspace_runtime.apply_analysis_patch(
        project_id=pid,
        artifact_type="analysis",
        proposal_id=state["proposalId"],
        actor=user,
        expected_draft_version=binding["draft"]["draftVersion"],
        base_artifact_version=binding["baseArtifactVersion"],
        base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
    )


def test_injected_failure_review_rerun_and_preserved_evidence(repair_env, tmp_path):
    kernel, pid, user, failed, requests, _ = repair_env
    workflow = RepairWorkflow(kernel)
    original = copy.deepcopy(
        kernel.workspace_runtime.get_execution(
            project_id=pid, execution_run_id=failed["executionRunId"]
        )
    )
    logs = copy.deepcopy(
        kernel.workspace_runtime.list_logs(
            project_id=pid, execution_run_id=failed["executionRunId"]
        )
    )
    snapshot = copy.deepcopy(kernel.kernel_store.get_snapshot(failed["inputSnapshotId"]))
    state = workflow.start(pid, user, failed["executionRunId"], "analysis")
    initial = copy.deepcopy(state)
    state = advance(workflow, state, user)
    assert state["status"] == "review" and requests
    proposal = kernel.kernel_store.get_firmware_patch_proposal(state["proposalId"])
    assert proposal["inputArtifactReferences"] == requests[-1]["inputArtifactReferences"]
    assert advance(workflow, state, user) == state  # no approval, no rerun
    apply(kernel, pid, user, state)
    state = advance(workflow, state, user)
    assert state["status"] == "running"
    assert wait(kernel, state["runId"])["status"] == "completed"
    # Reconstruct coordinator from the existing SQLite ledger before advancing.
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, state, user)
    assert state["status"] == "completed", workflow._cases(pid, state["runId"])
    assert len(state["attempts"]) == 2
    assert state["attempts"][0]["runIds"] == [failed["executionRunId"]]
    assert original == kernel.workspace_runtime.get_execution(
        project_id=pid, execution_run_id=failed["executionRunId"]
    )
    assert logs == kernel.workspace_runtime.list_logs(
        project_id=pid, execution_run_id=failed["executionRunId"]
    )
    assert snapshot == kernel.kernel_store.get_snapshot(failed["inputSnapshotId"])
    events, _ = kernel.ledger.list_events(pid, limit=100)
    repair_events = [e for e in events if e["subject"]["subjectId"] == state["repairId"]]
    assert initial in [json.loads(e["payload"]["summary"]) for e in repair_events]
    from nexus_contracts.validation.schema_validator import validate_against_schema_id

    for event in repair_events:
        assert (
            validate_against_schema_id(
                event, "https://nexus.local/schemas/events/project-event.v1.schema.json"
            )
            == []
        )
    assert (
        kernel.kernel_store.get_firmware_patch_proposal(
            state["attempts"][0]["correctionProposalId"]
        )["status"]
        == "applied"
    )

    reopened_ps, reopened_ks = build_stores("sqlite", f"sqlite:///{tmp_path}/repair.db")
    reopened = build_project_kernel(
        reopened_ks, project_store=reopened_ps, auto_start_scheduler=False
    )
    try:
        assert RepairWorkflow(reopened).get(pid, state["repairId"]) == state
        assert (
            reopened.workspace_runtime.get_execution(
                project_id=pid, execution_run_id=failed["executionRunId"]
            )
            == original
        )
        assert (
            reopened.workspace_runtime.list_logs(
                project_id=pid, execution_run_id=failed["executionRunId"]
            )
            == logs
        )
    finally:
        reopened.jobs.shutdown()


def test_exhaustion_is_visible_and_enforced(repair_env):
    kernel, pid, user, failed, requests, _ = repair_env
    workflow = RepairWorkflow(kernel)
    state = workflow.start(pid, user, failed["executionRunId"], "analysis", max_attempts=1)
    state = advance(workflow, state, user)
    assert state["status"] == "exhausted" and "limit" in state["explanation"]
    assert advance(workflow, state, user) == state
    assert not requests and len(state["attempts"]) == 1
    with pytest.raises(BoardError):
        workflow.start(pid, user, failed["executionRunId"], "analysis", max_attempts=4)


def test_unavailability_blocks_without_canned_success(repair_env):
    kernel, pid, user, failed, requests, _ = repair_env
    kernel.workspace_runtime._analysis_patch_generator = None
    workflow = RepairWorkflow(kernel)
    state = workflow.start(pid, user, failed["executionRunId"], "analysis")
    state = advance(workflow, state, user)
    assert state["status"] == "unavailable" and state["errorCode"] == "MODEL_PROVIDER_UNAVAILABLE"
    assert not requests


def test_rejected_correction_cannot_rerun(repair_env):
    kernel, pid, user, failed, _, _ = repair_env
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, workflow.start(pid, user, failed["executionRunId"], "analysis"), user)
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
    before = copy.deepcopy(binding["draft"])
    kernel.workspace_runtime.discard_analysis_patch(
        project_id=pid, artifact_type="analysis", proposal_id=state["proposalId"], actor=user
    )
    state = advance(workflow, state, user)
    assert state["status"] == "rejected" and len(state["attempts"]) == 1
    assert kernel.kernel_store.get_draft(binding["workspaceId"]) == before


@pytest.mark.parametrize("status", ["cancelled", "timed-out"])
def test_cancelled_or_timed_out_run_never_passes(repair_env, status):
    kernel, pid, user, failed, _, _ = repair_env
    workflow = RepairWorkflow(kernel)
    state = workflow.start(pid, user, failed["executionRunId"], "analysis")
    state = advance(workflow, state, user)
    apply(kernel, pid, user, state)
    state = advance(workflow, state, user)
    wait(kernel, state["runId"])
    run = kernel.executions.get_run(state["runId"])
    run["status"] = status  # terminal runtime-result regression injection
    kernel.kernel_store.update_execution_status(state["runId"], run)
    state = advance(workflow, state, user)
    assert state["status"] in {"cancelled", "stopped"}


def test_cancel_review_and_stale_advance(repair_env):
    kernel, pid, user, failed, _, _ = repair_env
    workflow = RepairWorkflow(kernel)
    state = workflow.start(pid, user, failed["executionRunId"], "analysis")
    old = copy.deepcopy(state)
    state = advance(workflow, state, user, cancel=True)
    assert state["status"] == "cancelled"
    with pytest.raises(BoardError, match="Stale"):
        advance(workflow, old, user)


def set_analysis_reply(kernel, source):
    kernel.workspace_runtime._analysis_patch_generator.gateway.set_script(
        "analysis.patch-proposal",
        lambda *_: {
            "operations": [
                {"operationType": "replace-file", "path": "analysis.py", "content": source}
            ]
        },
    )


def test_unrepairable_failure_exhausts_after_real_rerun(repair_env):
    kernel, pid, user, failed, _, _ = repair_env
    set_analysis_reply(kernel, 'raise RuntimeError("UNREPAIRABLE")\n')
    workflow = RepairWorkflow(kernel)
    state = workflow.start(pid, user, failed["executionRunId"], "analysis", max_attempts=2)
    state = advance(workflow, state, user)
    apply(kernel, pid, user, state)
    state = advance(workflow, state, user)
    assert wait(kernel, state["runId"])["status"] == "failed"
    state = advance(workflow, state, user)
    state = advance(workflow, state, user)
    assert state["status"] == "exhausted" and len(state["attempts"]) == 2
    assert len({r for a in state["attempts"] for r in a["runIds"]}) == 2


@pytest.mark.parametrize("stop", ["timeout", "cancel"])
def test_inflight_stop_uses_existing_job_runtime(repair_env, monkeypatch, stop):
    kernel, pid, user, failed, _, _ = repair_env
    set_analysis_reply(kernel, "import time\ntime.sleep(30)\n")
    original_run = kernel.workspace_runtime.run_analysis
    if stop == "timeout":

        def run(**kwargs):
            return original_run(**kwargs, max_duration_ms=100)

        monkeypatch.setattr(kernel.workspace_runtime, "run_analysis", run)
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, workflow.start(pid, user, failed["executionRunId"], "analysis"), user)
    apply(kernel, pid, user, state)
    state = advance(workflow, state, user)
    if stop == "cancel":
        deadline = time.monotonic() + 5
        while kernel.executions.get_run(state["runId"])["status"] != "running":
            assert time.monotonic() < deadline
            time.sleep(0.01)
        state = advance(workflow, state, user, cancel=True)
        result = wait(kernel, state["runId"])
        # Existing process runtime can record SIGKILL as NONZERO_EXIT before
        # observing its cancellation flag. The loop preserves that diagnosis.
        assert result["status"] in {"cancelled", "failed"}
        if result["status"] == "failed":
            assert result["error"] == {
                "code": "NONZERO_EXIT",
                "message": "Process exited with code -9",
            }
        assert state["status"] == "cancelled"
    else:
        assert wait(kernel, state["runId"])["status"] == "timed-out"
        assert advance(workflow, state, user)["status"] == "stopped"


def test_stale_correction_requires_review_again(repair_env):
    kernel, pid, user, failed, _, write = repair_env
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, workflow.start(pid, user, failed["executionRunId"], "analysis"), user)
    write("analysis.py", b"print('concurrent edit')\n")
    with pytest.raises(BoardError, match="changed|stale|Stale"):
        apply(kernel, pid, user, state)
    assert advance(workflow, state, user)["status"] == "review"


@pytest.mark.parametrize(
    "repair_env,simulator,bad_evidence",
    [
        (None, "ready", False),
        (None, "unavailable", False),
        (None, "failed", False),
        (None, "firmware-test", False),
        (None, "build", False),
        (None, "build-retry", False),
        (None, "build-exhausted", False),
        (None, "electrical-held", False),
        (None, "analysis-held", False),
        ("live", "live", False),
        ("live", "live", True),
    ],
    indirect=["repair_env"],
)
def test_firmware_defect_repair_reruns_existing_w4_path(
    repair_env, monkeypatch, tmp_path, simulator, bad_evidence
):
    """Scripted compiler/model/simulator; real jobs, storage, import and Python analysis."""
    kernel, pid, user, _, _, write = repair_env
    if simulator != "live":
        seed_approved_firmware_plan(kernel.project_store, pid)
    fixed_analysis = (
        (GOLDEN / "analysis.py")
        .read_text()
        .replace(
            '"sampleCount": len(xs),',
            '"sampleCount": len(xs), "sampling_hz": (len(ts) - 1) / (ts[-1] - ts[0]),',
        )
    )
    if simulator == "live":
        from nexus_embedded_systems.workflows.project_modification.execution_plan import (
            ExecutionPlanWorkflow,
        )

        plan = kernel.project_store.get_artifact(pid, "execution-plan")["content"]
        fixed_analysis = (
            ExecutionPlanWorkflow(kernel).render(plan)["analysis"]["analysis.py"].decode()
        )
    write("analysis.py", fixed_analysis.encode())
    pio = tmp_path / "pio"
    pio.write_text(
        "#!/usr/bin/python3\nfrom pathlib import Path\nimport sys\n"
        "source = Path('src/main.cpp').read_bytes()\n"
        "if b'INJECTED_DEFECT' in source:\n"
        " print('INJECTED_DEFECT: compiler regression error', file=sys.stderr)\n sys.exit(1)\n"
        "p = Path('.pio/build/nexus'); p.mkdir(parents=True, exist_ok=True)\n"
        "(p / 'firmware.elf').write_bytes(b'\\x7fELF' + source)\n"
        "(p / 'firmware.bin').write_bytes(source)\n"
    )
    pio.chmod(0o755)
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    from nexus_board.execution import process_runtime

    original_env = process_runtime.build_sandbox_environment

    def environment(entries):
        env = original_env(entries)
        env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
        return env

    monkeypatch.setattr(process_runtime, "build_sandbox_environment", environment)
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=pid, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=pid,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    if simulator != "live":
        kernel.workspace_runtime.generate_firmware_scaffold(
            project_id=pid,
            artifact_type="firmware",
            actor=user,
            expected_draft_version=1,
            base_artifact_version=binding["baseArtifactVersion"],
            base_project_state_version=binding["baseProjectStateVersion"],
        )
    source = (GOLDEN / "main.cpp").read_text()
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="firmware")
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path="src/main.cpp",
        content=(source + "\nINJECTED_DEFECT\n").encode(),
        actor=user,
        expected_draft_version=binding["draft"]["draftVersion"],
        base_artifact_version=binding["baseArtifactVersion"],
        base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    if simulator == "firmware-test":
        binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="firmware")
        kernel.filesystem.write_file(
            workspace_id=binding["workspaceId"],
            path="test/test_nexus.cpp",
            content=b"// regression test\n",
            actor=user,
            expected_draft_version=binding["draft"]["draftVersion"],
            base_artifact_version=binding["baseArtifactVersion"],
            base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
            origin="USER",
            write_policy="USER_EDITABLE",
        )
    operation = (
        kernel.workspace_runtime.test_firmware
        if simulator == "firmware-test"
        else kernel.workspace_runtime.compile_firmware
    )
    failed = operation(project_id=pid, artifact_type="firmware", actor=user)["executionRun"]
    assert wait(kernel, failed["executionRunId"])["status"] == "failed"
    gateway = FakeModelGateway()

    corrections = []

    def correction(_task, payload, _schema):
        corrections.append(payload)
        assert "INJECTED_DEFECT: compiler regression error" in payload["requestedChange"]
        if len(corrections) == 1:
            assert failed["executionRunId"] in payload["requestedChange"]
        for kind in (
            ("requirement-set", "electrical-architecture")
            if simulator == "live"
            else ("requirement-set", "electrical-architecture", "test-plan")
        ):
            current = kernel.project_store.get_artifact(pid, kind)
            assert {
                k: current[k] for k in ("artifactType", "artifactId", "artifactVersion")
            } in payload["inputArtifactReferences"]
        return {
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "src/main.cpp",
                    "content": source
                    + (
                        "\nINJECTED_DEFECT\n"
                        if simulator in {"build-retry", "build-exhausted"} and len(corrections) == 1
                        else ""
                    ),
                }
            ]
        }

    gateway.set_script("firmware.patch-proposal", correction)
    kernel.workspace_runtime._firmware_patch_generator = LiveFirmwarePatchGenerator(
        gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
    )
    telemetry = b"NEXUS_MPU_READY\ntime_s,accel_x_g,accel_y_g,accel_z_g\n" + b"".join(
        f"TEL,{i / 50},0.01,0,1\n".encode() for i in range(100)
    )
    if bad_evidence and simulator == "live":
        telemetry = b"NEXUS_MPU_READY\ntime_s,accel_x_g,accel_y_g,accel_z_g\n" + b"".join(
            f"TEL,{i / 25},0.01,0,1\n".encode() for i in range(100)
        )
    consumed = []

    class Runner:
        def run(self, request):
            if request.arguments[0] == "lint":
                return RunnerResult(exit_code=0, timed_out=False)
            assert request.files["firmware.elf"] == b"\x7fELF" + source.encode()
            consumed.append(request.files["firmware.elf"])
            if simulator == "failed":
                return RunnerResult(
                    exit_code=1, timed_out=False, stderr=b"INJECTED_SIMULATOR_FAILURE"
                )
            return RunnerResult(exit_code=0, timed_out=False, outputs={"serial.log": telemetry})

    kernel.executions._capability_executors["circuit-simulation"] = (
        CircuitSimulationExecutionAdapter(
            provider=WokwiProvider(
                executable=str(pio),
                token="" if simulator == "unavailable" else "regression-only",
                runner=Runner(),
            ),
            project_store=kernel.project_store,
            kernel_store=kernel.kernel_store,
            file_store=kernel.filesystem.file_store,
        )
    )
    kernel.executions._capabilities.register(
        {
            "schemaVersion": "1.0.0",
            "capabilityId": "circuit-simulation",
            "displayName": "Regression simulator",
            "providerId": "wokwi",
            "available": True,
        }
    )
    electrical = kernel.workspace_runtime.resolve_binding(
        project_id=pid, artifact_type="electrical-architecture", actor=user
    )
    analysis = kernel.workspace_runtime.resolve_binding(
        project_id=pid, artifact_type="analysis", actor=user
    )
    kernel.workspaces.release_edit_lease(workspace_id=analysis["workspaceId"], actor=user)
    other = {**user, "actorId": "user_other"}
    blocked = electrical if simulator == "electrical-held" else analysis
    if simulator in {"electrical-held", "analysis-held"}:
        kernel.workspaces.acquire_edit_lease(workspace_id=blocked["workspaceId"], actor=other)
    workflow = RepairWorkflow(kernel)
    build_scope = simulator.startswith("build")
    if build_scope:
        before_plan = copy.deepcopy(kernel.project_store.get_artifact(pid, "test-plan"))

        def forbidden(*args, **kwargs):
            pytest.fail("Build-only repair must not launch simulation/analysis or promote evidence")

        monkeypatch.setattr(kernel.verification, "promote_execution_evidence", forbidden)
        monkeypatch.setattr(kernel.workspace_runtime, "run_analysis", forbidden)
        original_execute = kernel.executions.execute

        def compile_only(**kwargs):
            assert kwargs["artifact_type"] == "firmware"
            return original_execute(**kwargs)

        monkeypatch.setattr(kernel.executions, "execute", compile_only)
    if build_scope:
        import asyncio

        from httpx import ASGITransport, AsyncClient

        monkeypatch.setattr(main, "_kernel", kernel)

        async def start_over_http():
            async with AsyncClient(
                transport=ASGITransport(app=main.app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/v1/projects/{pid}/repair",
                    headers={"Authorization": "Bearer " + main.EXPECTED_SESSION_TOKEN.decode()},
                    json={
                        "action": "start",
                        "executionRunId": failed["executionRunId"],
                        "target": "firmware",
                        "scope": "build",
                        "requestedBy": user,
                        "requireReal": True,
                        "maxAttempts": 2 if simulator == "build-exhausted" else 3,
                    },
                )
                assert response.status_code == 200, response.text
                return response.json()

        initial = asyncio.run(start_over_http())
    else:
        initial = workflow.start(
            pid, user, failed["executionRunId"], "firmware", require_real=False
        )
    state = advance(workflow, initial, user)
    assert state["status"] == "review", str(state)
    proposal = kernel.kernel_store.get_firmware_patch_proposal(state["proposalId"])
    assert proposal["generatorMetadata"]["mode"] == "regression"
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="firmware")
    kernel.workspace_runtime.apply_firmware_patch(
        project_id=pid,
        artifact_type="firmware",
        proposal_id=state["proposalId"],
        actor=user,
        expected_draft_version=binding["draft"]["draftVersion"],
        base_artifact_version=binding["baseArtifactVersion"],
        base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
    )
    for _ in range(12):
        if (
            build_scope
            and state["status"] == "review"
            and kernel.kernel_store.get_firmware_patch_proposal(state["proposalId"])["status"]
            == "proposed"
        ):
            binding = kernel.workspace_runtime.resolve_binding(
                project_id=pid, artifact_type="firmware"
            )
            kernel.workspace_runtime.apply_firmware_patch(
                project_id=pid,
                artifact_type="firmware",
                proposal_id=state["proposalId"],
                actor=user,
                expected_draft_version=binding["draft"]["draftVersion"],
                base_artifact_version=binding["baseArtifactVersion"],
                base_project_state_version=kernel.project_store.get_project(pid)[
                    "currentStateVersion"
                ],
            )
        state = advance(workflow, state, user)
        if state["status"] == "running":
            wait(kernel, state["runId"])
        if state["status"] in {"completed", "stopped", "unavailable", "exhausted"}:
            break
        if simulator == "live" and state["stage"] == "analyze":
            break
        if simulator == "failed" and state["status"] == "inspect":
            break
    if build_scope:
        assert state["scope"] == "build" and state["stage"] == "compile"
        assert workflow.get(pid, state["repairId"]) == state
        assert len(state["attempts"]) == (3 if simulator == "build-retry" else 2)
        assert all(len(a["runIds"]) == 1 for a in state["attempts"])
        assert state["status"] == ("exhausted" if simulator == "build-exhausted" else "completed")
        if state["status"] == "completed":
            assert "Build-only repair" in state["explanation"]
        assert not consumed
        assert kernel.project_store.get_artifact(pid, "test-plan") == before_plan
        return
    if simulator in {"electrical-held", "analysis-held"}:
        assert state["status"] == "stopped", state
        assert state["errorCode"] == "DRAFT_EDIT_LEASE_HELD"
        assert "another actor" in state["explanation"]
        assert blocked["artifactType"] in state["explanation"]
        assert (
            kernel.kernel_store.get_draft(blocked["workspaceId"])["editLease"]["ownerActorId"]
            == other["actorId"]
        )
        return
    if simulator in {"unavailable", "failed"}:
        assert len(state["attempts"][1]["runIds"]) == 2  # failed simulation also retained
        failed_simulation = kernel.executions.get_run(state["runId"])
        assert failed_simulation["status"] == "failed"
        if simulator == "unavailable":
            assert state["status"] == "unavailable"
            assert state["errorCode"] == "WOKWI_CREDENTIAL_MISSING"
        else:
            assert state["status"] == "inspect"
            assert "INJECTED_SIMULATOR_FAILURE" in failed_simulation["error"]["message"]
            gateway.set_script(
                "firmware.patch-proposal",
                lambda _t, payload, _s: (
                    {
                        "operations": [
                            {
                                "operationType": "replace-file",
                                "path": "src/main.cpp",
                                "content": source,
                            }
                        ]
                    }
                    if "INJECTED_SIMULATOR_FAILURE" in str(payload["requestedChange"])
                    else {}
                ),
            )
            assert advance(workflow, state, user)["status"] == "review"
        return
    if simulator == "live":
        assert state["stage"] == "analyze", state
        assert state["status"] == "running", state
        assert kernel.executions.get_run(state["runId"])["status"] == "completed"
        state = advance(workflow, state, user)
        assert state["status"] == ("inspect" if bad_evidence else "completed"), str(state)
        assert not state.get("errorCode")
        return
    assert state["status"] == "completed", str(state)
    for downstream in (electrical, analysis):
        assert not kernel.kernel_store.get_draft(downstream["workspaceId"]).get("editLease")
    assert (
        kernel.kernel_store.get_draft(binding["workspaceId"])["editLease"]["ownerActorId"]
        == user["actorId"]
    )
    assert len(state["attempts"]) == 2
    assert len(state["attempts"][1]["runIds"]) == (4 if simulator == "firmware-test" else 3)
    assert consumed
    simulation = kernel.executions.get_run(state["attempts"][1]["runIds"][-2])
    assert simulation["inputOutputReferences"] == [state["firmwareOutputId"]]
    output = kernel.workspace_runtime.get_output(
        project_id=pid, output_id=state["firmwareOutputId"]
    )
    assert output["contentDigest"] == "sha256:" + hashlib.sha256(consumed[0]).hexdigest()
    snap = kernel.kernel_store.get_snapshot(
        kernel.executions.get_run(state["runId"])["inputSnapshotId"]
    )
    entry = next(
        e
        for e in snap["content"]["filesystemManifest"]["entries"]
        if e["path"] == "data/serial.log"
    )
    assert kernel.filesystem.file_store.get(entry["contentHash"]) == telemetry


@pytest.mark.asyncio
async def test_http_repair_revision_and_validation(repair_env, monkeypatch):
    import asyncio

    from httpx import ASGITransport, AsyncClient

    # Keep the managed test runner's event loop ticking while a worker completes.
    # This changes no provider/job outcome and avoids relying on cross-thread
    # socket wakeups, which are restricted in this environment.
    async def tick():
        while True:
            await asyncio.sleep(0.01)

    ticker = asyncio.create_task(tick())
    kernel, pid, user, failed, _, _ = repair_env
    monkeypatch.setattr(main, "_kernel", kernel)
    client = AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")
    headers = {"Authorization": "Bearer " + main.EXPECTED_SESSION_TOKEN.decode()}
    route = f"/v1/projects/{pid}/repair"
    response = await asyncio.wait_for(
        client.post(
            route,
            headers=headers,
            json={
                "executionRunId": failed["executionRunId"],
                "target": "analysis",
                "requestedBy": user,
            },
        ),
        5,
    )
    assert response.status_code == 200, response.text
    state = response.json()
    response = await client.post(
        route,
        headers=headers,
        json={
            "action": "advance",
            "repairId": state["repairId"],
            "revision": state["revision"],
            "requestedBy": user,
        },
    )
    assert response.status_code == 200 and response.json()["status"] == "review"
    conflict = await client.post(
        route,
        headers=headers,
        json={
            "action": "advance",
            "repairId": state["repairId"],
            "revision": state["revision"],
        },
    )
    assert conflict.status_code == 409
    invalid = await client.post(route, headers=headers, json={"executionRunId": [], "target": []})
    assert invalid.status_code == 422
    for scope in ("build", "unknown", None, []):
        rejected = await client.post(
            route,
            headers=headers,
            json={
                "action": "start",
                "executionRunId": failed["executionRunId"],
                "target": "analysis",
                "scope": scope,
                "requestedBy": user,
            },
        )
        assert rejected.status_code == 422, rejected.text
    bad_action = await client.post(route, headers=headers, json={"action": []})
    assert bad_action.status_code == 422
    assert (await client.post(route, headers=headers, content="{")).status_code == 422
    await client.aclose()
    ticker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await ticker


def test_real_analysis_gate_rejects_fixture_before_rerun(repair_env, monkeypatch):
    kernel, pid, user, failed, _, _ = repair_env
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, workflow.start(pid, user, failed["executionRunId"], "analysis"), user)
    apply(kernel, pid, user, state)
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "1")
    state = advance(workflow, state, user)
    assert state["status"] == "unavailable"
    assert state["errorCode"] == "ANALYSIS_TOOLCHAIN_UNAVAILABLE"
    assert not state["attempts"][-1]["runIds"]


def test_failed_metric_inspection_and_rerun_keeps_prior_summary(repair_env):
    kernel, pid, user, _, _, write = repair_env
    source = (
        (GOLDEN / "analysis.py")
        .read_text()
        .replace(
            '"sampleCount": len(xs),',
            '"sampleCount": len(xs), "sampling_hz": (len(ts) - 1) / (ts[-1] - ts[0]),',
        )
    )
    # Controlled processing defect: an offset contaminates the demeaned RMS.
    write("analysis.py", source.replace("(v - mean_x)", "(v + 0.20)").encode())
    run = kernel.workspace_runtime.run_analysis(
        project_id=pid, artifact_type="analysis", actor=user
    )["executionRun"]
    wait(kernel, run["executionRunId"])
    kernel.verification.promote_execution_evidence(
        project_id=pid, execution_run_id=run["executionRunId"], actor=user
    )
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=pid, execution_run_id=run["executionRunId"]
    )["outputs"]
    summary = next(o for o in outputs if o["name"] == "outputs/summary.json")
    prior = copy.deepcopy(summary)
    before_plan = kernel.project_store.get_artifact(pid, "test-plan")
    assert any(c.get("assessment") == "FAIL" for c in before_plan["content"]["testCases"])

    def correction(_task, payload, _schema):
        assert "accel_x_rms_noise_g" in payload["requestedChange"]
        assert (
            "FAIL" in payload["requestedChange"]
            and run["executionRunId"] in payload["requestedChange"]
        )
        return {
            "operations": [
                {"operationType": "replace-file", "path": "analysis.py", "content": source}
            ]
        }

    kernel.workspace_runtime._analysis_patch_generator.gateway.set_script(
        "analysis.patch-proposal", correction
    )
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, workflow.start(pid, user, run["executionRunId"], "analysis"), user)
    assert state["status"] == "review"
    apply(kernel, pid, user, state)
    state = advance(workflow, state, user)
    wait(kernel, state["runId"])
    state = advance(workflow, state, user)
    assert state["status"] == "completed" and state["evidenceMode"] == "regression"
    assert kernel.workspace_runtime.get_output(project_id=pid, output_id=prior["outputId"]) == prior
    historical = kernel.project_store.get_artifact(
        pid, "test-plan", version=before_plan["artifactVersion"]
    )
    # Revision metadata transitions to superseded; assessments and evidence
    # in the historical content remain byte-equivalent JSON values.
    assert historical["lifecycleStatus"] == "superseded"
    assert historical["artifactVersion"] == before_plan["artifactVersion"]
    assert historical["content"] == before_plan["content"]


def test_verbose_failure_context_respects_existing_patch_contract(repair_env):
    kernel, pid, user, _, requests, write = repair_env
    write("analysis.py", b'raise RuntimeError("INJECTED_DEFECT " + "X" * 8000)\n')
    run = kernel.workspace_runtime.run_analysis(
        project_id=pid, artifact_type="analysis", actor=user
    )["executionRun"]
    assert wait(kernel, run["executionRunId"])["status"] == "failed"
    workflow = RepairWorkflow(kernel)
    state = advance(workflow, workflow.start(pid, user, run["executionRunId"], "analysis"), user)
    assert state["status"] == "review"
    assert len(requests[-1]["requestedChange"]) <= 4096
    assert state["attempts"][0]["diagnostics"]["logExcerptLimited"] is True
    logs = kernel.workspace_runtime.list_logs(
        project_id=pid, execution_run_id=run["executionRunId"]
    )
    assert sum(len(c["content"]) for c in logs["chunks"]) > 8000


@pytest.mark.parametrize(
    "stage,target,status",
    [
        ("test", "firmware", "failed"),
        ("simulate", "firmware", "failed"),
        ("analyze", "firmware", "failed"),
        ("compile", "analysis", "failed"),
        ("compile", "firmware", "completed"),
    ],
)
def test_build_scope_rejects_other_stages_and_targets(
    repair_env, monkeypatch, stage, target, status
):
    kernel, pid, user, failed, _, _ = repair_env
    workflow = RepairWorkflow(kernel)
    monkeypatch.setattr(workflow, "_stage", lambda run: stage)
    monkeypatch.setattr(
        workflow.runtime, "get_execution", lambda **kwargs: {"executionRun": {"status": status}}
    )
    with pytest.raises(BoardError, match="Build scope requires"):
        workflow.start(pid, user, failed["executionRunId"], target, scope="build")


def test_cases_without_test_plan(repair_env, monkeypatch):
    from nexus_persistence.errors import ArtifactNotFoundError

    kernel, pid, _, _, _, _ = repair_env

    def missing(*args, **kwargs):
        raise ArtifactNotFoundError("missing test-plan")

    monkeypatch.setattr(kernel.project_store, "get_artifact", missing)
    assert RepairWorkflow(kernel)._cases(pid, "run_missing") == []


@pytest.mark.parametrize(
    "code", ["ARCHITECTURE_UNSUPPORTED", "SIMULATOR_UNAVAILABLE", "WOKWI_CLI_MISSING"]
)
@pytest.mark.parametrize("phase", ["inspect", "running"])
def test_non_firmware_failure_stops_before_inspection(repair_env, monkeypatch, code, phase):
    kernel, pid, user, failed, requests, _ = repair_env
    workflow = RepairWorkflow(kernel)
    state = workflow.start(pid, user, failed["executionRunId"], "analysis")
    if phase == "running":
        state["status"] = "running"
        state = workflow._save(state, user)
    original = kernel.workspace_runtime.get_execution

    def get(**kwargs):
        result = original(**kwargs)
        result["executionRun"]["error"] = {
            "code": code,
            "message": "Simulation prerequisite unsupported",
        }
        return result

    monkeypatch.setattr(kernel.workspace_runtime, "get_execution", get)
    state = advance(workflow, state, user)
    assert state["status"] == "unavailable"
    assert state["errorCode"] == code
    assert not requests


def test_evidence_promotion_without_test_plan_is_structured(repair_env, monkeypatch):
    from nexus_board.services.verification_service import VerificationError
    from nexus_persistence.errors import ArtifactNotFoundError

    kernel, pid, _, failed, _, _ = repair_env
    run = {**failed, "status": "completed", "executionJobId": None}
    monkeypatch.setattr(kernel.verification._kernel, "get_execution_run", lambda _: run)

    def missing(*args, **kwargs):
        raise ArtifactNotFoundError("missing test-plan")

    monkeypatch.setattr(kernel.project_store, "get_artifact", missing)
    with pytest.raises(VerificationError) as error:
        kernel.verification.promote_execution_evidence(
            project_id=pid, execution_run_id=run["executionRunId"], actor=actor()
        )
    assert error.value.code == "TEST_PLAN_MISSING"


@pytest.mark.parametrize("repair_env", ["live"], indirect=True)
@pytest.mark.parametrize("noisy,slow", [(False, False), (True, False), (False, True)])
def test_materialized_imu_analysis_serial_metrics(repair_env: Any, noisy: bool, slow: bool) -> None:
    """Real analysis runner promotes schema-valid seeded metric criteria."""
    from nexus_board.verification.close import promote_analysis_evidence_into_test_plan
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        ExecutionPlanWorkflow,
    )

    kernel, pid, user, _, _, write = repair_env
    plan = kernel.project_store.get_artifact(pid, "execution-plan")["content"]
    rendered = ExecutionPlanWorkflow(kernel).render(plan)["analysis"]["analysis.py"]
    write("analysis.py", rendered)
    telemetry = (Path(__file__).parent / "fixtures" / "imu_serial.txt").read_bytes()
    if noisy:
        telemetry = telemetry.replace(b"0.01000", b"0.21000").replace(b"-0.01000", b"-0.21000")
    if slow:
        telemetry = (
            telemetry.replace(b"TEL,0.080,", b"TEL,0.160,")
            .replace(b"TEL,0.060,", b"TEL,0.120,")
            .replace(b"TEL,0.040,", b"TEL,0.080,")
            .replace(b"TEL,0.020,", b"TEL,0.040,")
        )
    write("data/serial.log", telemetry)
    run = kernel.workspace_runtime.run_analysis(
        project_id=pid, artifact_type="analysis", actor=user
    )["executionRun"]
    run = wait(kernel, run["executionRunId"])
    assert run["status"] == "completed", run
    summary, names, output_id, _ = kernel.verification._extract_run_evidence(run)
    assert summary is not None
    assert summary["inputPath"] == "data/serial.log"
    assert summary["inputSha256"] == hashlib.sha256(telemetry).hexdigest()
    assert summary["sampling_hz"] == pytest.approx(25 if slow else 50)
    assert summary["accel_x_rms_noise_g"] == pytest.approx(0.21 if noisy else 0.01)
    assert {"outputs/summary.json", "outputs/processed.csv", "outputs/accel_plot.png"} <= set(names)
    golden = json.loads(
        (
            ROOT
            / "packages/contracts/examples/valid/esp32-imu-vibration-monitor"
            / "test-plan-artifact.json"
        ).read_text()
    )["content"]
    assessed, changed = promote_analysis_evidence_into_test_plan(
        golden,
        summary=summary,
        produced_output_names=names,
        execution_run_id=run["executionRunId"],
        output_id=output_id,
    )
    assert changed
    cases = {c["displayId"]: c for c in assessed["testCases"]}
    assert cases["T6"]["assessment"] == ("FAIL" if slow else "PASS")
    assert cases["T7"]["assessment"] == ("FAIL" if noisy else "PASS")
    assert cases["T8"]["assessment"] == "PASS"
    seeded = kernel.project_store.get_artifact(pid, "test-plan")["content"]
    assessed, changed = promote_analysis_evidence_into_test_plan(
        seeded,
        summary=summary,
        produced_output_names=names,
        execution_run_id=run["executionRunId"],
        output_id=output_id,
    )
    assert changed
    cases = {c["displayId"]: c for c in assessed["testCases"]}
    assert cases["T6"]["assessment"] == ("FAIL" if slow else "PASS")
    assert cases["T7"]["assessment"] == ("FAIL" if noisy else "PASS")
    assert cases["T8"]["assessment"] == "PASS"
    assert all(cases[t]["assessmentAuthority"] == "deterministic-code" for t in ("T6", "T7", "T8"))


def test_generic_analysis_profile_remains_generic() -> None:
    from nexus_board.analysis.scaffold import get_analysis_scaffold_profile

    profile = get_analysis_scaffold_profile("python-analysis-v1")
    source = next(f.content for f in profile.files if f.path == "analysis.py")
    assert b'"status": "ok"' in source
    assert b"accel_x_rms_noise_g" not in source
    assert b"serial.log" not in source


@pytest.mark.parametrize("repair_env", ["live"], indirect=True)
@pytest.mark.parametrize("timestamp_field", ["time_ms", "time_s"])
def test_seeded_r5_telemetry_normalization(
    repair_env: Any, monkeypatch: Any, timestamp_field: str
) -> None:
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        ExecutionPlanWorkflow,
    )
    from nexus_persistence.errors import ArtifactNotFoundError

    kernel, pid, _, _, _, _ = repair_env
    original = kernel.project_store.get_artifact
    requirements = copy.deepcopy(original(pid, "requirement-set"))
    r5 = next(r for r in requirements["content"]["requirements"] if r["displayId"] == "R5")
    r5["statement"] = (
        "Firmware streams acceleration telemetry in a machine-readable form "
        f"containing {timestamp_field}, accel_x_g, accel_y_g, and accel_z_g."
    )
    plan = copy.deepcopy(original(pid, "execution-plan"))
    captured: dict[str, Any] = {}

    def get(project_id: str, kind: str) -> Any:
        if kind == "test-plan":
            raise ArtifactNotFoundError("missing")
        if kind == "requirement-set":
            return requirements
        return original(project_id, kind)

    monkeypatch.setattr(kernel.project_store, "get_artifact", get)
    monkeypatch.setattr(
        kernel.project_store, "apply_accepted_artifact_revision", lambda **kw: captured.update(kw)
    )
    ExecutionPlanWorkflow(kernel)._seed_test_plan(pid, plan)
    cases = captured["new_artifact"]["content"]["testCases"]
    baseline = original(pid, "test-plan")["content"]["testCases"]
    for other in cases:
        if other["linkedRequirementIds"] == [r5["requirementId"]]:
            continue
        unchanged = next(
            c for c in baseline if c["linkedRequirementIds"] == other["linkedRequirementIds"]
        )
        assert other["criterion"] == unchanged["criterion"]
        assert other["verificationMethod"] == unchanged["verificationMethod"]
        assert other["expectedResult"] == unchanged["expectedResult"]
    case = next(c for c in cases if c["linkedRequirementIds"] == [r5["requirementId"]])
    assert case["verificationMethod"] == "execution-output"
    assert case["criterion"] == {"criterionType": "contains", "marker": "accel_x_g"}
    assert case["expectedResult"] == "Telemetry includes time_s, accel_x_g, accel_y_g, accel_z_g."


@pytest.mark.parametrize("repair_env", ["live"], indirect=True)
@pytest.mark.parametrize("changed_statement", [False, True])
def test_unmapped_objective_stays_manual(
    repair_env: Any, monkeypatch: Any, changed_statement: bool
) -> None:
    from nexus_board.verification.close import (
        promote_analysis_evidence_into_test_plan,
        promote_marker_evidence_into_test_plan,
    )
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        ExecutionPlanWorkflow,
    )
    from nexus_persistence.errors import ArtifactNotFoundError

    kernel, pid, _, _, _, _ = repair_env
    original = kernel.project_store.get_artifact
    requirements = copy.deepcopy(original(pid, "requirement-set"))
    requirement = requirements["content"]["requirements"][0]
    if changed_statement:
        requirement["statement"] = "Unrelated R1 requirement."
    else:
        requirement["displayId"] = "R99"
        requirement["statement"] = "An unknown objective."
    plan = copy.deepcopy(original(pid, "execution-plan"))
    plan["content"]["plan"]["verificationObjectives"] = [
        plan["content"]["plan"]["verificationObjectives"][0]
    ]
    captured: dict[str, Any] = {}

    def get(project_id: str, kind: str) -> Any:
        if kind == "test-plan":
            raise ArtifactNotFoundError("missing")
        if kind == "requirement-set":
            return requirements
        return original(project_id, kind)

    monkeypatch.setattr(kernel.project_store, "get_artifact", get)
    monkeypatch.setattr(
        kernel.project_store, "apply_accepted_artifact_revision", lambda **kw: captured.update(kw)
    )
    ExecutionPlanWorkflow(kernel)._seed_test_plan(pid, plan)
    content = captured["new_artifact"]["content"]
    case = content["testCases"][0]
    assert case["verificationMethod"] == "manual"
    assert "criterion" not in case
    promoted, _ = promote_analysis_evidence_into_test_plan(
        content,
        summary={"sampling_hz": 50},
        produced_output_names=[],
        execution_run_id="run_unknown",
    )
    promoted, _ = promote_marker_evidence_into_test_plan(
        promoted, log_text="NEXUS_MPU_READY", execution_run_id="run_unknown"
    )
    assert promoted == content


@pytest.mark.parametrize("repair_env", ["live"], indirect=True)
@pytest.mark.parametrize("ready", [False, True])
def test_seeded_marker_promotion(repair_env: Any, ready: bool) -> None:
    from nexus_board.verification.close import promote_marker_evidence_into_test_plan
    from nexus_contracts.validation.schema_validator import validate_against_schema_id

    kernel, pid, _, _, _, _ = repair_env
    artifact = kernel.project_store.get_artifact(pid, "test-plan")
    assert not validate_against_schema_id(
        artifact, "https://nexus.local/schemas/artifacts/artifact.v1.schema.json"
    )
    promoted, changed = promote_marker_evidence_into_test_plan(
        artifact["content"],
        log_text="NEXUS_MPU_READY accel_x_g" if ready else "boot failed",
        execution_run_id="run_marker",
    )
    assert changed
    cases = {c["displayId"]: c for c in promoted["testCases"]}
    for tid in ("T1", "T4", "T5"):
        assert cases[tid]["assessment"] == ("PASS" if ready else "FAIL")
        assert cases[tid]["assessmentAuthority"] == "deterministic-code"
        assert cases[tid]["executionRunId"] == "run_marker"
    assert all("assessment" not in cases[tid] for tid in ("T2", "T3"))


@pytest.fixture
def inspection_env(monkeypatch: Any) -> Any:
    """Exercise evidence extraction and the request bound without scheduling repairs."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    runtime = Mock()
    runtime.get_execution.return_value = {
        "executionRun": {
            "status": "completed",
            "inputSnapshotId": "snap_sim",
            "outputReferences": ["out_serial"],
        }
    }
    runtime.list_outputs_for_run.return_value = {"outputs": []}
    runtime.propose_firmware_patch.return_value = {
        "proposal": {"proposalId": "prop_repair", "generatorMetadata": {"mode": "llm"}}
    }
    kernel = SimpleNamespace(workspace_runtime=runtime)
    workflow = RepairWorkflow(kernel)
    golden = json.loads(
        (
            ROOT
            / "packages/contracts/examples/valid/esp32-imu-vibration-monitor"
            / "test-plan-artifact.json"
        ).read_text()
    )["content"]["testCases"]
    cases = [copy.deepcopy(c) for c in golden if c["displayId"] in {"T1", "T4", "T5"}]
    for case in cases:
        case.update(assessment="FAIL", status="failed", actualResult="NEXUS_MPU_INIT_FAIL")
    monkeypatch.setattr(workflow, "_cases", lambda *_: cases)
    monkeypatch.setattr(workflow, "_save", lambda state, _: state)
    state = {
        "projectId": "proj_sim",
        "runId": "run_sim",
        "repairId": "repair_sim",
        "stage": "simulate",
        "target": "firmware",
        "attempts": [{"runIds": ["run_sim"]}],
        "maxAttempts": 3,
    }
    return workflow, runtime, state, cases


def serial_output(text: str, *, truncated: bool = False) -> dict[str, Any]:
    return {
        "name": "serial.log",
        "outputType": "log",
        "content": {
            "kind": "inline-structured",
            "structuredResult": {"text": text, "truncated": truncated},
        },
    }


def inspect_diagnostics(env: Any) -> Any:
    workflow, runtime, state, _ = env
    workflow._inspect(state, actor())
    assert state["status"] == "review"
    runtime.propose_firmware_patch.assert_called_once()
    assert len(runtime.propose_firmware_patch.call_args.kwargs["requested_change"]) <= 4096
    runtime.list_logs.assert_not_called()
    return state["attempts"][0]["diagnostics"]


def test_simulation_failure_populates_log_excerpt_from_serial_output(inspection_env: Any) -> None:
    _, runtime, _, cases = inspection_env
    text = "NEXUS_MPU_INIT_FAIL\nWire NACK at address 0x69\n"
    runtime.list_outputs_for_run.return_value = {"outputs": [serial_output(text)]}
    original = copy.deepcopy(cases)
    diagnostics = inspect_diagnostics(inspection_env)
    assert diagnostics["logExcerpt"] == text
    assert diagnostics["logExcerptLimited"] is False
    assert diagnostics["job"] == {"exitCode": None, "failure": None, "logTruncated": None}
    assert cases == original


@pytest.mark.parametrize("output_lookup_fails", [False, True])
def test_simulation_failure_falls_back_to_test_case_actual_result(
    inspection_env: Any, output_lookup_fails: bool
) -> None:
    _, runtime, _, cases = inspection_env
    # Missing outputs and a failed lookup both leave the linked case evidence usable.
    cases[0]["actualResult"] = "NEXUS_MPU_INIT_FAIL (contains 'NEXUS_MPU_READY')"
    if output_lookup_fails:
        runtime.list_outputs_for_run.side_effect = BoardError("Output unavailable")
    diagnostics = inspect_diagnostics(inspection_env)
    assert diagnostics["logExcerpt"] == cases[0]["actualResult"]
    assert diagnostics["logExcerptLimited"] is False


def test_simulation_verbose_serial_log_respects_4096_budget(inspection_env: Any) -> None:
    _, runtime, _, _ = inspection_env
    text = "START_BOOT\n" + "NEXUS_MPU_INIT_FAIL 0x69\n" * 400 + "END_LOG\n"
    runtime.list_outputs_for_run.return_value = {"outputs": [serial_output(text)]}
    diagnostics = inspect_diagnostics(inspection_env)
    assert diagnostics["logExcerptLimited"] is True
    assert diagnostics["logExcerpt"].startswith("START_BOOT\n")
    assert diagnostics["logExcerpt"].endswith("END_LOG\n")
    assert runtime.list_outputs_for_run.return_value["outputs"][0] == serial_output(text)


def test_simulation_multi_case_actual_result_bounded_in_diagnostics(inspection_env: Any) -> None:
    _, runtime, _, cases = inspection_env
    text = "START_BOOT\n" + "NEXUS_MPU_INIT_FAIL 0x69\n" * 400 + "END_LOG\n"
    for case in cases:
        case["actualResult"] = text
    original = copy.deepcopy(cases)
    runtime.list_outputs_for_run.return_value = {"outputs": [serial_output(text)]}
    diagnostics = inspect_diagnostics(inspection_env)
    assert len(diagnostics["testCases"]) == 3
    for case in diagnostics["testCases"]:
        assert len(case["actualResult"]) <= 400
        assert case["actualResult"].startswith("START_BOOT\n")
        assert case["actualResult"].endswith("END_LOG\n")
    assert diagnostics["logExcerptLimited"] is True
    assert cases == original


def test_compile_stage_repair_ignores_serial_outputs(inspection_env: Any) -> None:
    workflow, runtime, state, _ = inspection_env
    state["stage"] = "compile"
    job = {"exitCode": 1, "failure": "compiler failed", "logTruncated": False}
    runtime.get_execution.return_value["executionJob"] = job
    runtime.list_logs.return_value = {"chunks": [{"content": "INJECTED_DEFECT: compiler error"}]}
    runtime.list_outputs_for_run.return_value = {"outputs": [serial_output("DECOY_SIM_LOG")]}
    workflow._inspect(state, actor())
    assert state["status"] == "review"
    diagnostics = state["attempts"][0]["diagnostics"]
    assert diagnostics["logExcerpt"] == "INJECTED_DEFECT: compiler error"
    assert diagnostics["logExcerptLimited"] is False
    assert diagnostics["job"] == job
    assert diagnostics["testCases"] == []
    runtime.list_outputs_for_run.assert_not_called()
    runtime.list_logs.assert_called_once_with(
        project_id=state["projectId"], execution_run_id=state["runId"], limit=100
    )
