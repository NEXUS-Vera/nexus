"""Deterministic Analysis scaffold profiles (Phase 16B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexus_persistence.file_store.hashing import blob_digest

ANALYSIS_PYTHON_V1_PROFILE_ID = "python-analysis-v1"
ANALYSIS_PYTHON_V1_PROFILE_VERSION = "1.0.0"

OUTPUT_RESULTS_PATH = "outputs/results.json"
DATA_DIR = "data"

ANALYSIS_PYTHON_V1_ANALYSIS_PY_BYTES = b"""import json
import pathlib


def main() -> None:
    # Deterministic scaffold runtime: create outputs/results.json.
    out_dir = pathlib.Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"status": "ok"}
    out_path = out_dir / "results.json"
    # Stable formatting (no timestamps).
    out_path.write_text(json.dumps(results, sort_keys=True, indent=2) + "\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
"""

ANALYSIS_PYTHON_V1_README_BYTES = b"""# Analysis Workspace

This workspace is deterministic and scaffolded by Nexus.

## Inputs

Place user-provided input files under `data/`.

## Execution outputs

Execution writes produced outputs under `outputs/`.

## Entrypoint

The analysis entrypoint is `analysis.py`.
"""


@dataclass(frozen=True)
class ScaffoldFileSpec:
    path: str
    content: bytes
    media_type: str

    @property
    def content_hash(self) -> str:
        return blob_digest(self.content)


@dataclass(frozen=True)
class AnalysisScaffoldProfile:
    profile_id: str
    profile_version: str
    display_name: str
    language: str
    entrypoint: str
    files: tuple[ScaffoldFileSpec, ...]

    @property
    def generated_from(self) -> str:
        return f"{self.profile_id}@{self.profile_version}"

    def target_paths(self) -> tuple[str, ...]:
        return tuple(spec.path for spec in self.files)

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "displayName": self.display_name,
            "language": self.language,
            "entrypoint": self.entrypoint,
            "targetPaths": list(self.target_paths()),
            "generatedFrom": self.generated_from,
        }


ANALYSIS_PYTHON_V1_PROFILE = AnalysisScaffoldProfile(
    profile_id=ANALYSIS_PYTHON_V1_PROFILE_ID,
    profile_version=ANALYSIS_PYTHON_V1_PROFILE_VERSION,
    display_name="Python Analysis · v1",
    language="python",
    entrypoint="analysis.py",
    files=(
        ScaffoldFileSpec(
            path="analysis.py",
            content=ANALYSIS_PYTHON_V1_ANALYSIS_PY_BYTES,
            media_type="text/x-python",
        ),
        ScaffoldFileSpec(
            path="README.md",
            content=ANALYSIS_PYTHON_V1_README_BYTES,
            media_type="text/markdown",
        ),
    ),
)

_PROFILES: dict[str, AnalysisScaffoldProfile] = {
    ANALYSIS_PYTHON_V1_PROFILE_ID: ANALYSIS_PYTHON_V1_PROFILE,
}

DEFAULT_ANALYSIS_SCAFFOLD_PROFILE_ID = ANALYSIS_PYTHON_V1_PROFILE_ID


def get_analysis_scaffold_profile(
    profile_id: str | None = None,
) -> AnalysisScaffoldProfile:
    key = profile_id or DEFAULT_ANALYSIS_SCAFFOLD_PROFILE_ID
    profile = _PROFILES.get(key)
    if profile is None:
        raise KeyError(f"Unknown analysis scaffold profile: {key}")
    return profile


def materialize_analysis_scaffold_files(
    profile_id: str | None = None,
) -> list[dict[str, Any]]:
    profile = get_analysis_scaffold_profile(profile_id)
    return [
        {
            "path": spec.path,
            "content": spec.content,
            "contentHash": spec.content_hash,
            "mediaType": spec.media_type,
            "sizeBytes": len(spec.content),
        }
        for spec in profile.files
    ]
