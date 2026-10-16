"""N28 M4/M9 authority and M2/M8 durable history acceptance gaps."""

from pathlib import Path

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel, cmd, minimal_package
from nexus_board import build_project_kernel
from nexus_persistence import build_stores


@pytest.mark.parametrize("actor_type", ["vera", "embedded-systems-agent", "execution"])
def test_non_user_acceptance_is_rejected_and_recorded(actor_type: str) -> None:
    """M4/M9: deny actual acceptance, preserve state, and retain the denial."""
    kernel, projects, store, project_id = build_test_kernel()
    artifact = projects.get_artifact(project_id, "requirement-set")
    editor = actor()
    workspace = kernel.workspaces.create_workspace(
        project_id=project_id, artifact_type="requirement-set", actor=editor
    )["workspace"]["workspaceId"]

    def dispatch(command_type: str, data: dict, requested_by: dict | None = None) -> dict:
        return kernel.dispatch(
            cmd(
                command_type=command_type,
                project_id=project_id,
                artifact_id=artifact["artifactId"],
                workspace_id=workspace,
                input_data=data,
                requested_by=requested_by or editor,
            )
        )

    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=artifact["artifactId"],
        workspace_id=workspace,
        requested_by=editor,
    )
    snapshot = dispatch("workspace.create-snapshot", {"reason": "authority check"})
    proposal = dispatch("artifact.propose-revision", {"snapshotId": snapshot["snapshotId"]})
    before = store.get_proposal(proposal["proposalId"])
    result = dispatch(
        "artifact.accept-revision", {"proposalId": proposal["proposalId"]}, actor(actor_type)
    )
    assert result["status"] == "rejected"
    assert result["error"]["code"] == "GOVERNANCE_REJECTED"
    assert store.get_command_run(result["commandRunId"]) == result
    assert projects.get_artifact(project_id, "requirement-set") == artifact
    assert projects.get_project(project_id)["currentStateVersion"] == 1
    assert store.get_proposal(proposal["proposalId"]) == before
    accepted = dispatch("artifact.accept-revision", {"proposalId": proposal["proposalId"]})
    assert accepted["status"] == "completed"
    assert projects.get_artifact(project_id, "requirement-set")["artifactVersion"] == 2


def test_sqlite_restart_reconstructs_execution_history(tmp_path: Path) -> None:
    """M2/M8: reopen durable stores and resolve run inputs, outputs and history."""
    url = f"sqlite:///{tmp_path / 'history.sqlite3'}"
    projects, store = build_stores("sqlite", url)
    package = minimal_package()
    projects.save_initialization_package(package)
    project_id = package["project"]["projectId"]
    artifact = projects.get_artifact(project_id, "requirement-set")
    kernel = build_project_kernel(store, project_store=projects)
    editor = actor()
    workspace = kernel.workspaces.create_workspace(
        project_id=project_id, artifact_type="requirement-set", actor=editor
    )["workspace"]["workspaceId"]

    def dispatch(command_type: str, data: dict, version: int = 1) -> dict:
        result = kernel.dispatch(
            cmd(
                command_type=command_type,
                project_id=project_id,
                artifact_id=artifact["artifactId"],
                workspace_id=workspace,
                base_artifact_version=version,
                base_project_state_version=version,
                input_data=data,
                requested_by=editor,
            )
        )
        assert result["status"] == "completed", result
        return result

    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=artifact["artifactId"],
        workspace_id=workspace,
        requested_by=editor,
    )
    dispatch("workspace.update-draft", {"content": {"requirements": []}, "expectedDraftVersion": 1})
    snapshot = dispatch("workspace.create-snapshot", {"reason": "durable input"})
    proposal = dispatch("artifact.propose-revision", {"snapshotId": snapshot["snapshotId"]})
    dispatch("artifact.accept-revision", {"proposalId": proposal["proposalId"]})
    # A fresh snapshot records the accepted revision's bases.
    snapshot = dispatch("workspace.create-snapshot", {"reason": "accepted input"}, 2)
    result = dispatch(
        "artifact.execute",
        {"snapshotId": snapshot["snapshotId"], "capability": "fake-execution"},
        2,
    )
    run = store.get_execution_run(result["executionRunId"])
    assert run["inputSnapshotId"] == snapshot["snapshotId"]
    outputs = store.list_produced_outputs(project_id)
    assert {o["outputId"] for o in outputs} == set(run["outputReferences"])
    assert outputs
    events, _ = store.list_project_events(project_id)
    assert {e["eventType"] for e in events} >= {
        "artifact.revision-accepted",
        "execution.completed",
        "evidence.attached",
    }
    nodes = store.list_graph_nodes(project_id)
    edges = store.list_graph_edges(project_id)
    assert nodes and edges
    board = kernel.get_board(project_id)
    saved_snapshot = store.get_snapshot(snapshot["snapshotId"])
    historical = projects.get_artifact(project_id, "requirement-set", version=1)
    assert historical["content"] == artifact["content"]
    assert historical["lifecycleStatus"] == "superseded"
    del kernel, store, projects

    projects, store = build_stores("sqlite", url)
    kernel = build_project_kernel(store, project_store=projects)
    assert projects.get_artifact(project_id, "requirement-set", version=1) == historical
    assert projects.get_artifact(project_id, "requirement-set")["artifactVersion"] == 2
    assert store.get_proposal(proposal["proposalId"])["status"] == "accepted"
    assert store.get_execution_run(run["executionRunId"]) == run
    assert store.get_snapshot(run["inputSnapshotId"]) == saved_snapshot
    assert saved_snapshot["content"]["structuredContent"] == {"requirements": []}
    assert store.list_produced_outputs(project_id) == outputs
    reopened_events, cursor = store.list_project_events(project_id)
    assert reopened_events == events
    assert cursor is None
    assert store.list_graph_nodes(project_id) == nodes
    assert store.list_graph_edges(project_id) == edges
    assert kernel.get_board(project_id) == board
    assert store.get_command_run(result["commandRunId"]) == result
