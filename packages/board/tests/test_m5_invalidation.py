"""M5 real-path verification invalidation, using golden G1 on durable SQLite."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from helpers import actor, cmd
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.ids import new_id
from nexus_board.kernel import build_project_kernel
from nexus_board.services.verification_service import VerificationError
from nexus_contracts.validation.schema_validator import validate_against_schema_id
from nexus_persistence.factory import build_stores
from test_phase16i_golden_e2e import _run_golden_g1, _wait_run


@pytest.fixture
def golden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    url = f"sqlite:///{tmp_path / 'm5.sqlite3'}"
    state = _run_golden_g1(monkeypatch, tmp_path, False, sqlite_url=url)
    assert state is not None
    projects, store = build_stores("sqlite", url)
    kernel = build_project_kernel(store, project_store=projects)
    yield kernel, state["projectId"], state["run"], url
    kernel.jobs.shutdown()


def _plan(kernel: Any, pid: str) -> dict[str, Any]:
    return kernel.project_store.get_artifact(pid, "test-plan")


def _case(kernel: Any, pid: str, display: str = "T7") -> dict[str, Any]:
    return next(c for c in _plan(kernel, pid)["content"]["testCases"] if c["displayId"] == display)


def _state(kernel: Any, pid: str, display: str = "R7") -> str:
    return next(
        r["verificationState"]
        for r in kernel.verification.requirement_verification_projection(pid)
        if r["displayId"] == display
    )


def _user(kernel: Any, pid: str, kind: str = "test-plan") -> dict[str, Any]:
    workspace = kernel.kernel_store.get_workspace_by_project_artifact(pid, kind)
    lease = kernel.kernel_store.get_draft(workspace["workspaceId"]).get("editLease") or {}
    return {"actorType": "user", "actorId": lease.get("ownerActorId") or new_id("actor")}


def _events(kernel: Any, pid: str) -> list[dict[str, Any]]:
    return [
        e
        for e in kernel.ledger.list_events(pid, limit=10000)[0]
        if e["eventType"] in {"verification.invalidated", "verification.revalidated"}
    ]


def _accept(kernel: Any, pid: str, kind: str, content: dict[str, Any]) -> tuple[Any, Any]:
    try:
        before = kernel.project_store.get_artifact(pid, kind)
    except Exception:
        workspace = kernel.kernel_store.get_workspace_by_project_artifact(pid, kind)
        before = {"artifactType": kind, "artifactId": workspace["artifactId"], "artifactVersion": 0}
    workspace = kernel.kernel_store.get_workspace_by_project_artifact(pid, kind)
    user = actor()
    if workspace is None:
        workspace = kernel.workspaces.create_workspace(
            project_id=pid, artifact_type=kind, actor=user
        )["workspace"]
    draft = kernel.kernel_store.get_draft(workspace["workspaceId"])
    lease = draft.get("editLease")
    if lease:
        user = {"actorId": lease["ownerActorId"], "actorType": lease["ownerActorType"]}
    kernel.workspaces.acquire_edit_lease(workspace_id=workspace["workspaceId"], actor=user)

    def dispatch(kind: str, data: dict[str, Any]) -> Any:
        current = kernel.kernel_store.get_workspace(workspace["workspaceId"])
        result = kernel.dispatch(
            cmd(
                command_type=kind,
                project_id=pid,
                artifact_id=current["artifactId"],
                workspace_id=current["workspaceId"],
                base_artifact_version=current["baseArtifactVersion"],
                base_project_state_version=kernel.project_store.get_project(pid)[
                    "currentStateVersion"
                ],
                input_data=data,
                requested_by=user,
            )
        )
        assert result["status"] == "completed", result
        return result

    dispatch(
        "workspace.update-draft",
        {"content": content, "expectedDraftVersion": draft["draftVersion"]},
    )
    snapshot = dispatch("workspace.create-snapshot", {"reason": "M5 dependency change"})
    proposal = dispatch(
        "artifact.propose-revision",
        {"snapshotId": snapshot["snapshotId"], "consequenceLevel": "low"},
    )
    dispatch("artifact.accept-revision", {"proposalId": proposal["proposalId"]})
    return before, kernel.project_store.get_artifact(pid, before["artifactType"])


def _change_requirement(kernel: Any, pid: str, display: str = "R7") -> tuple[Any, Any]:
    content = copy.deepcopy(kernel.project_store.get_artifact(pid, "requirement-set")["content"])
    req = next(r for r in content["requirements"] if r["displayId"] == display)
    req["statement"] += " Revised threshold/input requirement."
    return _accept(kernel, pid, "requirement-set", content)


def test_relevant_change_invalidates_dependents(golden: Any) -> None:
    kernel, pid, _, _ = golden
    original = copy.deepcopy(_case(kernel, pid))
    before, after = _change_requirement(kernel, pid)
    assert _state(kernel, pid) == "STALE"
    assert not validate_against_schema_id(
        _plan(kernel, pid)["content"],
        "https://nexus.local/schemas/artifacts/content/test-plan.v1.schema.json",
    )
    for event in _events(kernel, pid):
        assert not validate_against_schema_id(
            event, "https://nexus.local/schemas/events/project-event.v1.schema.json"
        )
    case = _case(kernel, pid)
    reason = case["applicability"]["reasons"][0]
    assert reason["triggerArtifactType"] == "requirement-set"
    assert "R7" in reason["reason"]
    assert (reason["fromVersion"], reason["toVersion"]) == (
        before["artifactVersion"],
        after["artifactVersion"],
    )
    assert original["linkedRequirementIds"] == case["linkedRequirementIds"] == ["R7"]
    assert reason["path"]
    assert any(e["payload"]["requirementIds"] == ["R7"] for e in _events(kernel, pid))
    for key in ("status", "assessment", "actualResult", "evidenceReferences"):
        assert case[key] == original[key]


def test_unrelated_change_keeps_independent_results(golden: Any) -> None:
    kernel, pid, _, _ = golden
    plan = _plan(kernel, pid)
    _change_requirement(kernel, pid, "R3")
    assert _state(kernel, pid) == "VERIFIED"
    assert _case(kernel, pid)["applicability"]["state"] == "CURRENT"
    assert _plan(kernel, pid)["artifactVersion"] == plan["artifactVersion"]
    assert _events(kernel, pid) == []


def test_transitive_change_propagates(golden: Any) -> None:
    kernel, pid, run, _ = golden
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
    draft = kernel.kernel_store.get_draft(binding["workspaceId"])
    csv_bytes = kernel.filesystem.read_file(binding["workspaceId"], "data/stationary_imu.csv")[
        "content"
    ]
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path="data/stationary_imu.csv",
        content=csv_bytes + b"10.0,0.02,0,1\n",
        actor=_user(kernel, pid, "analysis"),
        expected_draft_version=draft["draftVersion"],
        base_artifact_version=binding["baseArtifactVersion"],
        base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    content = {"summary": "Analysis input revision"}
    content["summary"] = "Changed analysis input CSV revision"
    _accept(kernel, pid, "analysis", content)
    assert _state(kernel, pid) == "STALE"
    assert len(_case(kernel, pid)["applicability"]["reasons"][0]["path"]) >= 3
    # The second branch uses a real firmware run with a deterministic marker log.
    firmware = kernel.kernel_store.get_workspace_by_project_artifact(pid, "firmware")
    runs = kernel.executions.list_runs(pid, limit=1000)[0]
    fw_run = next(r for r in runs if r["workspaceId"] == firmware["workspaceId"])
    kernel.verification.promote_marker_log(
        project_id=pid,
        execution_run_id=fw_run["executionRunId"],
        log_text="NEXUS_READY",
        actor=_user(kernel, pid),
    )
    electrical = copy.deepcopy(
        kernel.project_store.get_artifact(pid, "electrical-architecture")["content"]
    )
    electrical["summary"] = "Changed electrical wiring"
    _accept(kernel, pid, "electrical-architecture", electrical)
    marker_cases = [
        c
        for c in _plan(kernel, pid)["content"]["testCases"]
        if (c.get("verificationBasis") or {}).get("executionRunId") == fw_run["executionRunId"]
    ]
    assert marker_cases
    assert all(c["applicability"]["state"] == "STALE" for c in marker_cases)
    assert all(len(c["applicability"]["reasons"][0]["path"]) >= 4 for c in marker_cases)
    assert run["inputSnapshotId"]


def _legacy_revision(kernel: Any, pid: str, *, unknown: bool) -> None:
    # Simulate a persisted pre-M5 revision through the existing revision store.
    previous = _plan(kernel, pid)
    revision = copy.deepcopy(previous)
    case = next(c for c in revision["content"]["testCases"] if c["displayId"] == "T7")
    if unknown:
        case["verificationBasis"]["dependencies"].append(
            {
                "artifactType": "missing-input",
                "artifactId": "unresolvable",
                "artifactVersion": 1,
                "contentHash": "unknown",
            }
        )
    else:
        case.pop("verificationBasis")
    case.pop("applicability", None)
    revision.update(artifactId=new_id("art"), artifactVersion=previous["artifactVersion"] + 1)
    project = kernel.project_store.get_project(pid)
    kernel.project_store.apply_accepted_artifact_revision(
        project_id=pid,
        new_artifact=revision,
        next_state_version=project["currentStateVersion"] + 1,
        updated_at=revision["updatedAt"],
    )


@pytest.mark.parametrize("unknown", [False, True])
def test_unknown_dependency_cannot_leave_pass(golden: Any, unknown: bool) -> None:
    kernel, pid, run, _ = golden
    count = _plan(kernel, pid)["content"]["coverageSummary"]["verifiedRequirements"]
    _legacy_revision(kernel, pid, unknown=unknown)
    assert _state(kernel, pid) == "RECHECK_REQUIRED"
    case = _case(kernel, pid)
    assert case["assessment"] == "PASS"
    assert case["applicability"]["reasons"][0]["reason"] == "UNKNOWN_DEPENDENCY"
    assert _plan(kernel, pid)["content"]["coverageSummary"]["verifiedRequirements"] == count - 1
    version = _plan(kernel, pid)["artifactVersion"]
    _state(kernel, pid)
    assert _plan(kernel, pid)["artifactVersion"] == version

    # A case introduced after execution has no criterion in that run's inputs.
    before = _plan(kernel, pid)["content"]
    content = copy.deepcopy(before)
    introduced = copy.deepcopy(case)
    introduced["testId"] = new_id("test")
    content["testCases"].append(introduced)
    kernel.invalidation.stamp(pid, before, content, run["executionRunId"])
    assert introduced["verificationBasis"]["dependencies"] == []
    assert introduced["applicability"]["state"] == "RECHECK_REQUIRED"


def test_history_immutable(golden: Any) -> None:
    kernel, pid, _, _ = golden
    before = _plan(kernel, pid)
    ledger = kernel.ledger.list_events(pid, limit=10000)[0]
    _change_requirement(kernel, pid)
    historical = kernel.project_store.get_artifact(
        pid, "test-plan", version=before["artifactVersion"]
    )
    assert historical["content"] == before["content"]
    assert (
        _case(kernel, pid)["evidenceReferences"]
        == next(c for c in before["content"]["testCases"] if c["displayId"] == "T7")[
            "evidenceReferences"
        ]
    )
    after = {e["eventId"]: e for e in kernel.ledger.list_events(pid, limit=10000)[0]}
    assert all(after[e["eventId"]] == e for e in ledger)


def test_invalidation_persists_after_restart(golden: Any) -> None:
    kernel, pid, _, url = golden
    _change_requirement(kernel, pid)
    chain = kernel.verification.evidence_chain(pid)
    events = _events(kernel, pid)
    kernel.jobs.shutdown()
    projects, store = build_stores("sqlite", url)
    restarted = build_project_kernel(store, project_store=projects)
    try:
        assert restarted.verification.evidence_chain(pid) == chain
        assert _state(restarted, pid) == "STALE"
        assert _events(restarted, pid) == events
    finally:
        restarted.jobs.shutdown()


def test_revalidation_only_via_executed_run(golden: Any) -> None:
    kernel, pid, run, _ = golden
    _change_requirement(kernel, pid)
    # Replaying the old run cannot update its basis or restore applicability.
    kernel.verification.promote_execution_evidence(
        project_id=pid, execution_run_id=run["executionRunId"], actor=_user(kernel, pid)
    )
    assert _state(kernel, pid) == "STALE"
    for who, field in (
        (actor("vera"), "applicability"),
        (actor("user"), "applicability"),
        (actor("vera"), "verificationBasis"),
        (actor("user"), "verificationBasis"),
    ):
        content = copy.deepcopy(_plan(kernel, pid)["content"])
        edited = next(c for c in content["testCases"] if c["displayId"] == "T7")
        edited[field] = {"state": "CURRENT", "reasons": []} if field == "applicability" else {}
        workspace = kernel.kernel_store.get_workspace_by_project_artifact(pid, "test-plan")
        result = kernel.dispatch(
            cmd(
                command_type="workspace.update-draft",
                project_id=pid,
                artifact_id=workspace["artifactId"],
                workspace_id=workspace["workspaceId"],
                requested_by=who,
                input_data={"content": content, "expectedDraftVersion": 1},
            )
        )
        assert result["status"] == "failed"
        assert "system-managed" in result["error"]["message"]
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
    script = kernel.filesystem.read_file(binding["workspaceId"], "analysis.py")["content"]

    def write_script(current: Any, data: bytes) -> None:
        draft = current.kernel_store.get_draft(binding["workspaceId"])
        current.filesystem.write_file(
            workspace_id=binding["workspaceId"],
            path="analysis.py",
            content=data,
            actor=_user(current, pid, "analysis"),
            expected_draft_version=draft["draftVersion"],
            base_artifact_version=binding["baseArtifactVersion"],
            base_project_state_version=current.project_store.get_project(pid)[
                "currentStateVersion"
            ],
            origin="USER",
            write_policy="USER_EDITABLE",
        )

    def execute(current: Any) -> Any:
        started = current.workspace_runtime.run_analysis(
            project_id=pid, artifact_type="analysis", actor=_user(current, pid, "analysis")
        )
        return _wait_run(current, started["executionRun"]["executionRunId"])

    write_script(kernel, b"raise SystemExit(1)\n")
    failed = execute(kernel)
    assert failed["status"] == "failed"
    with pytest.raises(VerificationError, match="completed"):
        kernel.verification.promote_execution_evidence(
            project_id=pid, execution_run_id=failed["executionRunId"], actor=_user(kernel, pid)
        )
    assert _state(kernel, pid) == "STALE"
    write_script(kernel, script + b'\nprint("M5 truncation check" * 100)\n')
    kernel.jobs.shutdown()
    limited = build_project_kernel(
        kernel.kernel_store,
        project_store=kernel.project_store,
        execution_limits=ExecutionLimits(stdout_bytes=8, total_log_bytes=8),
    )
    try:
        truncated = execute(limited)
        assert truncated["status"] in {"completed", "completed-with-warnings"}
        assert limited.kernel_store.get_execution_job(truncated["executionJobId"])["logTruncated"]
        with pytest.raises(VerificationError, match="truncated"):
            limited.verification.promote_execution_evidence(
                project_id=pid,
                execution_run_id=truncated["executionRunId"],
                actor=_user(limited, pid),
            )
        assert _state(limited, pid) == "STALE"
    finally:
        limited.jobs.shutdown()
    fresh_kernel = build_project_kernel(kernel.kernel_store, project_store=kernel.project_store)
    try:
        write_script(fresh_kernel, script)
        executed = execute(fresh_kernel)
        assert executed["status"] == "completed"
        promotion = fresh_kernel.verification.promote_execution_evidence(
            project_id=pid,
            execution_run_id=executed["executionRunId"],
            actor=_user(fresh_kernel, pid),
            accept=False,
        )
        assert _state(fresh_kernel, pid) == "STALE"
        workspace = fresh_kernel.kernel_store.get_workspace_by_project_artifact(pid, "test-plan")
        accepted = fresh_kernel.dispatch(
            cmd(
                command_type="artifact.accept-revision",
                project_id=pid,
                artifact_id=workspace["artifactId"],
                workspace_id=workspace["workspaceId"],
                base_artifact_version=workspace["baseArtifactVersion"],
                base_project_state_version=fresh_kernel.project_store.get_project(pid)[
                    "currentStateVersion"
                ],
                input_data={"proposalId": promotion["proposalId"]},
                requested_by=_user(fresh_kernel, pid),
            )
        )
        assert accepted["status"] == "completed", accepted
        assert _state(fresh_kernel, pid) == "VERIFIED"
        assert _case(fresh_kernel, pid)["applicability"] == {"state": "CURRENT", "reasons": []}
        events = _events(fresh_kernel, pid)
        assert any(e["eventType"] == "verification.revalidated" for e in events)
        assert all(
            not validate_against_schema_id(
                e, "https://nexus.local/schemas/events/project-event.v1.schema.json"
            )
            for e in events
        )
    finally:
        fresh_kernel.jobs.shutdown()


def test_repeated_processing_idempotent(golden: Any) -> None:
    kernel, pid, _, _ = golden
    version = _plan(kernel, pid)["artifactVersion"]
    previous, artifact = _change_requirement(kernel, pid)
    events = _events(kernel, pid)
    assert _plan(kernel, pid)["artifactVersion"] == version + 1
    assert len(events) == 1
    assert kernel.invalidation.process(pid, previous, artifact) == {"changed": False}
    assert _plan(kernel, pid)["artifactVersion"] == version + 1
    assert _events(kernel, pid) == events


@pytest.mark.parametrize("broken", ["missing", "foreign", "bytes", "marker"])
def test_consumed_output_with_unknown_basis_requires_recheck(golden: Any, broken: str) -> None:
    """Malformed/legacy handoff metadata cannot produce current PASS evidence."""
    kernel, pid, _, _ = golden
    binding = kernel.workspace_runtime.resolve_binding(project_id=pid, artifact_type="analysis")
    workspace_id = binding["workspaceId"]
    output = next(
        o
        for o in kernel.kernel_store.list_produced_outputs(pid)
        if o["name"] == "outputs/summary.json"
    )
    if broken == "foreign":
        # Corrupt metadata regression, not a supported user import.
        from unittest.mock import patch

        original_get = kernel.kernel_store.get_produced_output

        def foreign(oid):
            return {**original_get(oid), "projectId": "foreign"}

        guard = patch.object(kernel.kernel_store, "get_produced_output", side_effect=foreign)
    else:
        from contextlib import nullcontext

        guard = nullcontext()
    kernel.filesystem.write_file(
        workspace_id=workspace_id,
        path="data/handoff.txt",
        content=(
            output["content"]["structuredResult"]["text"].encode()
            if broken == "foreign"
            else b"unmatched observation"
        ),
        actor=_user(kernel, pid, "analysis"),
        expected_draft_version=kernel.kernel_store.get_draft(workspace_id)["draftVersion"],
        base_artifact_version=binding["baseArtifactVersion"],
        base_project_state_version=kernel.project_store.get_project(pid)["currentStateVersion"],
        origin="RUNTIME_OUTPUT",
        write_policy="USER_EDITABLE",
        generated_from=(
            None
            if broken == "marker"
            else "imported-output:" + ("out_missing" if broken == "missing" else output["outputId"])
        ),
    )
    with guard:
        started = kernel.workspace_runtime.run_analysis(
            project_id=pid, artifact_type="analysis", actor=_user(kernel, pid, "analysis")
        )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"])
    assert run["status"] == "completed"
    kernel.verification.promote_execution_evidence(
        project_id=pid,
        execution_run_id=run["executionRunId"],
        actor=_user(kernel, pid),
    )
    case = _case(kernel, pid)
    assert case["assessment"] == "PASS"
    assert case["applicability"]["state"] == "RECHECK_REQUIRED"
    assert case["verificationBasis"]["dependencies"] == []
    assert any(r["reason"] == "UNKNOWN_DEPENDENCY" for r in case["applicability"]["reasons"])
