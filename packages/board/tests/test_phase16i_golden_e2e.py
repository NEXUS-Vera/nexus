"""Phase 16I golden full-system E2E: ESP32 IMU Vibration Monitor."""

from __future__ import annotations

import copy
import csv
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from golden.esp32_imu_vibration_monitor.consistency import (
    ANALYSIS_OUTPUTS,
    GOLDEN_PROMPT,
    validate_golden_consistency,
)
from helpers import acquire_edit_lease, actor, build_test_kernel, cmd
from nexus_board.analysis.semantics import assess_metric
from nexus_board.execution.runtime_factory import build_execution_runtime
from nexus_board.kernel import build_project_kernel
from nexus_board.services.verification_service import VerificationError
from nexus_circuit_simulation import MaterializationRequest, assess_support, materialize_workspace
from nexus_embedded_systems.workflows.layered_architecture import (
    ensure_layered_architecture_artifacts,
)
from nexus_embedded_systems.workflows.project_initialization.fixture_router import (
    FixtureRouteOutcome,
    route_fixture_family,
)
from nexus_embedded_systems.workflows.project_initialization.materializer import (
    materialize_fixture_package,
)
from nexus_persistence import InMemoryKernelStore, InMemoryProjectStore, LocalFileStore
from nexus_persistence.factory import build_stores

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "esp32_imu_vibration_monitor"
FIXTURE_FAMILY = "esp32-imu-vibration-monitor"
FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "valid"


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 60.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = kernel.executions.get_run(run_id)
        if run["status"] not in {"queued", "starting", "running", "cancelling"}:
            return run
        time.sleep(0.05)
    return kernel.executions.get_run(run_id)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_golden_prompt_routes_to_vibration_monitor_family() -> None:
    decision = route_fixture_family(GOLDEN_PROMPT)
    assert decision.outcome == FixtureRouteOutcome.MATCHED
    assert decision.family == FIXTURE_FAMILY


@pytest.mark.parametrize("fail_analysis", [False, True, "noise", "missing-metric"])
def test_golden_g1_fixture_full_system(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_analysis: bool | str,
) -> None:
    _run_golden_g1(monkeypatch, tmp_path, fail_analysis)


def _run_golden_g1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_analysis: bool | str,
    *,
    sqlite_url: str | None = None,
    file_store_root: Path | None = None,
    simulation_handoff: bool | str = False,
) -> dict[str, Any] | None:
    with ExitStack() as cleanup:
        return _execute_golden_g1(
            monkeypatch,
            tmp_path,
            cleanup,
            fail_analysis,
            sqlite_url=sqlite_url,
            file_store_root=file_store_root,
            simulation_handoff=simulation_handoff,
        )


def _execute_golden_g1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cleanup: ExitStack,
    fail_analysis: bool | str,
    *,
    sqlite_url: str | None = None,
    file_store_root: Path | None = None,
    simulation_handoff: bool | str = False,
) -> dict[str, Any] | None:
    """GOLDEN G1 — fixture generation, compile stub, real analysis and VERIFY."""
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    if simulation_handoff:
        monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    if simulation_handoff == "regression" or simulation_handoff is True:
        # Scripted compiler/runner regression evidence, never a live toolchain claim.
        monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
        pio = tmp_path / "pio"
        pio.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "p = Path('.pio/build/nexus')\n"
            "p.mkdir(parents=True, exist_ok=True)\n"
            "(p / 'firmware.elf').write_bytes(b'\\x7fELF\\x00REGRESSION_BUILD')\n"
            "(p / 'firmware.bin').write_bytes(b'REGRESSION_BIN')\n"
        )
        pio.chmod(0o755)
        from nexus_board.execution import process_runtime

        original_environment = process_runtime.build_sandbox_environment

        def regression_environment(entries):
            env = original_environment(entries)
            env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
            return env

        monkeypatch.setattr(process_runtime, "build_sandbox_environment", regression_environment)
        monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])

    decision = route_fixture_family(GOLDEN_PROMPT)
    assert decision.family == FIXTURE_FAMILY
    package, _id_map = materialize_fixture_package(
        FIXTURES_ROOT / FIXTURE_FAMILY,
        message=GOLDEN_PROMPT,
        autonomy_mode="collaborate",
    )
    artifacts = list(package["artifacts"])
    ensured = ensure_layered_architecture_artifacts(
        project_id=str(package["project"]["projectId"]),
        artifacts=artifacts,
        actor=artifacts[0].get("createdBy") if artifacts else None,
        turn_id=str(package["userTurn"]["turnId"]),
        workflow_run_id=str(package["workflowRun"]["workflowRunId"]),
        now=str(artifacts[0].get("updatedAt") or artifacts[0].get("createdAt")),
    )
    init_artifacts = list(ensured.get("artifacts") or artifacts)
    assert any(a["artifactType"] == "requirement-set" for a in init_artifacts)
    assert any(a["artifactType"] == "component-plan" for a in init_artifacts)
    assert any(a["artifactType"] == "electrical-architecture" for a in init_artifacts)

    by_type = {a["artifactType"]: a for a in init_artifacts}
    wokwi_request = MaterializationRequest(
        electrical_architecture=by_type["electrical-architecture"],
        component_plan=by_type["component-plan"],
    )
    wokwi_assessment = assess_support(wokwi_request)
    assert wokwi_assessment.status.value in {"SURROGATE_REQUIRED", "SUPPORTED"}
    wokwi_workspace = materialize_workspace(wokwi_request)
    diagram = json.loads(wokwi_workspace.files["diagram.json"])
    part_types = {str(p.get("type")) for p in diagram.get("parts") or []}
    assert "wokwi-esp32-devkit-v1" in part_types
    assert "wokwi-mpu6050" in part_types
    connections = {tuple(c[:2]) for c in (diagram.get("connections") or []) if isinstance(c, list)}
    assert ("mcu1:D21", "imu1:SDA") in connections or ("imu1:SDA", "mcu1:D21") in connections
    assert ("mcu1:D22", "imu1:SCL") in connections or ("imu1:SCL", "mcu1:D22") in connections
    assert any("$serialMonitor" in str(c) for c in (diagram.get("connections") or []))
    wokwi_support = {
        "status": wokwi_assessment.status.value,
        "partTypes": sorted(part_types),
        "connectionCount": len(diagram.get("connections") or []),
    }

    firmware_src = (GOLDEN_DIR / "main.cpp").read_text(encoding="utf-8")
    analysis_src = (GOLDEN_DIR / "analysis.py").read_text(encoding="utf-8")
    if fail_analysis is True:
        analysis_src += "\nraise SystemExit(1)\n"
    if fail_analysis == "missing-metric":
        # Simulate a completed producer omitting its metric while retaining PASS prose.
        analysis_src += (
            '\nsummary_path = OUT / "summary.json"\n'
            "summary = json.loads(summary_path.read_text())\n"
            'summary.pop("accel_x_rms_noise_g")\n'
            "summary_path.write_text(json.dumps(summary))\n"
        )
    findings = validate_golden_consistency(
        artifacts=init_artifacts,
        firmware_source=firmware_src,
        analysis_source=analysis_src,
        wokwi_support=wokwi_support,
    )
    assert findings == [], findings

    project_store: Any
    if sqlite_url is None:
        project_store = InMemoryProjectStore()
        ks = InMemoryKernelStore(project_store=project_store)
    else:
        project_store, ks = build_stores("sqlite", sqlite_url)
    package["artifacts"] = init_artifacts
    package["project"]["currentArtifactReferences"] = [
        {
            "artifactType": a["artifactType"],
            "artifactId": a["artifactId"],
            "artifactVersion": a["artifactVersion"],
            "contentSchemaVersion": a["contentSchemaVersion"],
        }
        for a in init_artifacts
    ]
    project_store.save_initialization_package(package)
    kernel_kwargs: dict[str, Any] = {}
    if file_store_root is not None:
        kernel_kwargs["file_store"] = LocalFileStore(file_store_root)
    kernel = build_project_kernel(ks, project_store=project_store, **kernel_kwargs)
    cleanup.callback(kernel.jobs.shutdown)
    user = actor("user")
    project_id = str(package["project"]["projectId"])

    # Firmware path
    fw = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=fw["artifactId"],
        workspace_id=fw["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(fw["baseArtifactVersion"]),
        base_project_state_version=int(fw["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(fw["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=fw["workspaceId"],
        path="src/main.cpp",
        content=firmware_src.encode("utf-8"),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(fw["baseArtifactVersion"]),
        base_project_state_version=int(fw["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    draft = ks.get_draft(fw["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=fw["workspaceId"],
        path="platformio.ini",
        content=(GOLDEN_DIR / "platformio.ini").read_bytes(),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(fw["baseArtifactVersion"]),
        base_project_state_version=int(fw["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    compiled = kernel.workspace_runtime.compile_firmware(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    fw_run = _wait_run(kernel, compiled["executionRun"]["executionRunId"])
    assert fw_run["status"] == "completed", fw_run.get("error")
    fw_outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=fw_run["executionRunId"]
    )["outputs"]
    fw_names = {o.get("name") for o in fw_outputs}
    assert any("firmware.elf" in str(n) for n in fw_names)

    serial_output = None
    if simulation_handoff:
        import hashlib

        from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
        from nexus_circuit_simulation import RunnerResult, WokwiProvider

        elf = next(o for o in fw_outputs if o["name"].endswith("firmware.elf"))
        elf_bytes = kernel.filesystem.file_store.get(elf["content"]["uri"])
        telemetry = b"NEXUS_MPU_READY\n" + b"".join(
            f"TEL,{i / 50},0.01,0,1\n".encode() for i in range(100)
        )

        class RegressionRunner:
            def run(self, request):
                if request.arguments[0] == "lint":
                    return RunnerResult(exit_code=0, timed_out=False)
                assert request.files["firmware.elf"] == elf_bytes
                assert (
                    "sha256:" + hashlib.sha256(request.files["firmware.elf"]).hexdigest()
                    == elf["contentDigest"]
                )
                return RunnerResult(exit_code=0, timed_out=False, outputs={"serial.log": telemetry})

        provider = (
            WokwiProvider(token=os.environ.get("WOKWI_CLI_TOKEN"))
            if simulation_handoff == "live"
            else WokwiProvider(executable=pio, token="regression-only", runner=RegressionRunner())
        )
        adapter = CircuitSimulationExecutionAdapter(
            provider=provider,
            project_store=project_store,
            kernel_store=ks,
            file_store=kernel.filesystem.file_store,
        )
        kernel.executions._capability_executors["circuit-simulation"] = adapter
        cap = kernel.executions._capabilities
        cap.register(
            {
                "schemaVersion": "1.0.0",
                "capabilityId": "circuit-simulation",
                "displayName": "Regression simulator",
                "providerId": "wokwi",
                "available": True,
            }
        )
        electrical = kernel.workspace_runtime.resolve_binding(
            project_id=project_id, artifact_type="electrical-architecture", actor=user
        )
        acquire_edit_lease(
            kernel,
            project_id=project_id,
            artifact_id=electrical["artifactId"],
            workspace_id=electrical["workspaceId"],
            requested_by=user,
        )
        snap = kernel.workspaces.create_snapshot(
            workspace_id=electrical["workspaceId"], actor=user, reason="before-execution"
        )
        dispatched = kernel.dispatch(
            cmd(
                command_type="artifact.execute",
                project_id=project_id,
                artifact_id=electrical["artifactId"],
                workspace_id=electrical["workspaceId"],
                requested_by=user,
                input_data={
                    "snapshotId": snap["snapshotId"],
                    "capability": "circuit-simulation",
                    "firmwareOutputId": elf["outputId"],
                },
            )
        )
        assert dispatched["status"] == "completed", dispatched
        simulated = {
            "executionRun": ks.get_execution_run(dispatched["executionRunId"]),
            "outputs": kernel.workspace_runtime.list_outputs_for_run(
                project_id=project_id, execution_run_id=dispatched["executionRunId"]
            )["outputs"],
        }
        assert simulated["executionRun"]["inputOutputReferences"] == [elf["outputId"]]
        serial_output = next(o for o in simulated["outputs"] if o["name"] == "serial.log")
        if simulation_handoff == "live":
            telemetry = serial_output["content"]["structuredResult"]["text"].encode()
            assert b"TEL," in telemetry
        else:
            assert serial_output["content"]["structuredResult"]["text"].encode() == telemetry
        assert elf["outputId"] in serial_output["provenance"]["derivedFromIds"]
        assert all(o["evidenceStatus"] == "unverified" for o in simulated["outputs"])

    # Analysis path
    an = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=an["artifactId"],
        workspace_id=an["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(an["workspaceId"])
    kernel.workspace_runtime.upsert_analysis_investigation(
        project_id=project_id,
        artifact_type="analysis",
        investigation={
            "schemaVersion": "1.0.0",
            "investigationId": "ainv_GOLDENVIBRATIONMONITOR0001",
            "title": "Stationary IMU noise verification",
            "purpose": "verification",
            "question": "Is demeaned accel_x RMS noise below 0.10 g?",
            "linkedRequirementIds": ["R7"],
            "linkedComponentIds": [],
            "linkedTestPlanIds": [],
            "linkedEvidenceIds": [],
            "lifecycleStage": "VERIFY",
            "verificationCriterion": {
                "metricId": "accel_x_rms_noise_g",
                "operator": "<",
                "threshold": 0.10,
                "unit": "g",
            },
            "stageVocabulary": ["INPUTS", "TRANSFORM", "METRICS", "VISUALIZATION", "VERIFY"],
        },
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(an["workspaceId"])
    dataset = (GOLDEN_DIR / "stationary_imu.csv").read_bytes()
    if fail_analysis == "noise":
        lines = dataset.decode().splitlines()
        dataset = (
            lines[0]
            + "\n"
            + "\n".join(f"{i / 50},{0.2 if i % 2 else -0.2},0,1" for i in range(100))
            + "\n"
        ).encode()
    if serial_output:
        kernel.workspace_runtime.import_produced_output_into_analysis_input(
            project_id=project_id,
            artifact_type="analysis",
            output_id=serial_output["outputId"],
            path="data/serial.log",
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(an["baseArtifactVersion"]),
            base_project_state_version=int(an["baseProjectStateVersion"]),
        )
    else:
        kernel.workspace_runtime.write_analysis_input_file(
            project_id=project_id,
            artifact_type="analysis",
            path="data/stationary_imu.csv",
            content=dataset,
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(an["baseArtifactVersion"]),
            base_project_state_version=int(an["baseProjectStateVersion"]),
            media_type="text/csv",
        )
    draft = ks.get_draft(an["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=an["workspaceId"],
        path="analysis.py",
        content=analysis_src.encode("utf-8"),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )

    # Real analysis.py execution (not analysis stub) via ProcessRuntime
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    an_run = _wait_run(kernel, started["executionRun"]["executionRunId"])
    if simulation_handoff:
        assert serial_output is not None
        analysis_outputs = kernel.workspace_runtime.list_outputs_for_run(
            project_id=project_id, execution_run_id=an_run["executionRunId"]
        )["outputs"]
        summary_output = next(o for o in analysis_outputs if o["name"] == "outputs/summary.json")
        content = summary_output["content"]
        summary = json.loads(
            kernel.filesystem.file_store.get(content["uri"])
            if content["kind"] == "storage-reference"
            else content["structuredResult"]["text"]
        )
        snapshot = ks.get_snapshot(an_run["inputSnapshotId"])
        imported_entry = next(
            entry
            for entry in snapshot["content"]["filesystemManifest"]["entries"]
            if entry["path"] == "data/serial.log"
        )
        assert imported_entry["generatedFrom"] == f"imported-output:{serial_output['outputId']}"
        assert summary_output["executionRunId"] == an_run["executionRunId"]
        assert summary["inputSha256"] == hashlib.sha256(telemetry).hexdigest()
        assert summary["sampleCount"] > 0
        if simulation_handoff != "live":
            assert summary["sampleCount"] == 100
        assert summary["assessment"] == "PASS"
        return None
    if fail_analysis is True:
        assert an_run["status"] == "failed", an_run
        before = project_store.get_artifact(project_id, "test-plan")
        coverage_before = kernel.verification.requirement_verification_projection(project_id)
        with pytest.raises(VerificationError, match="completed"):
            kernel.verification.promote_execution_evidence(
                project_id=project_id,
                execution_run_id=an_run["executionRunId"],
                actor=user,
                accept=True,
            )
        assert project_store.get_artifact(project_id, "test-plan") == before
        assert (
            kernel.verification.requirement_verification_projection(project_id) == coverage_before
        )
        return
    assert an_run["status"] == "completed", an_run
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=an_run["executionRunId"]
    )["outputs"]
    names = {o.get("name") for o in outputs}
    for required in ANALYSIS_OUTPUTS:
        assert required in names, names

    summary_preview = None
    for out in outputs:
        if out.get("name") == "outputs/summary.json":
            preview = kernel.workspace_runtime.preview_analysis_output(
                project_id=project_id, output_id=out["outputId"]
            )
            summary_preview = json.loads(preview["text"])
            break
    assert summary_preview is not None
    if fail_analysis in {"noise", "missing-metric"}:
        missing_metric = fail_analysis == "missing-metric"
        expected_state = "INCONCLUSIVE" if missing_metric else "FAILED"
        expected_assessment = "INCONCLUSIVE" if missing_metric else "FAIL"
        if missing_metric:
            assert "accel_x_rms_noise_g" not in summary_preview
            assert "metricValue" not in summary_preview
            assert summary_preview["assessment"] == "PASS"
        else:
            assert summary_preview["accel_x_rms_noise_g"] == pytest.approx(0.20)
            assert summary_preview["assessment"] == "FAIL"
        before = project_store.get_artifact(project_id, "test-plan")
        original_case = next(c for c in before["content"]["testCases"] if c["displayId"] == "T7")
        promotion = kernel.verification.promote_execution_evidence(
            project_id=project_id,
            execution_run_id=an_run["executionRunId"],
            actor=user,
            accept=True,
        )
        assert promotion["changed"] is True
        assert promotion["accepted"] is True
        after = project_store.get_artifact(project_id, "test-plan")
        assert after["artifactVersion"] == before["artifactVersion"] + 1
        case = next(c for c in after["content"]["testCases"] if c["displayId"] == "T7")
        assert case["criterion"] == original_case["criterion"]
        assert case["verificationMethod"] == "analysis"
        assert case["assessment"] == expected_assessment
        assert case["status"] == ("inconclusive" if missing_metric else "failed")
        rows = kernel.verification.requirement_verification_projection(project_id)
        r7 = next(r for r in rows if r["displayId"] == "R7")
        assert r7["verificationState"] == expected_state
        assert r7["verificationState"] != "VERIFIED"
        chain = kernel.verification.evidence_chain(project_id)
        evidence = next(r for r in chain if r["requirementId"] == "R7")
        assert evidence["testId"] == "T7"
        assert evidence["verificationState"] == expected_state
        assert evidence["assessment"] == expected_assessment
        assert evidence["assessmentAuthority"] == "deterministic-code"
        assert evidence["criterion"]["metricId"] == "accel_x_rms_noise_g"
        assert evidence["criterion"]["operator"] == "<"
        assert evidence["criterion"]["expectedValue"] == 0.10
        assert evidence["executionRunId"] == an_run["executionRunId"]
        summary_output = next(o for o in outputs if o["name"] == "outputs/summary.json")
        assert summary_output["outputId"] in case["producedOutputIds"]
        assert evidence["evidenceReferences"]
        assert all(
            ref["sourceId"] == an_run["executionRunId"] for ref in evidence["evidenceReferences"]
        )
        # M3: trace evidence to the exact immutable input revision.
        assert an_run["baseArtifactVersion"] == an["baseArtifactVersion"]
        assert an_run["baseProjectStateVersion"] == an["baseProjectStateVersion"]
        snapshot = kernel.workspace_runtime.read_analysis_snapshot_file(
            project_id=project_id,
            artifact_type="analysis",
            snapshot_id=an_run["inputSnapshotId"],
            path="data/stationary_imu.csv",
        )
        assert snapshot["snapshotId"] == an_run["inputSnapshotId"]
        assert snapshot["content"].encode() == dataset
        script_snapshot = kernel.workspace_runtime.read_analysis_snapshot_file(
            project_id=project_id,
            artifact_type="analysis",
            snapshot_id=an_run["inputSnapshotId"],
            path="analysis.py",
        )
        assert script_snapshot["content"] == analysis_src
        if not missing_metric:
            _write_report(
                tmp_path / "defect.json",
                {"R7": "FAILED", "summary": summary_preview, "evidence": evidence},
            )
            print("DEFECT: R7 FAILED; injected 0.20 g RMS input; evidence=" + json.dumps(evidence))
        if sqlite_url is not None:
            return _capture_golden_restart_state(kernel, project_id, an_run)
        return
    assert summary_preview["assessment"] == "PASS"
    assert summary_preview["authority"] == "deterministic-code"
    assert (
        assess_metric(
            metric_value=float(summary_preview["accel_x_rms_noise_g"]),
            operator="<",
            threshold=0.10,
        )
        == "PASS"
    )

    findings2 = validate_golden_consistency(
        artifacts=init_artifacts,
        firmware_source=firmware_src,
        analysis_source=analysis_src,
        analysis_summary=summary_preview,
        wokwi_support=wokwi_support,
    )
    assert findings2 == []

    assert summary_preview["accel_x_rms_noise_g"] == pytest.approx(0.015676464092948383)
    before = project_store.get_artifact(project_id, "test-plan")
    promoted = kernel.verification.promote_execution_evidence(
        project_id=project_id,
        execution_run_id=an_run["executionRunId"],
        actor=user,
        accept=True,
    )
    assert promoted["changed"] and promoted["accepted"]
    after = project_store.get_artifact(project_id, "test-plan")
    assert after["artifactVersion"] > before["artifactVersion"]
    rows = kernel.verification.requirement_verification_projection(project_id)
    assert next(r for r in rows if r["displayId"] == "R7")["verificationState"] == "VERIFIED"
    assert next(r for r in rows if r["displayId"] == "R8")["verificationState"] == "VERIFIED"
    chain = kernel.verification.evidence_chain(project_id)
    r7 = next(r for r in chain if r["requirementId"] == "R7")
    assert r7["assessment"] == "PASS"
    assert r7["assessmentAuthority"] == "deterministic-code"
    assert r7["evidenceReferences"]
    for requirement_id in ("R7", "R8"):
        evidence = next(r for r in chain if r["requirementId"] == requirement_id)
        assert evidence["assessment"] == "PASS"
        assert any(
            ref["sourceId"] == an_run["executionRunId"] for ref in evidence["evidenceReferences"]
        )
    again = kernel.verification.promote_execution_evidence(
        project_id=project_id,
        execution_run_id=an_run["executionRunId"],
        actor=user,
        accept=True,
    )
    assert again["idempotent"] and not again["changed"]
    risks = promoted["riskMitigationAnnotations"]
    assert next(r for r in risks if r["displayId"] == "K6")["status"] == "monitoring"
    evidence_gap = "PASS — executed analysis outputs promoted into accepted Test Plan"
    report = {
        "schemaVersion": "1.0.0",
        "gate": "GOLDEN_G1",
        "projectId": project_id,
        "prompt": GOLDEN_PROMPT,
        "fixtureFamily": FIXTURE_FAMILY,
        "wokwi": {
            "translation": wokwi_support,
            "live": "GAP — ENVIRONMENT/HARNESS",
        },
        "firmware": {
            "executionRunId": fw_run["executionRunId"],
            "snapshotId": compiled["executionSnapshotId"],
            "status": fw_run["status"],
            "outputNames": sorted(str(n) for n in fw_names if n),
            "runtimeIdentity": fw_run.get("runtimeIdentity"),
        },
        "analysis": {
            "executionRunId": an_run["executionRunId"],
            "snapshotId": started["executionSnapshotId"],
            "status": an_run["status"],
            "outputNames": sorted(str(n) for n in names if n),
            "runtimeIdentity": an_run.get("runtimeIdentity"),
            "r7": summary_preview,
        },
        "consistencyFindings": findings2,
        "evidenceTrace": evidence_gap,
        "requirementVerification": rows,
        "humanReadable": {
            "title": "NEXUS GOLDEN PROJECT RESULT",
            "stages": {
                "Brief": "PASS",
                "Requirements": "PASS",
                "Functional Architecture": "PASS",
                "Components": "PASS",
                "Electrical Architecture": "PASS",
                "Wokwi Translation": "PASS",
                "Wokwi Live": "GAP — ENVIRONMENT/HARNESS",
                "Firmware Generation": "PASS",
                "Firmware Compile": "STUB PASS — no live build evidence",
                "ELF/BIN": "STUB outputs",
                "Analysis Generation": "PASS",
                "Analysis Execution": "PASS",
                "JSON/CSV/PNG": "PASS",
                "R7 Assessment": "PASS",
                "Cross-artifact consistency": "PASS",
                "Evidence Traceability": evidence_gap,
            },
        },
        "result": "PASS",
    }
    if sqlite_url is not None:
        return _capture_golden_restart_state(kernel, project_id, an_run)
    # Preserve the evidence basis, then accept a changed requirement through the store.
    requirement = project_store.get_artifact(project_id, "requirement-set")
    basis_version = requirement["artifactVersion"]
    changed = copy.deepcopy(requirement)
    from nexus_board.ids import new_id

    changed["artifactId"] = new_id("art")
    changed["supersedesArtifactId"] = requirement["artifactId"]
    changed["supersedesArtifactVersion"] = basis_version
    changed["artifactVersion"] += 1
    r7_requirement = next(r for r in changed["content"]["requirements"] if r["displayId"] == "R7")
    r7_requirement["statement"] = "Stationary accel_x RMS noise shall be below 0.01 g."
    project_store.apply_accepted_artifact_revision(
        project_id=project_id,
        new_artifact=changed,
        next_state_version=project_store.get_project(project_id)["currentStateVersion"] + 1,
        updated_at=changed["updatedAt"],
    )
    kernel.invalidation.process(project_id, requirement, changed)
    stale_rows = kernel.verification.requirement_verification_projection(project_id)
    r7_state = next(r for r in stale_rows if r["displayId"] == "R7")["verificationState"]
    assert r7_state == "STALE"
    current_version = project_store.get_artifact(project_id, "requirement-set")["artifactVersion"]
    assert current_version > basis_version
    report["requirementVerification"] = stale_rows
    report["evidenceFreshness"] = {
        "status": r7_state,
        "basisRequirementVersion": basis_version,
        "currentRequirementVersion": current_version,
        "note": "Accepted requirement revision invalidates the product verification projection.",
    }
    _write_report(tmp_path / "golden-g1.json", report)
    print("FIXTURE: R7 VERIFIED; RMS=" + str(summary_preview["accel_x_rms_noise_g"]))
    print("REQUIREMENT CHANGE: evidence STALE; " + json.dumps(report["evidenceFreshness"]))


def _capture_golden_restart_state(
    kernel: Any, project_id: str, run: dict[str, Any]
) -> dict[str, Any]:
    return copy.deepcopy(
        {
            "projectId": project_id,
            "board": kernel.get_board(project_id),
            "projection": kernel.verification.requirement_verification_projection(project_id),
            "chain": kernel.verification.evidence_chain(project_id),
            "run": run,
            "inputs": {
                path: kernel.workspace_runtime.read_analysis_snapshot_file(
                    project_id=project_id,
                    artifact_type="analysis",
                    snapshot_id=run["inputSnapshotId"],
                    path=path,
                )
                for path in ("analysis.py", "data/stationary_imu.csv")
            },
        }
    )


def _assert_golden_restart_preserves_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_analysis: bool | str,
    expected_state: str,
    *,
    durable_files: bool,
) -> None:
    url = f"sqlite:///{tmp_path / 'golden.sqlite3'}"
    file_root = tmp_path / "file-store" if durable_files else None
    # Only detached data returns; the helper shuts down jobs and retains no
    # bound finalizer for the original kernel before fresh stores are built.
    before = _run_golden_g1(
        monkeypatch, tmp_path, fail_analysis, sqlite_url=url, file_store_root=file_root
    )
    assert before is not None
    r7 = next(row for row in before["projection"] if row["displayId"] == "R7")
    assert r7["verificationState"] == expected_state
    evidence = next(row for row in before["chain"] if row["requirementId"] == "R7")
    assert evidence["evidenceReferences"]
    assert evidence["executionRunId"] == before["run"]["executionRunId"]
    assert evidence["assessmentAuthority"] == "deterministic-code"
    assert evidence["criterion"]["metricId"] == "accel_x_rms_noise_g"
    assert evidence["criterion"]["expectedValue"] == 0.10

    projects, store = build_stores("sqlite", url)
    kernel_kwargs: dict[str, Any] = {}
    if file_root is not None:
        kernel_kwargs["file_store"] = LocalFileStore(file_root)
    kernel = build_project_kernel(store, project_store=projects, **kernel_kwargs)
    try:
        run = store.get_execution_run(before["run"]["executionRunId"])
        assert run == before["run"]
        assert kernel.get_board(before["projectId"]) == before["board"]
        assert (
            kernel.verification.requirement_verification_projection(before["projectId"])
            == before["projection"]
        )
        assert kernel.verification.evidence_chain(before["projectId"]) == before["chain"]
        after = _capture_golden_restart_state(kernel, before["projectId"], run)
        # Full equality includes verified counts, evidence IDs, criterion,
        # execution links, deterministic authority, and snapshot file contents.
        assert after == before
    finally:
        kernel.jobs.shutdown()


@pytest.mark.parametrize(
    "fail_analysis, expected_state", [(False, "VERIFIED"), ("noise", "FAILED")]
)
def test_golden_g1_sqlite_restart_preserves_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_analysis: bool | str,
    expected_state: str,
) -> None:
    """M2: promoted evidence and its immutable inputs survive fresh SQLite + file stores."""
    _assert_golden_restart_preserves_verification(
        monkeypatch, tmp_path, fail_analysis, expected_state, durable_files=True
    )


def test_golden_g1_sqlite_restart_default_file_store_preserves_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default SQLite storage preserves immutable snapshot bytes after restart."""
    monkeypatch.delenv("NEXUS_FILE_STORE_ROOT", raising=False)
    _assert_golden_restart_preserves_verification(
        monkeypatch, tmp_path, False, "VERIFIED", durable_files=False
    )


@pytest.mark.skipif(
    os.environ.get("RUN_GOLDEN_DOCKER", "0") != "1"
    or shutil.which(os.environ.get("NEXUS_EXEC_DOCKER", "docker")) is None,
    reason="Set RUN_GOLDEN_DOCKER=1 with Docker images for GOLDEN G2",
)
def test_golden_g2_fixture_live_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    fw_image = os.environ.get(
        "NEXUS_FIRMWARE_CONTAINER_IMAGE", "nexus-firmware-platformio-esp32:1.0.0"
    )
    # Analysis uses NEXUS_EXEC_CONTAINER_IMAGE
    monkeypatch.setenv(
        "NEXUS_EXEC_CONTAINER_IMAGE",
        os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "nexus-python-analysis:1.0.0"),
    )
    runtime = build_execution_runtime(
        "container",
        container_image=os.environ["NEXUS_EXEC_CONTAINER_IMAGE"],
    )
    kernel, _ps, ks, project_id = build_test_kernel(
        auto_start_scheduler=True,
        execution_runtime=runtime,
    )
    user = actor("user")
    an = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=an["artifactId"],
        workspace_id=an["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(an["workspaceId"])
    kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/stationary_imu.csv",
        content=(GOLDEN_DIR / "stationary_imu.csv").read_bytes(),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    draft = ks.get_draft(an["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=an["workspaceId"],
        path="analysis.py",
        content=(GOLDEN_DIR / "analysis.py").read_bytes(),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"], timeout=90.0)
    assert run["status"] == "completed"
    assert run["runtimeIdentity"]["runtimeKind"] == "container"
    _ = fw_image  # firmware image documented; compile covered when image present


@pytest.mark.skipif(
    os.environ.get("RUN_GOLDEN_LLM", "0") != "1" or not os.environ.get("NEXUS_MODEL_API_KEY"),
    reason="Set RUN_GOLDEN_LLM=1 and NEXUS_MODEL_API_KEY for GOLDEN G3",
)
def test_golden_g3_live_llm_stub_runtimes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GOLDEN G3 — live model patches with stub/process toolchains; no fixture substitution."""
    from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
    from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
    from nexus_model_gateway import ModelPolicy, OpenAICompatibleGateway

    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "1")
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
    kernel, _ps, ks, project_id = build_test_kernel(
        approved_firmware_plan=True,
        auto_start_scheduler=True,
        firmware_patch_generator=LiveFirmwarePatchGenerator(gateway=gateway, model_policy=policy),
        analysis_patch_generator=LiveAnalysisPatchGenerator(gateway=gateway, model_policy=policy),
    )
    user = actor("user")

    fw = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=fw["artifactId"],
        workspace_id=fw["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(fw["baseArtifactVersion"]),
        base_project_state_version=int(fw["baseProjectStateVersion"]),
    )
    fw_proposal = kernel.workspace_runtime.propose_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change=(
            "Implement ESP32 MPU6050 vibration monitor firmware: I2C SDA=GPIO21 SCL=GPIO22, "
            "Serial 115200, readiness marker, TEL telemetry with time_s and accel_*_g."
        ),
    )["proposal"]
    assert fw_proposal["operations"], "Live firmware patch generator returned no operations"
    assert "llm" in str(fw_proposal.get("generatorId") or "").lower() or (
        (fw_proposal.get("generatorMetadata") or {}).get("mode") == "llm"
    )
    draft = ks.get_draft(fw["workspaceId"])
    kernel.workspace_runtime.apply_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        proposal_id=fw_proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(fw["baseArtifactVersion"]),
        base_project_state_version=int(fw["baseProjectStateVersion"]),
    )
    fw_src = kernel.filesystem.read_file(fw["workspaceId"], "src/main.cpp")["content"].decode(
        "utf-8"
    )
    assert "115200" in fw_src
    assert "21" in fw_src and "22" in fw_src

    an = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=an["artifactId"],
        workspace_id=an["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(an["workspaceId"])
    kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/stationary_imu.csv",
        content=(GOLDEN_DIR / "stationary_imu.csv").read_bytes(),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    an_proposal = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change=(
            "Read data/stationary_imu.csv, compute demeaned accel_x RMS noise, "
            "compare against 0.10 g, write outputs/summary.json with assessment, "
            "outputs/processed.csv, and outputs/accel_plot.png."
        ),
    )["proposal"]
    assert an_proposal["operations"], "Live analysis patch generator returned no operations"
    draft = ks.get_draft(an["workspaceId"])
    kernel.workspace_runtime.apply_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=an_proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    analysis_py = kernel.filesystem.read_file(an["workspaceId"], "analysis.py")["content"].decode(
        "utf-8"
    )
    assert "stationary_imu.csv" in analysis_py or "accel_x" in analysis_py
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"], timeout=90.0)
    assert run["status"] == "completed", run
    _write_report(
        tmp_path / "golden-live-analysis.json",
        {
            "schemaVersion": "1.0.0",
            "gate": "GOLDEN_G3",
            "projectId": project_id,
            "result": "PASS",
            "model": {
                "provider": provider,
                "model": policy.model if hasattr(policy, "model") else str(policy),
            },
            "note": "LLM-authored patches applied; stub analysis execution.",
        },
    )


@pytest.mark.skipif(
    os.environ.get("RUN_GOLDEN_FULL_LIVE", "0") != "1"
    or not os.environ.get("NEXUS_MODEL_API_KEY")
    or shutil.which(os.environ.get("NEXUS_EXEC_DOCKER", "docker")) is None,
    reason="Set RUN_GOLDEN_FULL_LIVE=1 with model key + Docker for GOLDEN G4",
)
def test_golden_g4_live_llm_analysis(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live LLM analysis in a container; firmware and simulator remain separate gates."""
    from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
    from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
    from nexus_model_gateway import ModelPolicy, OpenAICompatibleGateway

    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    fw_image = os.environ.get(
        "NEXUS_FIRMWARE_CONTAINER_IMAGE", "nexus-firmware-platformio-esp32:1.0.0"
    )
    an_image = os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "nexus-python-analysis:1.0.0")
    for _image in (fw_image, an_image):
        inspect = shutil.which(os.environ.get("NEXUS_EXEC_DOCKER", "docker"))
        assert inspect is not None
        # Image presence is validated by compile/run; missing images fail as GAP via runtime.

    provider = (os.environ.get("NEXUS_MODEL_PROVIDER") or "openai").strip().lower()
    gateway = OpenAICompatibleGateway(
        model_credential=os.environ["NEXUS_MODEL_API_KEY"],
        base_url=os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1"),
    )
    policy = ModelPolicy(
        provider=provider,
        model=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "120")),
    )
    runtime = build_execution_runtime("container", container_image=an_image)
    kernel, _ps, ks, project_id = build_test_kernel(
        auto_start_scheduler=True,
        execution_runtime=runtime,
        firmware_patch_generator=LiveFirmwarePatchGenerator(gateway=gateway, model_policy=policy),
        analysis_patch_generator=LiveAnalysisPatchGenerator(gateway=gateway, model_policy=policy),
    )
    user = actor("user")
    an = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=an["artifactId"],
        workspace_id=an["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    draft = ks.get_draft(an["workspaceId"])
    kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/stationary_imu.csv",
        content=(GOLDEN_DIR / "stationary_imu.csv").read_bytes(),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
        media_type="text/csv",
    )
    proposal = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change=(
            "Analyze stationary_imu.csv: demeaned accel_x RMS vs 0.10 g; write "
            "summary.json/processed.csv/accel_plot.png with deterministic assessment."
        ),
    )["proposal"]
    assert proposal["operations"]
    draft = ks.get_draft(an["workspaceId"])
    kernel.workspace_runtime.apply_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(an["baseArtifactVersion"]),
        base_project_state_version=int(an["baseProjectStateVersion"]),
    )
    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"], timeout=180.0)
    assert run["status"] == "completed", (
        "Live LLM analysis failed container execution — product/model defect, "
        f"not fixture substitution. run={run}"
    )
    assert run.get("runtimeIdentity", {}).get("runtimeKind") == "container"
    _write_report(
        tmp_path / "golden-live-analysis.json",
        {
            "schemaVersion": "1.0.0",
            "gate": "GOLDEN_G4",
            "projectId": project_id,
            "result": "PASS",
            "runtimeIdentity": run.get("runtimeIdentity"),
            "firmwareImage": fw_image,
            "analysisImage": an_image,
        },
    )


def test_firmware_telemetry_parses_in_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from golden.esp32_imu_vibration_monitor import analysis
    from golden.esp32_imu_vibration_monitor.consistency import TELEMETRY_FIELDS

    firmware = (GOLDEN_DIR / "main.cpp").read_text()
    header = re.search(r'Serial.println\("(time_s,[^" ]+)"\)', firmware)
    assert header is not None, "Firmware must emit the CSV header with explicit units"
    assert tuple(header[1].split(",")) == TELEMETRY_FIELDS == analysis.REQUIRED
    assert "Serial.print(now / 1000.0, 3)" in firmware
    dataset = tmp_path / "stationary_imu.csv"
    dataset.write_text(header[1] + "\n0.020,0.01,0,1\n0.040,-0.01,0,1\n")
    monkeypatch.setattr(analysis, "DATA", dataset)
    monkeypatch.setattr(analysis, "OUT", tmp_path / "outputs")
    analysis.main()
    with (tmp_path / "outputs/processed.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert [float(row["time_s"]) for row in rows] == [0.02, 0.04]


def _platformio_core_dir(tmp_path: Path) -> str:
    """PlatformIO core dir for the live build.

    ``PLATFORMIO_CORE_DIR`` wins when set (an empty value counts as unset,
    like ``${PLATFORMIO_CORE_DIR:-...}``). Otherwise the ESP32 platform and
    toolchain (about 1.5 GB) are cached once in a Nexus-owned directory under
    ``$XDG_CACHE_HOME`` (or ``~/.cache``) so later demo runs, including offline
    ones, reuse them; ``~/.platformio`` is never touched. If that cache cannot
    be created or written, fall back to a throwaway directory under the demo's
    temporary artifacts.
    """
    override = os.environ.get("PLATFORMIO_CORE_DIR")
    if override:
        return override
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    try:
        base = Path(xdg) if os.path.isabs(xdg) else Path.home() / ".cache"
        cache = base / "nexus" / "platformio-core"
        cache.mkdir(parents=True, exist_ok=True)
        if os.access(cache, os.W_OK | os.X_OK):
            return str(cache)
    except (OSError, RuntimeError):
        pass
    return str(tmp_path / "platformio-core")


@pytest.mark.skipif(
    os.environ.get("NEXUS_DEMO_LIVE_COMPILE") != "1",
    reason="Live compile runs through make demo-golden, outside offline tests",
)
def test_golden_local_platformio(tmp_path: Path) -> None:
    """Attempt an actual local build whenever the CLI exists; absence is a gap."""
    cli = shutil.which("platformio") or shutil.which("pio")
    if cli is None:
        print("LIVE PlatformIO: GAP — CLI absent; no live compile pass")
        pytest.skip("LIVE PlatformIO GAP: CLI absent")
    (tmp_path / "src").mkdir()
    shutil.copyfile(GOLDEN_DIR / "main.cpp", tmp_path / "src/main.cpp")
    shutil.copyfile(GOLDEN_DIR / "platformio.ini", tmp_path / "platformio.ini")
    core_dir = _platformio_core_dir(tmp_path)
    print(f"LIVE PlatformIO: core dir {core_dir}")
    try:
        result = subprocess.run(
            [cli, "run", "--project-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env={**os.environ, "PLATFORMIO_CORE_DIR": core_dir},
        )
    except subprocess.TimeoutExpired:
        pytest.fail("LIVE PlatformIO: FAILED — build timed out after 300 seconds")
    (tmp_path / "platformio.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("firmware.elf", "firmware.bin"):
        assert (tmp_path / ".pio/build/nexus" / name).stat().st_size > 0
    print("LIVE PlatformIO: PASS — real CLI build and ELF/BIN checked")


@pytest.mark.parametrize("core_dir", [None, "", "/tmp/nexus-platformio-override"])
@pytest.mark.parametrize("returncode", [0, 1])
def test_platformio_harness_core_dir_and_build_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, core_dir: str | None, returncode: int
) -> None:
    if core_dir is None:
        monkeypatch.delenv("PLATFORMIO_CORE_DIR", raising=False)
    else:
        monkeypatch.setenv("PLATFORMIO_CORE_DIR", core_dir)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(shutil, "which", lambda _: "/fake/pio")

    def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        expected = core_dir or str(tmp_path / "xdg/nexus/platformio-core")
        assert kwargs["env"]["PLATFORMIO_CORE_DIR"] == expected
        if not core_dir:
            assert Path(expected).is_dir()
            (Path(expected) / "writable").write_text("ok")
        build = tmp_path / ".pio/build/nexus"
        build.mkdir(parents=True)
        for name in ("firmware.elf", "firmware.bin"):
            (build / name).write_bytes(b"build output")
        return subprocess.CompletedProcess(args[0], returncode, "compile output", "")

    monkeypatch.setattr(subprocess, "run", run)
    if returncode:
        with pytest.raises(AssertionError, match="compile output"):
            test_golden_local_platformio(tmp_path)
    else:
        test_golden_local_platformio(tmp_path)


def test_platformio_core_dir_reuses_nexus_cache_across_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PLATFORMIO_CORE_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    first = _platformio_core_dir(tmp_path / "run1")
    second = _platformio_core_dir(tmp_path / "run2")
    assert first == second == str(tmp_path / "xdg/nexus/platformio-core")
    assert Path(first).is_dir()


def test_platformio_core_dir_relative_xdg_uses_home_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PLATFORMIO_CORE_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/cache")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    core_dir = _platformio_core_dir(tmp_path)
    assert core_dir == str(tmp_path / "home/.cache/nexus/platformio-core")
    assert Path(core_dir).is_dir()


@pytest.mark.parametrize("blocker", ["file", "read-only"])
def test_platformio_core_dir_falls_back_to_temp_when_cache_unusable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blocker: str
) -> None:
    monkeypatch.delenv("PLATFORMIO_CORE_DIR", raising=False)
    xdg = tmp_path / "xdg"
    if blocker == "file":
        xdg.write_text("not a directory")
    else:
        (xdg / "nexus/platformio-core").mkdir(parents=True)
        monkeypatch.setattr(os, "access", lambda *_args, **_kwargs: False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg))
    assert _platformio_core_dir(tmp_path) == str(tmp_path / "platformio-core")


def test_platformio_harness_missing_cli_is_gap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(pytest.skip.Exception, match="GAP: CLI absent"):
        test_golden_local_platformio(tmp_path)
    assert "GAP — CLI absent; no live compile pass" in capsys.readouterr().out


def test_w4_firmware_simulation_import_analysis_regression(monkeypatch, tmp_path):
    """Fake compiler and Wokwi runner; real output import and Python analysis."""
    _run_golden_g1(monkeypatch, tmp_path, False, simulation_handoff=True)


@pytest.mark.skipif(
    os.environ.get("RUN_WOKWI_INTEGRATION") != "1", reason="Opt-in live W4 toolchain gate"
)
def test_w4_live_built_firmware_simulation_import_analysis(monkeypatch, tmp_path):
    if (
        not shutil.which("pio")
        or not shutil.which("wokwi-cli")
        or not os.environ.get("WOKWI_CLI_TOKEN")
    ):
        pytest.skip("Live W4 needs PlatformIO, Wokwi CLI and token")
    _run_golden_g1(monkeypatch, tmp_path, False, simulation_handoff="live")


@pytest.mark.parametrize(
    "telemetry", [b"", b"NEXUS_MPU_INIT_FAIL\n", b"TEL,0,nan,0,1\n", b"TEL,0,invalid,0,1\n"]
)
def test_w4_analysis_rejects_missing_or_invalid_telemetry(tmp_path, telemetry):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/serial.log").write_bytes(telemetry)
    python = shutil.which("python3")
    assert python is not None
    result = subprocess.run(
        [python, str(GOLDEN_DIR / "analysis.py")],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert not (tmp_path / "outputs/summary.json").exists()
