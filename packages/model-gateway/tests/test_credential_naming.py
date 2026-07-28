"""Regression: credential field names must not trip secret-pattern scans."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_secret_pattern_scan_passes_on_tracked_tree() -> None:
    script = ROOT / "scripts" / "scan-secret-patterns.sh"
    completed = subprocess.run(
        ["bash", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "No high-risk secret patterns" in completed.stdout


def test_openai_gateway_accepts_model_credential_field() -> None:
    from nexus_model_gateway import OpenAICompatibleGateway

    gateway = OpenAICompatibleGateway(model_credential="")
    assert gateway.model_credential == ""
    # Ensure the old matching field name is not present on the dataclass.
    assert "model_credential" in gateway.__dataclass_fields__
    assert all("key" not in name for name in gateway.__dataclass_fields__)
