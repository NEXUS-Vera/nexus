"""Phase 17F G1 — hermetic VERIFY product-path E2E and negative paths N1–N9."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from helpers import actor, content_for
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.kernel import build_project_kernel
from nexus_board.services.verification_service import VerificationError
from nexus_board.verification.close import (
    annotate_risk_mitigation_verification,
    promote_analysis_evidence_into_test_plan,
    promote_marker_evidence_into_test_plan,
    promote_structural_evidence_into_test_plan,
    stable_evidence_id,
)
from nexus_board.verification.coverage import compute_requirement_coverage
from nexus_board.verification.fixture_risk_register import (
    build_golden_vibration_risk_register_content,
)
from nexus_board.verification.fixture_test_plan import build_golden_vibration_test_plan_content
from nexus_persistence import InMemoryKernelStore, InMemoryProjectStore

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "examples"
    / "valid"
    / "esp32-imu-vibration-monitor"
)


def _load_req_content() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (FIXTURE_DIR / "requirement-set-artifact.json").read_text(encoding="utf-8")
    )
    content = payload.get("content")
    if not isinstance(content, dict):
        raise AssertionError("requirement-set fixture missing content")
    return content


def _verify_package() -> dict[str, Any]:
    project_id = new_id("proj")
    turn_id = new_id("turn")
    route_id = new_id("route")
    run_id = new_id("run")
    now = utc_now_iso()
    user = actor()
    req_content = _load_req_content()
    tp = build_golden_vibration_test_plan_content(
        requirements=req_content["requirements"],
        apply_r7_pass=False,
        apply_structural_pass=False,
    )
    rr = build_golden_vibration_risk_register_content()

    arts: list[dict[str, Any]] = []
    for atype, content in [
        ("project-brief", content_for("project-brief")),
        ("requirement-set", req_content),
        ("functional-architecture", content_for("functional-architecture")),
        ("next-action", content_for("next-action")),
        ("test-plan", tp),
        ("risk-register", rr),
    ]:
        arts.append(
            {
                "schemaVersion": "1.0.0",
                "artifactId": new_id("art"),
                "projectId": project_id,
                "artifactType": atype,
                "artifactVersion": 1,
                "contentSchemaVersion": "1.0.0",
                "lifecycleStatus": "ready",
                "evidenceStatus": "unverified",
                "approvalStatus": "proposed",
                "createdBy": user,
                "createdAt": now,
                "updatedAt": now,
                "sourceTurnId": turn_id,
                "workflowRunId": run_id,
                "content": content,
            }
        )

    return {
        "schemaVersion": "1.0.0",
        "project": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "title": "VERIFY G1 Project",
            "domain": "embedded-products",
            "projectPhase": "concept",
            "currentStateVersion": 1,
            "autonomyMode": "collaborate",
            "currentArtifactReferences": [
                {
                    "artifactType": a["artifactType"],
                    "artifactId": a["artifactId"],
                    "artifactVersion": 1,
                    "contentSchemaVersion": "1.0.0",
                }
                for a in arts
            ],
            "openQuestionReferences": [],
            "blockerOrValidationIssueReferences": [],
            "createdAt": now,
            "updatedAt": now,
        },
        "userTurn": {
            "schemaVersion": "1.0.0",
            "turnId": turn_id,
            "projectId": project_id,
            "rawUserMessage": "Initialize VERIFY G1",
            "actor": user,
            "timestamp": now,
        },
        "turnRoute": {
            "schemaVersion": "1.0.0",
            "routeId": route_id,
            "turnId": turn_id,
            "supported": True,
            "routeType": "project-initialization",
            "domain": "embedded-products",
            "projectOperation": "create-project",
            "complexity": "medium",
            "autonomyMode": "collaborate",
            "chairmanRequiredEventually": False,
            "reasons": ["test"],
        },
        "workflowRun": {
            "schemaVersion": "1.0.0",
            "workflowRunId": run_id,
            "workflowType": "embedded-project-initialization",
            "projectId": project_id,
            "turnId": turn_id,
            "runStatus": "completed",
            "stepRecords": [
                {
                    "stepId": "s1",
                    "stepType": "complete-workflow",
                    "status": "completed",
                    "attempt": 1,
                }
            ],
            "startTime": now,
            "endTime": now,
            "warnings": [],
            "errorReferences": [],
        },
        "artifacts": arts,
        "validationIssues": [],
        "openQuestions": [],
        "veraResponse": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "turnId": turn_id,
            "userFacingMessage": "ok",
            "createdAt": now,
            "artifactReferences": [
                {
                    "artifactType": a["artifactType"],
                    "artifactId": a["artifactId"],
                    "artifactVersion": 1,
                    "contentSchemaVersion": "1.0.0",
                }
                for a in arts
            ],
            "openQuestionReferences": [],
            "validationIssueReferences": [],
            "nextActionReferences": [],
        },
    }


def _seed() -> tuple[Any, InMemoryProjectStore, str, dict[str, Any]]:
    project_store = InMemoryProjectStore()
    kernel_store = InMemoryKernelStore(project_store=project_store)
    package = _verify_package()
    project_store.save_initialization_package(copy.deepcopy(package))
    project_id = package["project"]["projectId"]
    kernel = build_project_kernel(kernel_store, project_store=project_store)
    return kernel, project_store, project_id, actor("user")


def _seed_summary_run(kernel: Any, project_id: str, run_id: str, status: str = "completed") -> None:
    provenance = {}
    if project_id != "proj_FOREIGN":
        provenance = _seed_run_inputs(kernel, project_id)
    kernel.kernel_store.create_execution_run(
        {
            "schemaVersion": "1.0.0",
            "executionRunId": run_id,
            "projectId": project_id,
            **provenance,
            "artifactType": "analysis",
            "status": "completed" if status == "truncated" else status,
            "createdAt": utc_now_iso(),
            "outputReferences": [],
            "runtimeKind": "process",
            "executionJobId": "execjob_SUMMARY",
        }
    )
    kernel.kernel_store.create_execution_job(
        {
            "executionJobId": "execjob_SUMMARY",
            "executionRunId": run_id,
            "projectId": project_id,
            "status": "succeeded",
            "logTruncated": status == "truncated",
        }
    )

    if provenance:
        kernel.invalidation.record_run(kernel.kernel_store.get_execution_run(run_id))


def _seed_run_inputs(kernel: Any, project_id: str) -> dict[str, Any]:
    user = actor()
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    kernel.workspaces.acquire_edit_lease(workspace_id=binding["workspaceId"], actor=user)
    snapshot = kernel.workspaces.create_snapshot(
        workspace_id=binding["workspaceId"], reason="Verification fixture", actor=user
    )
    return {
        "workspaceId": binding["workspaceId"],
        "artifactId": binding["artifactId"],
        "baseArtifactVersion": binding["baseArtifactVersion"],
        "inputSnapshotId": snapshot["snapshotId"],
    }


@pytest.mark.parametrize(
    "case,message",
    [
        ("missing", "execution_run_id is required"),
        ("empty", "execution_run_id is required"),
        ("foreign", "does not belong to this project"),
        ("failed", "Only completed ExecutionRuns"),
        ("timed-out", "Only completed ExecutionRuns"),
        ("cancelled", "Only completed ExecutionRuns"),
        ("running", "Only completed ExecutionRuns"),
        ("queued", "Only completed ExecutionRuns"),
        ("truncated", "logs were truncated"),
    ],
)
def test_analysis_summary_rejects_invalid_run(case: str, message: str) -> None:
    kernel, projects, project_id, user = _seed()
    run_id = "exec_SUMMARY_GATE"
    _seed_summary_run(
        kernel,
        "proj_FOREIGN" if case == "foreign" else project_id,
        run_id,
        "completed" if case in {"missing", "empty", "foreign"} else case,
    )
    before = copy.deepcopy(projects.get_artifact(project_id, "test-plan"))
    kwargs = {} if case == "missing" else {"execution_run_id": "" if case == "empty" else run_id}
    with pytest.raises(VerificationError, match=message):
        kernel.verification.promote_analysis_summary(
            project_id=project_id,
            summary={"accel_x_rms_noise_g": 0.0157},
            produced_output_names=["outputs/summary.json"],
            actor=user,
            **kwargs,
        )
    assert projects.get_artifact(project_id, "test-plan") == before


@pytest.mark.parametrize("run_status", ["completed", "completed-with-warnings"])
def test_g1_analysis_promotion_closes_r7_and_r8(run_status: str) -> None:
    kernel, project_store, project_id, user = _seed()
    _seed_summary_run(kernel, project_id, "exec_GOLDEN_ANALYSIS_R7_PROMOTION01", run_status)
    before = project_store.get_artifact(project_id, "test-plan")
    t7 = next(c for c in before["content"]["testCases"] if c["displayId"] == "T7")
    assert t7["status"] == "ready"

    result = kernel.verification.promote_analysis_summary(
        project_id=project_id,
        summary={"accel_x_rms_noise_g": 0.015676464092948383, "assessment": "PASS"},
        produced_output_names=[
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
        actor=user,
        execution_run_id="exec_GOLDEN_ANALYSIS_R7_PROMOTION01",
        accept=True,
    )
    assert result["changed"] is True
    assert result.get("accepted") is True

    after = project_store.get_artifact(project_id, "test-plan")
    assert after["artifactVersion"] >= before["artifactVersion"] + 1
    t7b = next(c for c in after["content"]["testCases"] if c["displayId"] == "T7")
    t8b = next(c for c in after["content"]["testCases"] if c["displayId"] == "T8")
    assert t7b["assessment"] == "PASS"
    assert t7b["assessmentAuthority"] == "deterministic-code"
    assert t7b["evidenceReferences"]
    assert t8b["assessment"] == "PASS"
    rows = compute_requirement_coverage(
        requirements=_load_req_content()["requirements"],
        test_cases=after["content"]["testCases"],
    )
    assert next(r for r in rows if r["displayId"] == "R7")["verificationState"] == "VERIFIED"
    assert next(r for r in rows if r["displayId"] == "R8")["verificationState"] == "VERIFIED"

    again = kernel.verification.promote_analysis_summary(
        project_id=project_id,
        summary={"accel_x_rms_noise_g": 0.015676464092948383, "assessment": "PASS"},
        produced_output_names=[
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
        actor=user,
        execution_run_id="exec_GOLDEN_ANALYSIS_R7_PROMOTION01",
        accept=True,
    )
    assert again["changed"] is False
    assert again["idempotent"] is True
    assert (
        project_store.get_artifact(project_id, "test-plan")["artifactVersion"]
        == after["artifactVersion"]
    )


def test_g1_structural_promotion_closes_t2() -> None:
    kernel, project_store, project_id, user = _seed()
    result = kernel.verification.promote_structural_mapping(
        project_id=project_id,
        signal_map={"SDA": "GPIO21", "SCL": "GPIO22"},
        actor=user,
        source_id="structural_wokwi_translation_01",
        accept=True,
    )
    assert result["changed"] is True
    tp = project_store.get_artifact(project_id, "test-plan")
    t2 = next(c for c in tp["content"]["testCases"] if c["displayId"] == "T2")
    assert t2["assessment"] == "PASS"


def test_n1_numeric_failure() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    updated, _ = promote_analysis_evidence_into_test_plan(
        content,
        summary={"accel_x_rms_noise_g": 0.12},
        produced_output_names=["outputs/summary.json"],
        execution_run_id="exec_N1",
        requirements=_load_req_content()["requirements"],
    )
    t7 = next(c for c in updated["testCases"] if c["displayId"] == "T7")
    assert t7["assessment"] == "FAIL"
    rows = compute_requirement_coverage(
        requirements=_load_req_content()["requirements"], test_cases=updated["testCases"]
    )
    assert next(r for r in rows if r["displayId"] == "R7")["verificationState"] == "FAILED"


def test_n2_missing_metric_inconclusive() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    updated, _ = promote_analysis_evidence_into_test_plan(
        content,
        summary={"status": "ok"},
        produced_output_names=["outputs/summary.json"],
        execution_run_id="exec_N2",
        requirements=_load_req_content()["requirements"],
    )
    t7 = next(c for c in updated["testCases"] if c["displayId"] == "T7")
    assert t7["assessment"] == "INCONCLUSIVE"
    rows = compute_requirement_coverage(
        requirements=_load_req_content()["requirements"], test_cases=updated["testCases"]
    )
    assert next(r for r in rows if r["displayId"] == "R7")["verificationState"] != "VERIFIED"


def test_n3_missing_output_fails_existence() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    updated, _ = promote_analysis_evidence_into_test_plan(
        content,
        summary={"accel_x_rms_noise_g": 0.01},
        produced_output_names=["outputs/summary.json"],
        execution_run_id="exec_N3",
        requirements=_load_req_content()["requirements"],
    )
    t8 = next(c for c in updated["testCases"] if c["displayId"] == "T8")
    assert t8["assessment"] == "FAIL"


def test_n4_marker_absent_after_run_fails() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    updated, _ = promote_marker_evidence_into_test_plan(
        content,
        log_text="boot ok, no sensor ready marker",
        execution_run_id="exec_N4",
        requirements=_load_req_content()["requirements"],
        run_occurred=True,
    )
    t4 = next(c for c in updated["testCases"] if c["displayId"] == "T4")
    assert t4["assessment"] == "FAIL"


def test_n4b_no_run_blocks_marker_test() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    updated, _ = promote_marker_evidence_into_test_plan(
        content,
        log_text=None,
        execution_run_id="exec_N4B",
        requirements=_load_req_content()["requirements"],
        run_occurred=False,
    )
    t4 = next(c for c in updated["testCases"] if c["displayId"] == "T4")
    assert t4["status"] == "blocked"


def test_n5_structural_mismatch_fails() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    updated, _ = promote_structural_evidence_into_test_plan(
        content,
        signal_map={"SDA": "GPIO18", "SCL": "GPIO22"},
        source_id="structural_N5",
        requirements=_load_req_content()["requirements"],
    )
    t2 = next(c for c in updated["testCases"] if c["displayId"] == "T2")
    assert t2["assessment"] == "FAIL"


def test_n6_uncovered_requirement_visible() -> None:
    reqs = list(_load_req_content()["requirements"]) + [
        {
            "requirementId": "req_UNCOVEREDREQ00000001",
            "displayId": "R9",
            "statement": "Informational requirement with no test.",
            "priority": "should",
            "status": "accepted",
            "verificationMethod": "inspection",
        }
    ]
    content = build_golden_vibration_test_plan_content(requirements=reqs, apply_r7_pass=False)
    rows = compute_requirement_coverage(requirements=reqs, test_cases=content["testCases"])
    assert next(r for r in rows if r["displayId"] == "R9")["verificationState"] == "UNCOVERED"
    assert content["coverageSummary"]["uncoveredRequirements"] == 1


def test_n7_invalid_evidence_reuse_rejected() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    with pytest.raises(ValueError, match="EVIDENCE_PROJECT_MISMATCH"):
        promote_analysis_evidence_into_test_plan(
            content,
            summary={"accel_x_rms_noise_g": 0.01},
            produced_output_names=["outputs/summary.json"],
            execution_run_id="exec_N7",
            project_id="proj_OTHERPROJECT00001",
            expected_project_id="proj_EXPECTEDPROJECT01",
        )


def test_n8_duplicate_evidence_idempotent() -> None:
    content = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    first, changed1 = promote_analysis_evidence_into_test_plan(
        content,
        summary={"accel_x_rms_noise_g": 0.0157},
        produced_output_names=[
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
        execution_run_id="exec_N8",
        requirements=_load_req_content()["requirements"],
    )
    second, changed2 = promote_analysis_evidence_into_test_plan(
        first,
        summary={"accel_x_rms_noise_g": 0.0157},
        produced_output_names=[
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
        execution_run_id="exec_N8",
        requirements=_load_req_content()["requirements"],
    )
    assert changed1 is True
    assert changed2 is False
    t7 = next(c for c in second["testCases"] if c["displayId"] == "T7")
    eids = [r["evidenceId"] for r in t7["evidenceReferences"]]
    assert len(eids) == len(set(eids))
    expected = stable_evidence_id(
        source_id="exec_N8",
        test_id=t7["testId"],
        key="metric:accel_x_rms_noise_g",
    )
    assert expected in eids


def test_n9_k6_remains_monitoring() -> None:
    rr = build_golden_vibration_risk_register_content()
    content = build_golden_vibration_test_plan_content(apply_r7_pass=True)
    annotated = annotate_risk_mitigation_verification(rr, test_cases=content["testCases"])
    k6 = next(r for r in annotated["risks"] if r["displayId"] == "K6")
    assert k6["status"] == "monitoring"
    assert not k6.get("verificationTestIds")


def test_evidence_chain_exposes_r7_links() -> None:
    kernel, _ps, project_id, user = _seed()
    _seed_summary_run(kernel, project_id, "exec_CHAIN_R7")
    kernel.verification.promote_analysis_summary(
        project_id=project_id,
        summary={"accel_x_rms_noise_g": 0.0157},
        produced_output_names=[
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
        actor=user,
        execution_run_id="exec_CHAIN_R7",
        accept=True,
    )
    chain = kernel.verification.evidence_chain(project_id)
    r7 = [c for c in chain if c["requirementId"] == "R7"]
    assert r7
    assert r7[0]["assessment"] == "PASS"
    assert r7[0]["assessmentAuthority"] == "deterministic-code"
    assert r7[0]["evidenceReferences"]


@pytest.mark.parametrize(
    "run_status",
    ["completed", "completed-with-warnings", "failed", "timed-out", "cancelled", "truncated"],
)
def test_g1_product_path_execution_run_promotion(run_status: str) -> None:
    """Analysis ExecutionRun + ProducedOutput → VerificationService (not helper-only)."""

    kernel, project_store, project_id, user = _seed()
    run_id = "exec_PRODUCT_PATH_ANALYSIS_R7"
    now = utc_now_iso()
    summary = {
        "accel_x_rms_noise_g": 0.015676464092948383,
        "assessment": "PASS",
    }
    outputs = [
        ("out_PRODUCT_SUMMARY_R7", "outputs/summary.json", json.dumps(summary)),
        ("out_PRODUCT_CSV_R8", "outputs/processed.csv", "t,x\n0,0.01\n"),
        ("out_PRODUCT_PNG_R8", "outputs/accel_plot.png", "png"),
    ]
    ks = kernel.kernel_store
    for oid, name, text in outputs:
        ks.create_produced_output(
            {
                "schemaVersion": "1.0.0",
                "outputId": oid,
                "projectId": project_id,
                "executionRunId": run_id,
                "name": name,
                "outputType": "json" if name.endswith(".json") else "file",
                "content": {
                    "kind": "inline-structured",
                    "structuredResult": {"text": text},
                },
                "createdAt": now,
            }
        )
    provenance = _seed_run_inputs(kernel, project_id)
    ks.create_execution_run(
        {
            "schemaVersion": "1.0.0",
            "executionRunId": run_id,
            "projectId": project_id,
            **provenance,
            "artifactType": "analysis",
            "status": "completed" if run_status == "truncated" else run_status,
            **({"executionJobId": "execjob_TRUNCATED"} if run_status == "truncated" else {}),
            "createdAt": now,
            "startedAt": now,
            "completedAt": now,
            "outputReferences": [oid for oid, _, _ in outputs],
            "runtimeKind": "process",
        }
    )

    kernel.invalidation.record_run(ks.get_execution_run(run_id))

    if run_status == "truncated":
        ks.create_execution_job(
            {
                "executionJobId": "execjob_TRUNCATED",
                "executionRunId": run_id,
                "projectId": project_id,
                "status": "succeeded",
                "logTruncated": True,
            }
        )

    if run_status not in {"completed", "completed-with-warnings"}:
        before = project_store.get_artifact(project_id, "test-plan")
        with pytest.raises(VerificationError, match="truncated|completed"):
            kernel.verification.promote_execution_evidence(
                project_id=project_id,
                execution_run_id=run_id,
                actor=user,
                accept=True,
            )
        assert project_store.get_artifact(project_id, "test-plan") == before
        return

    result = kernel.verification.promote_execution_evidence(
        project_id=project_id,
        execution_run_id=run_id,
        actor=user,
        accept=True,
    )
    assert result["changed"] is True
    tp = project_store.get_artifact(project_id, "test-plan")
    t7 = next(c for c in tp["content"]["testCases"] if c["displayId"] == "T7")
    t8 = next(c for c in tp["content"]["testCases"] if c["displayId"] == "T8")
    assert t7["assessment"] == "PASS"
    assert t7["evidenceReferences"]
    assert t8["assessment"] == "PASS"


def test_g1_marker_log_product_path() -> None:
    kernel, project_store, project_id, user = _seed()
    result = kernel.verification.promote_marker_log(
        project_id=project_id,
        log_text="boot\nNEXUS_MPU_READY\naccel_x_g=0.01\n",
        actor=user,
        execution_run_id="exec_MARKER_FW_01",
        run_occurred=True,
        accept=True,
    )
    assert result["changed"] is True
    tp = project_store.get_artifact(project_id, "test-plan")
    t4 = next(c for c in tp["content"]["testCases"] if c["displayId"] == "T4")
    assert t4["assessment"] == "PASS"


@pytest.mark.skipif(
    __import__("os").environ.get("RUN_PHASE17_LLM", "0") != "1"
    or not __import__("os").environ.get("NEXUS_MODEL_API_KEY"),
    reason="Set RUN_PHASE17_LLM=1 and NEXUS_MODEL_API_KEY for Phase 17F G2",
)
@pytest.mark.asyncio
async def test_g2_live_llm_test_and_risk_generation() -> None:
    import os

    from nexus_board.verification.live_generate import (
        generate_live_risk_register_content,
        generate_live_test_plan_content,
    )
    from nexus_model_gateway import ModelPolicy, OpenAICompatibleGateway
    from nexus_model_gateway.types import ModelGatewayError

    provider = (os.environ.get("NEXUS_MODEL_PROVIDER") or "openai").strip().lower()
    if provider == "anthropic":
        from nexus_model_gateway import AnthropicGateway

        gateway: Any = AnthropicGateway(model_credential=os.environ["NEXUS_MODEL_API_KEY"])
    else:
        gateway = OpenAICompatibleGateway(
            model_credential=os.environ["NEXUS_MODEL_API_KEY"],
            base_url=os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1"),
        )
    policy = ModelPolicy(
        provider=provider,
        model=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "90")),
    )
    reqs = _load_req_content()["requirements"]
    known = {str(r.get("displayId")) for r in reqs}
    try:
        tp = await generate_live_test_plan_content(
            gateway=gateway,
            model_policy=policy,
            system_instructions=(
                "Return a structured Test Plan draft only. Do not mark tests PASS/FAIL. "
                "Cover R1–R8 with allowed verification methods and typed criteria."
            ),
            context={
                "requirements": reqs,
                "allowedMethods": [
                    "analysis",
                    "execution-output",
                    "simulation",
                    "inspection",
                    "firmware-test",
                ],
            },
            requirements=reqs,
            known_requirement_ids=known,
            allow_fallback=False,
        )
    except ModelGatewayError as exc:
        pytest.skip(f"GAP — ENVIRONMENT/HARNESS: live model unavailable ({exc})")
    assert (tp.get("provenance") or {}).get("generatedBy") == "llm"
    assert len(tp.get("testCases") or []) >= 4
    for case in tp["testCases"]:
        assert case.get("assessment") in (None, "PENDING", "")
        assert case.get("status") in {"planned", "ready", None} or case.get("status") == "ready"

    try:
        rr = await generate_live_risk_register_content(
            gateway=gateway,
            model_policy=policy,
            system_instructions=(
                "Return a structured Risk Register draft. Do not mark risks mitigated by prose."
            ),
            context={"requirements": reqs, "testPlan": tp},
            requirements=reqs,
            test_cases=list(tp.get("testCases") or []),
            known_requirement_ids=known,
            known_test_ids={str(c.get("displayId")) for c in tp.get("testCases") or []},
            allow_fallback=False,
        )
    except ModelGatewayError as exc:
        pytest.skip(f"GAP — ENVIRONMENT/HARNESS: live model unavailable ({exc})")
    assert (rr.get("provenance") or {}).get("generatedBy") == "llm"
    assert len(rr.get("risks") or []) >= 1


@pytest.mark.skipif(
    __import__("os").environ.get("RUN_PHASE17_DOCKER", "0") != "1",
    reason="Set RUN_PHASE17_DOCKER=1 with PlatformIO/Analysis images for Phase 17F G3",
)
def test_g3_live_toolchain_evidence_gate() -> None:
    pytest.skip(
        "GAP — ENVIRONMENT/HARNESS: opt-in live toolchain evidence wired via Phase 15/16 G3"
    )


@pytest.mark.skipif(
    __import__("os").environ.get("RUN_PHASE17_FULL_LIVE", "0") != "1",
    reason="Set RUN_PHASE17_FULL_LIVE=1 for Phase 17F G4",
)
def test_g4_full_live_golden_gate() -> None:
    pytest.skip("GAP — ENVIRONMENT/HARNESS: full live golden VERIFY is opt-in")
