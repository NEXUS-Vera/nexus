"""Hermetic tests for Phase 16H reactive spike harness."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPIKE_DIR = Path(__file__).resolve().parent
_MODULE_NAME = "nexus_board_analysis_reactive_spike"
_SPEC = importlib.util.spec_from_file_location(
    _MODULE_NAME,
    _SPIKE_DIR / "run_spike.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_SPIKE = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _SPIKE
_SPEC.loader.exec_module(_SPIKE)
main = _SPIKE.main
run_stateless_explore = _SPIKE.run_stateless_explore


def test_stateless_explore_closure_for_c() -> None:
    result = run_stateless_explore("C")
    assert result["cellsMaterialized"] == ["A", "B", "C"]
    assert result["ephemeral"] is True
    assert result["durableHistory"] is False
    assert result["result"]["rms"] < 0.10


def test_spike_main_writes_recommendation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_SPIKE, "REPORT_PATH", tmp_path / "spike_report.json")
    report = main()
    assert report["recommendation"]["runtime"] == "R1"
    assert report["recommendation"]["cells"] is True
    assert report["recommendation"]["reactivity"] is False
    assert report["marimo"]["M1_fileFormat"]["status"] in {"pass", "gap"}
