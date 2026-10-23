"""Analysis Python toolchain mapping (Phase 16D / 16G).

Maps the product operation ``analysis.run`` to an approved ExecutionCommandSpec.
Never exposes arbitrary shell commands to callers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus_board.analysis.patch import snapshot_manifest_index
from nexus_board.errors import CommandValidationError
from nexus_board.execution.command_spec import validate_command_spec

ANALYSIS_RUN_OPERATION = "analysis.run"

# Snapshot reasons.
SNAPSHOT_REASON_BEFORE_RUN = "before-analysis-run"
SNAPSHOT_REASON_BEFORE_RESTORE = "before-analysis-restore"

ANALYSIS_ENTRYPOINT = "analysis.py"
ANALYSIS_OUTPUT_DIR = "outputs"
ANALYSIS_OUTPUT_RESULTS = "outputs/results.json"
ANALYSIS_OUTPUT_SUMMARY = "outputs/summary.json"
ANALYSIS_OUTPUT_PROCESSED_CSV = "outputs/processed.csv"
ANALYSIS_OUTPUT_PLOT_PNG = "outputs/accel_plot.png"
ANALYSIS_OUTPUT_NOTE_TXT = "outputs/note.txt"

# Bounded approved Analysis output manifest (Phase 14 declared-path collection).
ANALYSIS_DECLARED_OUTPUTS: tuple[dict[str, str], ...] = (
    {"path": ANALYSIS_OUTPUT_RESULTS, "kind": "result"},
    {"path": ANALYSIS_OUTPUT_SUMMARY, "kind": "result"},
    {"path": ANALYSIS_OUTPUT_PROCESSED_CSV, "kind": "result"},
    {"path": ANALYSIS_OUTPUT_PLOT_PNG, "kind": "artifact"},
    {"path": ANALYSIS_OUTPUT_NOTE_TXT, "kind": "result"},
)

ANALYSIS_IMAGE_TAG = "nexus-python-analysis:1.0.0"
ANALYSIS_PYTHON_VERSION = "3.13"
ANALYSIS_NUMPY_VERSION = "2.2.3"
ANALYSIS_PANDAS_VERSION = "2.2.3"
ANALYSIS_MATPLOTLIB_VERSION = "3.10.0"

_STUB_SCRIPT = Path(__file__).resolve().parent / "analysis_stub.py"


def _use_analysis_stub() -> bool:
    raw = os.environ.get("NEXUS_ANALYSIS_USE_STUB", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def build_analysis_command_spec() -> dict[str, Any]:
    """Build a validated ExecutionCommandSpec for analysis.run."""
    if _use_analysis_stub():
        executable = "python3"
        arguments = [str(_STUB_SCRIPT)]
    else:
        executable = "python3"
        arguments = [ANALYSIS_ENTRYPOINT]

    env_entries: list[dict[str, str]] = [
        {"name": "NEXUS_ANALYSIS_PROFILE", "value": "python-analysis-v1"},
    ]
    stub_delay = os.environ.get("NEXUS_ANALYSIS_STUB_DELAY_MS", "").strip()
    if stub_delay and _use_analysis_stub():
        env_entries.append({"name": "NEXUS_ANALYSIS_STUB_DELAY_MS", "value": stub_delay})

    spec: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "executable": executable,
        "arguments": arguments,
        "workingDirectory": "",
        "environment": env_entries,
        "declaredOutputs": [dict(item) for item in ANALYSIS_DECLARED_OUTPUTS],
    }
    return validate_command_spec(spec)


def analysis_toolchain_profile() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "executionMode": "fixture" if _use_analysis_stub() else "python",
        "profileId": "python-analysis-v1",
        "profileVersion": "1.0.0",
        "language": "python",
        "entrypoint": ANALYSIS_ENTRYPOINT,
        "outputDir": ANALYSIS_OUTPUT_DIR,
        "imageTag": ANALYSIS_IMAGE_TAG,
        "pinnedPackages": {
            "python": ANALYSIS_PYTHON_VERSION,
            "numpy": ANALYSIS_NUMPY_VERSION,
            "pandas": ANALYSIS_PANDAS_VERSION,
            "matplotlib": ANALYSIS_MATPLOTLIB_VERSION,
        },
        "networkPolicy": "none",
        "declaredRunOutputs": [
            {
                "path": item["path"],
                "kind": item["kind"],
                "logicalName": Path(item["path"]).name,
            }
            for item in ANALYSIS_DECLARED_OUTPUTS
        ],
    }


def validate_analysis_snapshot_for_run(
    snapshot: dict[str, Any],
    *,
    file_store: Any,
) -> None:
    """Application-side validation before starting analysis.run."""
    _ = file_store  # reserved for future content checks
    manifest = snapshot_manifest_index(snapshot)
    if ANALYSIS_ENTRYPOINT not in manifest:
        raise CommandValidationError(f"Snapshot missing required file: {ANALYSIS_ENTRYPOINT}")


def compare_produced_output_hashes(
    baseline_outputs: list[dict[str, Any]],
    rerun_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare ProducedOutput content hashes between a baseline run and a rerun.

    Returns per-name comparison rows with status match | different | not-comparable.
    """

    def _digest(item: dict[str, Any]) -> str | None:
        content = item.get("content") or {}
        if isinstance(content, dict):
            digest = content.get("contentDigest") or content.get("contentHash")
            if isinstance(digest, str) and digest:
                return digest
        for key in ("contentDigest", "contentHash"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    baseline_by_name: dict[str, dict[str, Any]] = {}
    for item in baseline_outputs:
        name = str(item.get("name") or item.get("outputId") or "")
        if name:
            baseline_by_name[name] = item

    rerun_by_name: dict[str, dict[str, Any]] = {}
    for item in rerun_outputs:
        name = str(item.get("name") or item.get("outputId") or "")
        if name:
            rerun_by_name[name] = item

    names = sorted(set(baseline_by_name) | set(rerun_by_name))
    rows: list[dict[str, Any]] = []
    for name in names:
        left = baseline_by_name.get(name)
        right = rerun_by_name.get(name)
        if left is None or right is None:
            rows.append(
                {
                    "name": name,
                    "status": "not-comparable",
                    "baselineDigest": _digest(left) if left else None,
                    "rerunDigest": _digest(right) if right else None,
                }
            )
            continue
        left_digest = _digest(left)
        right_digest = _digest(right)
        if left_digest is None or right_digest is None:
            status = "not-comparable"
        elif left_digest == right_digest:
            status = "match"
        else:
            status = "different"
        rows.append(
            {
                "name": name,
                "status": status,
                "baselineDigest": left_digest,
                "rerunDigest": right_digest,
                "baselineOutputId": left.get("outputId"),
                "rerunOutputId": right.get("outputId"),
            }
        )
    return rows
