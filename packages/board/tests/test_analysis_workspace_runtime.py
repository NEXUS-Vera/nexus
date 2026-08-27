"""Phase 16A analysis workspace facade tests."""

from __future__ import annotations

import pytest

from helpers import acquire_edit_lease, actor, build_test_kernel


def test_analysis_binding_and_capabilities() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="analysis",
    )
    assert binding["projectId"] == project_id
    assert binding["artifactType"] == "analysis"
    assert binding["workspaceId"].startswith("ws_")
    assert binding["capabilities"]["filesystem"] is True
    assert binding["capabilities"]["snapshots"] is True
    assert binding["capabilities"]["execution"] is True
    assert binding["filesystemEnabled"] is True

    again = kernel.workspace_runtime.resolve_binding(project_id=project_id, artifact_type="analysis")
    assert again["workspaceId"] == binding["workspaceId"]
    assert again["artifactId"] == binding["artifactId"]


def test_analysis_file_read_write_delete_via_facade() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )

    written = kernel.workspace_runtime.write_file(
        project_id=project_id,
        artifact_type="analysis",
        path="notes.md",
        content=b"# Title\n",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert written["file"]["path"] == "notes.md"
    assert written.get("draft")
    next_draft_version = int(written["draft"]["draftVersion"])

    listed = kernel.workspace_runtime.list_files(project_id=project_id, artifact_type="analysis")
    assert any(f["path"] == "notes.md" for f in listed["files"])

    read = kernel.workspace_runtime.read_file(
        project_id=project_id,
        artifact_type="analysis",
        path="notes.md",
    )
    assert read["content"] == b"# Title\n"

    kernel.workspace_runtime.delete_file(
        project_id=project_id,
        artifact_type="analysis",
        path="notes.md",
        actor=user,
        expected_draft_version=next_draft_version,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )

    listed2 = kernel.workspace_runtime.list_files(project_id=project_id, artifact_type="analysis")
    assert not any(f["path"] == "notes.md" for f in listed2["files"])


@pytest.mark.parametrize("path", ["notes.md", "data.csv"])
def test_analysis_allows_multiple_paths(path: str) -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(project_id=project_id, artifact_type="analysis", actor=user)
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.write_file(
        project_id=project_id,
        artifact_type="analysis",
        path=path,
        content=b"x",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )

