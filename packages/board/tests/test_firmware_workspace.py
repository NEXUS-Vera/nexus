"""Firmware Phase 15A registry + workspace-runtime binding."""

from __future__ import annotations

from helpers import build_test_kernel


def test_firmware_binding_resolves_filesystem_workspace() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="firmware",
    )
    assert binding["artifactType"] == "firmware"
    assert binding["capabilities"]["filesystem"] is True
    assert binding["capabilities"]["execution"] is True
    assert binding["filesystemEnabled"] is True
    assert binding["workspace"]["workspaceType"] == "code-workspace"

    again = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="firmware",
    )
    assert again["workspaceId"] == binding["workspaceId"]
