"""Dependency-aware verification over immutable artifacts, graph and ledger stores."""

from __future__ import annotations

import copy
from collections import deque
from typing import Any

from nexus_persistence.errors import PersistenceNotFoundError

from nexus_board.ids import content_digest, new_id, utc_now_iso
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)

SYSTEM = {
    "schemaVersion": "1.0.0",
    "actorType": "system",
    "actorId": "actor_systeminvalidation00000001",
    "displayName": "system:invalidation",
}


def protected_fields(content: dict[str, Any]) -> dict[str, Any]:
    return {
        str(c.get("testId")): {k: c[k] for k in ("applicability", "verificationBasis") if k in c}
        for c in content.get("testCases", [])
        if "applicability" in c or "verificationBasis" in c
    }


class InvalidationService:
    def __init__(self, projects: Any, store: Any, graph: Any, ledger: Any, projection: Any):
        self._projects = projects
        self._store = store
        self._graph = graph
        self._ledger = ledger
        self._projection = projection

    def bind_workspace(self, project_id: str, artifact_type: str) -> None:
        """Pin known workspace inputs in the existing dependency graph."""
        inputs = {"firmware": ["electrical-architecture"], "analysis": []}
        artifacts = {a["artifactType"]: a for a in self._projects.get_artifacts(project_id)}
        artifact = artifacts.get(artifact_type)
        if artifact is None:
            workspace = self._store.get_workspace_by_project_artifact(project_id, artifact_type)
            if workspace is None:
                return
            artifact = workspace
        source = self._node(project_id, artifact["artifactId"], "artifact", artifact_type)
        existing = self._graph.reader.get_downstream(
            project_id, source["nodeId"], max_depth=1, edge_type="depends-on"
        )
        pinned_types = {n["label"] for n in existing["nodes"] if n["nodeId"] != source["nodeId"]}
        for input_type in inputs.get(artifact_type, []):
            if input_type in pinned_types:
                continue
            target = artifacts.get(input_type)
            if target is None:
                target = {"artifactId": f"unresolved:{input_type}"}
            if target:
                self._link(
                    project_id,
                    source,
                    self._node(project_id, target["artifactId"], "artifact", input_type),
                )

    def record_run(self, run: dict[str, Any]) -> None:
        """Capture revision identities before execution, never at revalidation time."""
        pid = run["projectId"]
        workspace = self._store.get_workspace(run["workspaceId"])
        self.bind_workspace(pid, workspace["artifactType"])
        execution = self._node(pid, run["executionRunId"], "execution", "ExecutionRun")
        snapshot = self._node(pid, run["inputSnapshotId"], "workspace", "Input snapshot")
        producer = self._node(pid, run["artifactId"], "artifact", workspace["artifactType"])
        self._link(pid, execution, snapshot)
        self._link(pid, snapshot, producer)
        for artifact in self._projects.get_artifacts(pid):
            kind = artifact["artifactType"]
            if kind not in {"requirement-set", "test-plan"}:
                continue
            entries = artifact["content"].get(
                "requirements" if kind == "requirement-set" else "testCases", []
            )
            for entry in entries:
                key = (
                    entry.get("requirementId") if kind == "requirement-set" else entry.get("testId")
                )
                node = self._node(
                    pid,
                    f"{artifact['artifactId']}#{key}",
                    "requirement" if kind == "requirement-set" else "evidence",
                    kind,
                )
                self._link(pid, execution, node)

    def basis_is_current(self, project_id: str, case: dict[str, Any]) -> bool:
        basis = case.get("verificationBasis") or {}
        try:
            run = self._store.get_execution_run(basis.get("executionRunId", ""))
            if (
                run.get("projectId") != project_id
                or run.get("status") not in {"completed", "completed-with-warnings"}
                or run.get("inputSnapshotId") != basis.get("inputSnapshotId")
            ):
                return False
            if run.get("executionJobId") and self._store.get_execution_job(
                run["executionJobId"]
            ).get("logTruncated"):
                return False
            dependencies = basis.get("dependencies") or []
            return bool(dependencies) and all(
                self._current_hash(project_id, d, case) == d.get("contentHash")
                for d in dependencies
            )
        except (KeyError, PersistenceNotFoundError):
            return False

    def stamp(
        self, project_id: str, before: dict[str, Any], content: dict[str, Any], run_id: str
    ) -> None:
        """Stamp only newly assessed cases, retaining stale historical observations."""
        old = {c["testId"]: c for c in before.get("testCases", [])}
        try:
            run = self._store.get_execution_run(run_id)
        except (KeyError, PersistenceNotFoundError):
            run = None
        valid = bool(
            run
            and run.get("projectId") == project_id
            and run.get("status") in {"completed", "completed-with-warnings"}
        )
        if valid and run and run.get("executionJobId"):
            valid = not self._store.get_execution_job(run["executionJobId"]).get("logTruncated")
        for case in content.get("testCases", []):
            previous = old.get(case["testId"], {})
            if case == previous:
                continue
            dependencies = self._run_dependencies(project_id, run, case) if run else []
            basis = {
                "executionRunId": run_id,
                "inputSnapshotId": run.get("inputSnapshotId", "") if run else "",
                "dependencies": dependencies,
            }
            case["verificationBasis"] = basis
            known = (
                valid
                and bool(dependencies)
                and all(
                    self._current_hash(project_id, d, case) == d["contentHash"]
                    for d in dependencies
                )
            )
            if known:
                case["applicability"] = {"state": "CURRENT", "reasons": []}
            else:
                case["applicability"] = {
                    "state": "RECHECK_REQUIRED",
                    "reasons": [
                        self._reason(
                            case, "test-plan", case["testId"], 0, 0, [], "UNKNOWN_DEPENDENCY"
                        )
                    ],
                }
            case_node = self._node(project_id, case["testId"], "evidence", case["displayId"])
            if run:
                run_node = self._node(project_id, run_id, "execution", "ExecutionRun")
                self._link(project_id, case_node, run_node)
            for dep in dependencies:
                ref = dep["artifactId"] + ("#" + dep["entryId"] if dep.get("entryId") else "")
                target = self._node(
                    project_id,
                    ref,
                    "requirement" if dep["artifactType"] == "requirement-set" else "artifact",
                    dep["artifactType"],
                )
                # Requirements link directly; producer paths retain the run and snapshot.
                if dep["artifactType"] == "requirement-set":
                    self._link(project_id, case_node, target)
        self._summary(project_id, content)

    def _run_dependencies(
        self, pid: str, run: dict[str, Any], case: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if not all(
            run.get(k)
            for k in ("artifactId", "inputSnapshotId", "workspaceId", "baseArtifactVersion")
        ):
            return []
        nodes = self._store.list_graph_nodes(pid)
        root = next((n for n in nodes if n.get("refId") == run["executionRunId"]), None)
        if root is None:
            return []
        closure = self._graph.reader.get_downstream(
            pid,
            root["nodeId"],
            max_depth=50,
            max_nodes=10000,
            max_edges=20000,
            edge_type="depends-on",
        )
        if closure["truncated"]:
            return []
        artifacts = {a["artifactId"]: a for a in self._projects.get_artifacts(pid)}
        # Superseded inputs remain resolvable by version through existing artifact history.
        history = self._projects.get_history(pid, limit=100000)
        for ref in history.get("artifactRevisions", []):
            kind = ref.get("artifactType")
            if kind and ref.get("artifactVersion"):
                a = self._projects.get_artifact(pid, kind, version=ref["artifactVersion"])
                artifacts[a["artifactId"]] = a
        deps = []
        workspace = self._store.get_workspace(run["workspaceId"])
        snapshot = self._store.get_snapshot(run["inputSnapshotId"])
        deps.append(
            {
                "artifactType": workspace["artifactType"],
                "artifactId": run["artifactId"],
                "artifactVersion": run["baseArtifactVersion"],
                "contentHash": content_digest(snapshot["content"]),
                "snapshotId": run["inputSnapshotId"],
            }
        )
        linked = case.get("linkedRequirementIds", [])
        resolved_requirements: set[str] = set()
        resolved_criterion = False
        for node in closure["nodes"]:
            ref = str(node.get("refId", ""))
            aid, _, entry_id = ref.partition("#")
            artifact = artifacts.get(aid)
            if aid == run["artifactId"]:
                continue
            if artifact is None:
                if node["nodeType"] in {"artifact", "artifact-revision", "requirement"}:
                    return []
                continue
            kind = artifact["artifactType"]
            value = artifact["content"]
            if entry_id:
                entries = value.get(
                    "requirements" if kind == "requirement-set" else "testCases", []
                )
                entry = next(
                    (e for e in entries if entry_id in {e.get("testId"), e.get("requirementId")}),
                    None,
                )
                if entry is None:
                    continue
                if kind == "requirement-set":
                    if entry_id not in linked and entry.get("displayId") not in linked:
                        continue
                    resolved_requirements.update({entry_id, str(entry.get("displayId"))})
                    value = entry
                elif kind == "test-plan":
                    if entry_id != case["testId"]:
                        continue
                    value = entry.get("criterion")
                    resolved_criterion = True
            deps.append(
                {
                    "artifactType": kind,
                    "artifactId": aid,
                    "artifactVersion": artifact["artifactVersion"],
                    "contentHash": content_digest(value),
                    **({"entryId": entry_id} if entry_id else {}),
                }
            )
        if not resolved_criterion or not set(linked).issubset(resolved_requirements):
            return []
        return deps

    def _current_hash(self, pid: str, dep: dict[str, Any], case: dict[str, Any]) -> str | None:
        if not isinstance(dep, dict) or not all(
            dep.get(k) for k in ("artifactType", "artifactId", "artifactVersion", "contentHash")
        ):
            return None
        try:
            artifact = self._projects.get_artifact(pid, dep["artifactType"])
        except (KeyError, PersistenceNotFoundError):
            if dep.get("snapshotId"):
                try:
                    snapshot = self._store.get_snapshot(dep["snapshotId"])
                    workspace = self._store.get_workspace(snapshot["workspaceId"])
                    if (
                        snapshot["artifactId"] != dep["artifactId"]
                        or workspace["artifactType"] != dep["artifactType"]
                    ):
                        return None
                    return content_digest(snapshot["content"])
                except (KeyError, PersistenceNotFoundError):
                    return None
            return None
        if dep.get("snapshotId"):
            if artifact["artifactId"] == dep["artifactId"]:
                return content_digest(self._store.get_snapshot(dep["snapshotId"])["content"])
            events, cursor = self._ledger.list_events(pid, limit=1000)
            while True:
                for event in events:
                    if (
                        event["eventType"] == "artifact.revision-accepted"
                        and event["subject"]["subjectId"] == artifact["artifactId"]
                    ):
                        proposal = self._store.get_proposal(event["payload"]["proposalId"])
                        return content_digest(
                            self._store.get_snapshot(proposal["snapshotId"])["content"]
                        )
                if not cursor:
                    break
                events, cursor = self._ledger.list_events(pid, limit=1000, cursor=cursor)
        value = artifact["content"]
        entry_id = dep.get("entryId")
        if entry_id:
            if dep["artifactType"] == "test-plan":
                return content_digest(case.get("criterion")) if entry_id == case["testId"] else None
            value = next(
                (
                    r
                    for r in value.get("requirements", [])
                    if entry_id in {r.get("requirementId"), r.get("displayId")}
                ),
                None,
            )
            if value is None:
                return None
        return content_digest(value)

    def process(
        self,
        project_id: str,
        previous: dict[str, Any] | None,
        artifact: dict[str, Any],
        *,
        backfill: bool = False,
    ) -> dict[str, Any]:
        """One system revision per trigger; only applicability and summary may change."""
        try:
            plan = self._projects.get_artifact(project_id, "test-plan")
        except (KeyError, PersistenceNotFoundError):
            return {"changed": False}
        content = copy.deepcopy(plan["content"])
        events = []
        for case in content.get("testCases", []):
            basis = case.get("verificationBasis")
            observed = case.get("assessment") in {"PASS", "FAIL", "INCONCLUSIVE"} or case.get(
                "status"
            ) in {"passed", "failed"}
            if not observed:
                continue
            reasons = []
            if (
                not isinstance(basis, dict)
                or not isinstance(basis.get("dependencies"), list)
                or not basis["dependencies"]
            ):
                if any(
                    r.get("reason") == "UNKNOWN_DEPENDENCY"
                    for r in (case.get("applicability") or {}).get("reasons", [])
                ):
                    continue
                reasons.append(
                    self._reason(
                        case,
                        artifact["artifactType"],
                        artifact["artifactId"],
                        previous["artifactVersion"] if previous else 0,
                        artifact["artifactVersion"],
                        [],
                        "UNKNOWN_DEPENDENCY",
                    )
                )
            else:
                for raw_dep in basis["dependencies"]:
                    dep = raw_dep if isinstance(raw_dep, dict) else {}
                    dep = {
                        "artifactType": "unknown",
                        "artifactId": "unknown",
                        "artifactVersion": 0,
                        **dep,
                    }
                    current = self._current_hash(project_id, dep, case)
                    if current is None or not dep.get("contentHash"):
                        if backfill and any(
                            r.get("reason") == "UNKNOWN_DEPENDENCY"
                            for r in (case.get("applicability") or {}).get("reasons", [])
                        ):
                            continue
                        reason = "UNKNOWN_DEPENDENCY"
                    elif (
                        current == dep["contentHash"]
                        or backfill
                        or dep["artifactType"] != artifact["artifactType"]
                    ):
                        continue
                    else:
                        reason = "DEPENDENCY_CHANGED"
                    path = self._path(project_id, case["testId"], dep, basis.get("executionRunId"))
                    reasons.append(
                        self._reason(
                            case,
                            artifact["artifactType"],
                            artifact["artifactId"],
                            previous["artifactVersion"] if previous else dep["artifactVersion"],
                            artifact["artifactVersion"],
                            path,
                            reason
                            + (
                                ":"
                                + (
                                    ",".join(case.get("linkedRequirementIds", []))
                                    if dep["artifactType"] == "requirement-set"
                                    else str(dep.get("entryId", dep["artifactType"]))
                                )
                                if reason != "UNKNOWN_DEPENDENCY"
                                else ""
                            ),
                        )
                    )
            existing = case.get("applicability") or {"state": "CURRENT", "reasons": []}
            old_reasons = existing.get("reasons", [])
            reasons = [
                r for r in reasons if r["eventId"] not in {x["eventId"] for x in old_reasons}
            ]
            if not reasons:
                continue
            all_reasons = old_reasons + reasons
            state = (
                "RECHECK_REQUIRED"
                if any(r["reason"] == "UNKNOWN_DEPENDENCY" for r in all_reasons)
                else "STALE"
            )
            case["applicability"] = {"state": state, "reasons": all_reasons}
            events.extend((case, r) for r in reasons)
        if not events:
            return {"changed": False}
        self._summary(project_id, content)
        self._write_revision(project_id, plan, content)
        emitted = set()
        for case, reason in events:
            if reason["eventId"] in emitted:
                continue
            emitted.add(reason["eventId"])
            self._event(project_id, "verification.invalidated", case, reason["eventId"], reason)
        return {"changed": True}

    def backfill(self, project_id: str) -> None:
        try:
            plan = self._projects.get_artifact(project_id, "test-plan")
        except PersistenceNotFoundError:
            return
        self.process(project_id, None, plan, backfill=True)

    def _write_revision(self, pid: str, plan: dict[str, Any], content: dict[str, Any]) -> None:
        revision = copy.deepcopy(plan)
        now = utc_now_iso()
        revision.update(
            artifactId=new_id("art"),
            artifactVersion=plan["artifactVersion"] + 1,
            supersedesArtifactId=plan["artifactId"],
            supersedesArtifactVersion=plan["artifactVersion"],
            content=content,
            createdBy=SYSTEM,
            updatedAt=now,
            createdAt=now,
        )
        project = self._projects.get_project(pid)
        self._projects.apply_accepted_artifact_revision(
            project_id=pid,
            new_artifact=revision,
            next_state_version=project["currentStateVersion"] + 1,
            updated_at=now,
            expected_artifact_version=plan["artifactVersion"],
            expected_project_state_version=project["currentStateVersion"],
        )
        event_id = next(
            r["eventId"]
            for c in content["testCases"]
            for r in (c.get("applicability") or {}).get("reasons", [])
        )
        for artifact in (plan, revision):
            self._graph.ensure_artifact_node(
                project_id=pid,
                artifact_id=artifact["artifactId"],
                artifact_type="test-plan",
                created_by_event_id=event_id,
            )
        self._graph.link_supersedes(
            project_id=pid,
            from_artifact_id=revision["artifactId"],
            to_artifact_id=plan["artifactId"],
            created_by_event_id=event_id,
        )
        workspace = self._store.get_workspace_by_project_artifact(pid, "test-plan")
        if workspace is not None:
            workspace.update(
                artifactId=revision["artifactId"],
                baseArtifactVersion=revision["artifactVersion"],
                baseProjectStateVersion=project["currentStateVersion"] + 1,
                updatedAt=now,
            )
            self._store.update_workspace(workspace)
            draft = self._store.get_draft(workspace["workspaceId"])
            draft.update(
                baseArtifactVersion=revision["artifactVersion"],
                baseProjectStateVersion=project["currentStateVersion"] + 1,
            )
            self._store.update_draft(draft)
        self._projection.update_after_write(pid)

    def revalidated(self, pid: str, before: dict[str, Any], content: dict[str, Any]) -> None:
        old = {c["testId"]: c for c in before.get("testCases", [])}
        for case in content.get("testCases", []):
            if (case.get("applicability") or {}).get("state") == "CURRENT" and (
                old.get(case["testId"], {}).get("applicability") or {}
            ).get("state") in {"STALE", "RECHECK_REQUIRED"}:
                run_id = case["verificationBasis"]["executionRunId"]
                eid = "evt_" + content_digest([case["testId"], run_id, "revalidated"])[7:39]
                self._event(pid, "verification.revalidated", case, eid, {"executionRunId": run_id})

    def _event(
        self, pid: str, kind: str, case: dict[str, Any], eid: str, payload: dict[str, Any]
    ) -> None:
        self._ledger.append(
            project_id=pid,
            event_type=kind,
            event_id=eid,
            actor=SYSTEM,
            subject_type="evidence",
            subject_id=case["testId"],
            payload={
                **payload,
                "testId": case["testId"],
                "requirementIds": case.get("linkedRequirementIds", []),
            },
        )

    def _reason(
        self,
        case: dict[str, Any],
        kind: str,
        aid: str,
        start: int,
        end: int,
        path: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "triggerArtifactType": kind,
            "triggerArtifactId": aid,
            "fromVersion": start,
            "toVersion": end,
            "path": path,
            "reason": reason,
            "eventId": "evt_" + content_digest([case["testId"], aid, end])[7:39],
        }

    def _path(
        self, pid: str, case_id: str, dep: dict[str, Any], run_id: str | None = None
    ) -> list[str]:
        records = self._store.list_graph_nodes(pid)
        nodes = {n.get("refId"): n["nodeId"] for n in records}
        other_runs = {
            n["nodeId"]
            for n in records
            if n["nodeType"] == "execution" and n.get("refId") != run_id
        }
        target = nodes.get(dep["artifactId"] + ("#" + dep["entryId"] if dep.get("entryId") else ""))
        queue = deque([(nodes.get(case_id), [])])
        seen = set()
        edges = self._store.list_graph_edges(pid)
        while queue:
            node, path = queue.popleft()
            if node == target and node is not None:
                return path
            if node in seen:
                continue
            seen.add(node)
            for edge in edges:
                if (
                    edge["edgeType"] == "depends-on"
                    and edge["sourceNodeId"] == node
                    and edge["targetNodeId"] not in other_runs
                ):
                    queue.append((edge["targetNodeId"], path + [edge["edgeId"]]))
        return []

    def _summary(self, pid: str, content: dict[str, Any]) -> None:
        requirements = self._projects.get_artifact(pid, "requirement-set")["content"][
            "requirements"
        ]
        content["coverageSummary"] = compute_test_plan_coverage_summary(
            compute_requirement_coverage(requirements=requirements, test_cases=content["testCases"])
        )

    def _node(self, pid: str, ref: str, kind: str, label: str) -> dict[str, Any]:
        return self._graph.ensure_dependency_node(pid, ref, kind, label)

    def _link(self, pid: str, source: dict[str, Any], target: dict[str, Any]) -> None:
        self._graph.link_depends_on(project_id=pid, source=source, target=target)
