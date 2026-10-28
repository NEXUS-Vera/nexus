"""W5 regression evidence: scripted gateway, actual Python jobs and guarded review."""

import copy
import hashlib
import json
import os
import time
from pathlib import Path

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
            c["status"] == "planned" and "criterion" not in c
            for c in seeded["content"]["testCases"]
        )
        workflow.retry_materialization(
            pid,
            user,
            ps.get_artifact(pid, "execution-plan")["artifactId"],
            ps.get_project(pid)["currentStateVersion"],
        )
        assert ps.get_artifact(pid, "test-plan") == seeded
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
    "repair_env,simulator",
    [
        (None, "ready"),
        (None, "unavailable"),
        (None, "failed"),
        (None, "firmware-test"),
        ("live", "live"),
    ],
    indirect=["repair_env"],
)
def test_firmware_defect_repair_reruns_existing_w4_path(
    repair_env, monkeypatch, tmp_path, simulator
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

    def correction(_task, payload, _schema):
        assert "INJECTED_DEFECT: compiler regression error" in payload["requestedChange"]
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
                {"operationType": "replace-file", "path": "src/main.cpp", "content": source}
            ]
        }

    gateway.set_script("firmware.patch-proposal", correction)
    kernel.workspace_runtime._firmware_patch_generator = LiveFirmwarePatchGenerator(
        gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
    )
    telemetry = b"NEXUS_MPU_READY\ntime_s,accel_x_g,accel_y_g,accel_z_g\n" + b"".join(
        f"TEL,{i / 50},0.01,0,1\n".encode() for i in range(100)
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
    acquire_edit_lease(
        kernel,
        project_id=pid,
        artifact_id=electrical["artifactId"],
        workspace_id=electrical["workspaceId"],
        requested_by=user,
    )
    workflow = RepairWorkflow(kernel)
    state = advance(
        workflow,
        workflow.start(pid, user, failed["executionRunId"], "firmware", require_real=False),
        user,
    )
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
    for _ in range(8):
        state = advance(workflow, state, user)
        if state["status"] == "running":
            wait(kernel, state["runId"])
        if state["status"] in {"completed", "stopped", "unavailable", "exhausted"}:
            break
        if simulator == "live" and state["stage"] == "analyze":
            break
        if simulator == "failed" and state["status"] == "inspect":
            break
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
        assert state["status"] == "inspect", str(state)
        assert not state.get("errorCode")
        return
    assert state["status"] == "completed", str(state)
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
