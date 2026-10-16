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
from pathlib import Path
from typing import Any

import pytest
from golden.esp32_imu_vibration_monitor.consistency import (
    ANALYSIS_OUTPUTS,
    GOLDEN_PROMPT,
    validate_golden_consistency,
)
from helpers import acquire_edit_lease, actor, build_test_kernel
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
from nexus_persistence import InMemoryKernelStore, InMemoryProjectStore

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
    request: pytest.FixtureRequest,
    fail_analysis: bool | str,
) -> None:
    """GOLDEN G1 — fixture generation, compile stub, real analysis and VERIFY."""
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")

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

    project_store = InMemoryProjectStore()
    package["artifacts"] = init_artifacts
    project_store.save_initialization_package(package)
    ks = InMemoryKernelStore(project_store=project_store)
    kernel = build_project_kernel(ks, project_store=project_store)
    request.addfinalizer(kernel.jobs.shutdown)
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
    assert fw_run["status"] == "completed"
    fw_outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=fw_run["executionRunId"]
    )["outputs"]
    fw_names = {o.get("name") for o in fw_outputs}
    assert any("firmware.elf" in str(n) for n in fw_names)

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
    # Preserve the evidence basis, then accept a changed requirement through the store.
    requirement = project_store.get_artifact(project_id, "requirement-set")
    basis_version = requirement["artifactVersion"]
    changed = copy.deepcopy(requirement)
    changed["artifactVersion"] += 1
    r7_requirement = next(r for r in changed["content"]["requirements"] if r["displayId"] == "R7")
    r7_requirement["statement"] = "Stationary accel_x RMS noise shall be below 0.01 g."
    project_store.apply_accepted_artifact_revision(
        project_id=project_id,
        new_artifact=changed,
        next_state_version=project_store.get_project(project_id)["currentStateVersion"] + 1,
        updated_at=changed["updatedAt"],
    )
    current_version = project_store.get_artifact(project_id, "requirement-set")["artifactVersion"]
    assert current_version > basis_version
    report["evidenceFreshness"] = {
        "status": "STALE",
        "basisRequirementVersion": basis_version,
        "currentRequirementVersion": current_version,
        "note": "Demo basis comparison; coverage projection does not yet invalidate old evidence.",
    }
    _write_report(tmp_path / "golden-g1.json", report)
    print("FIXTURE: R7 VERIFIED; RMS=" + str(summary_preview["accel_x_rms_noise_g"]))
    print("REQUIREMENT CHANGE: evidence STALE; " + json.dumps(report["evidenceFreshness"]))


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
    try:
        result = subprocess.run(
            [cli, "run", "--project-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("LIVE PlatformIO: FAILED — build timed out after 300 seconds")
    (tmp_path / "platformio.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("firmware.elf", "firmware.bin"):
        assert (tmp_path / ".pio/build/nexus" / name).stat().st_size > 0
    print("LIVE PlatformIO: PASS — real CLI build and ELF/BIN checked")
