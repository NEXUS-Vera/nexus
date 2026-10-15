"""Deterministic contract type generation checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "packages" / "contracts" / "scripts" / "generate_contract_types.py"
GENERATED_PY = ROOT / "packages" / "contracts" / "generated" / "python"
GENERATED_TS = ROOT / "packages" / "contracts" / "generated" / "typescript"


def _run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_generate_is_deterministic_and_includes_notices() -> None:
    before_py = _file_map(GENERATED_PY)
    before_ts = _file_map(GENERATED_TS)
    completed = _run_generator()
    assert completed.returncode == 0, completed.stderr
    after_py = _file_map(GENERATED_PY)
    after_ts = _file_map(GENERATED_TS)
    assert before_py == after_py
    assert before_ts == after_ts

    py_sample = next(GENERATED_PY.glob("*.py"))
    ts_sample = next(GENERATED_TS.glob("*.ts"))
    assert "Do not edit manually" in py_sample.read_text(encoding="utf-8")
    assert "Do not edit manually" in ts_sample.read_text(encoding="utf-8")
    assert "[k: string]: any" not in (GENERATED_TS / "artifact_v1.ts").read_text(encoding="utf-8")


def test_stale_generated_output_fails_check_and_restores() -> None:
    target = GENERATED_TS / "artifact_v1.ts"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n// stale marker\n")
        completed = _run_generator("--check")
        assert completed.returncode != 0
        assert "stale" in completed.stderr.lower() or "stale" in completed.stdout.lower()
    finally:
        target.write_bytes(original)
