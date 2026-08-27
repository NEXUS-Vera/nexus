"""Phase 16B deterministic Analysis scaffold tests."""

from __future__ import annotations

import pytest

from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.analysis.scaffold import (
    ANALYSIS_PYTHON_V1_ANALYSIS_PY_BYTES,
    ANALYSIS_PYTHON_V1_PROFILE,
    ANALYSIS_PYTHON_V1_PROFILE_ID,
    ANALYSIS_PYTHON_V1_PROFILE_VERSION,
    ANALYSIS_PYTHON_V1_README_BYTES,
    get_analysis_scaffold_profile,
    materialize_analysis_scaffold_files,
)
from nexus_board.errors import WorkspaceScaffoldConflictError
from nexus_board.services.workspace_runtime import WorkspaceRuntimeCapabilityError


def test_scaffold_profile_is_stable_and_deterministic() -> None:
    profile = get_analysis_scaffold_profile()
    assert profile.profile_id == ANALYSIS_PYTHON_V1_PROFILE_ID
    assert profile.profile_version == ANALYSIS_PYTHON_V1_PROFILE_VERSION
    assert profile.entrypoint == "analysis.py"

    first = materialize_analysis_scaffold_files()
    second = materialize_analysis_scaffold_files()
    assert [item["path"] for item in first] == [item["path"] for item in second]
    assert [item["content"] for item in first] == [item["content"] for item in second]

    assert ANALYSIS_PYTHON_V1_PROFILE.generated_from == (
        f"{ANALYSIS_PYTHON_V1_PROFILE_ID}@{ANALYSIS_PYTHON_V1_PROFILE_VERSION}"
    )
    assert {item["path"] for item in first} == {"analysis.py", "README.md"}


def test_generate_scaffold_on_blank_analysis_workspace() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
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
    result = kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert result["status"] == "generated"
    assert result["generationId"].startswith("gen_")
    assert result["profile"]["profileId"] == ANALYSIS_PYTHON_V1_PROFILE_ID
    paths = {item["path"] for item in result["generatedFiles"]}
    assert paths == {"analysis.py", "README.md"}

    listed = kernel.workspace_runtime.list_files(project_id=project_id, artifact_type="analysis")
    assert {f["path"] for f in listed["files"]} == paths

    read_analysis = kernel.workspace_runtime.read_file(
        project_id=project_id, artifact_type="analysis", path="analysis.py"
    )
    assert read_analysis["content"] == ANALYSIS_PYTHON_V1_ANALYSIS_PY_BYTES

    read_readme = kernel.workspace_runtime.read_file(
        project_id=project_id, artifact_type="analysis", path="README.md"
    )
    assert read_readme["content"] == ANALYSIS_PYTHON_V1_README_BYTES

    events, _ = kernel_store.list_project_events(project_id, limit=50)
    scaffold_events = [e for e in events if e["eventType"] == "workspace.scaffold-generated"]
    assert len(scaffold_events) == 1
    payload = scaffold_events[0]["payload"]
    assert payload["scaffoldProfileId"] == ANALYSIS_PYTHON_V1_PROFILE_ID
    assert payload["scaffoldProfileVersion"] == ANALYSIS_PYTHON_V1_PROFILE_VERSION
    assert payload["generationKind"] == "scaffold"
    assert scaffold_events[0]["actor"]["actorId"] == user["actorId"]


def test_scaffold_preserves_unrelated_files_and_blocks_conflicts() -> None:
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
        path="notes.txt",
        content=b"keep me\n",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )

    draft_version = 2
    generated = kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=draft_version,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert generated["status"] == "generated"
    listed = kernel.workspace_runtime.list_files(project_id=project_id, artifact_type="analysis")
    assert {f["path"] for f in listed["files"]} == {"notes.txt", "analysis.py", "README.md"}

    # Conflicting analysis.py blocks scaffold generation.
    kernel2, _ps2, _ks2, project_id2 = build_test_kernel(auto_start_scheduler=False)
    user2 = actor("user")
    binding2 = kernel2.workspace_runtime.resolve_binding(project_id=project_id2, artifact_type="analysis", actor=user2)
    acquire_edit_lease(
        kernel2,
        project_id=project_id2,
        artifact_id=binding2["artifactId"],
        workspace_id=binding2["workspaceId"],
        requested_by=user2,
    )
    kernel2.workspace_runtime.write_file(
        project_id=project_id2,
        artifact_type="analysis",
        path="analysis.py",
        content=b"# user override\n",
        actor=user2,
        expected_draft_version=1,
        base_artifact_version=int(binding2["baseArtifactVersion"]),
        base_project_state_version=int(binding2["baseProjectStateVersion"]),
    )

    with pytest.raises(WorkspaceScaffoldConflictError):
        kernel2.workspace_runtime.generate_analysis_scaffold(
            project_id=project_id2,
            artifact_type="analysis",
            actor=user2,
            expected_draft_version=2,
            base_artifact_version=int(binding2["baseArtifactVersion"]),
            base_project_state_version=int(binding2["baseProjectStateVersion"]),
        )


def test_scaffold_denied_for_non_analysis_artifact() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    with pytest.raises(WorkspaceRuntimeCapabilityError):
        kernel.workspace_runtime.generate_analysis_scaffold(
            project_id=project_id,
            artifact_type="firmware",
            actor=user,
            expected_draft_version=1,
            base_artifact_version=1,
            base_project_state_version=1,
        )

