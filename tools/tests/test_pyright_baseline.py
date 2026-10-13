"""Repository typecheck gate regression tests."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/pyright-baseline.py"
spec = importlib.util.spec_from_file_location("pyright_baseline", SCRIPT)
assert spec is not None and spec.loader is not None
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def test_normalization_ignores_locations_and_warnings(tmp_path):
    diagnostic = {
        "file": str(tmp_path / "example.py"),
        "severity": "error",
        "rule": "reportAssignmentType",
        "message": "Cannot assign str to int",
        "range": {"start": {"line": 1, "character": 0}},
    }
    original = baseline.normalize_errors([diagnostic], tmp_path)
    diagnostic["range"]["start"]["line"] = 99
    assert baseline.normalize_errors([diagnostic], tmp_path) == original
    diagnostic["severity"] = "warning"
    assert baseline.normalize_errors([diagnostic], tmp_path) == []


def test_comparison_detects_new_and_duplicate_errors_and_allows_removals():
    known = ("example.py", "reportAssignmentType", "Cannot assign str to int")
    added = ("example.py", "reportAssignmentType", "Cannot assign float to int")
    counts = baseline.error_counts([known])
    assert counts == {"example.py::reportAssignmentType": 1}
    assert baseline.new_errors([known], counts) == []
    assert baseline.new_errors([added], counts) == []  # Message changes are harmless.
    assert baseline.new_errors([], counts) == []
    assert baseline.new_errors([known, added], counts) == sorted([known, added])
    assert baseline.new_errors([known, known], counts) == [known, known]
    assert baseline.new_errors([("other.py", *known[1:])], counts)
    assert baseline.new_errors([(known[0], "otherRule", known[2])], counts)
    assert baseline.new_errors([known], baseline.error_counts([known, known])) == []


def test_counts_are_sorted_and_preserve_multiplicity():
    errors = [("z.py", "rule", "one"), ("a.py", "", "two"), ("z.py", "rule", "three")]
    counts = baseline.error_counts(errors)
    assert list(counts) == ["a.py::", "z.py::rule"]
    assert counts == {"a.py::": 1, "z.py::rule": 2}


def test_gate_passes_baseline_and_fails_injected_error(tmp_path, monkeypatch, capsys):
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text('{"example.py::reportAssignmentType": 1}\n')
    monkeypatch.setattr(baseline, "BASELINE", baseline_file)
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", [str(SCRIPT), "example.py"])
    diagnostic = {
        "file": str(tmp_path / "example.py"),
        "severity": "error",
        "rule": "reportAssignmentType",
        "message": "Incompatible assignment",
    }
    diagnostics = [diagnostic]

    def run_pyright(*args, **kwargs):
        assert args[0] == ["pyright", "--outputjson", "example.py"]
        return SimpleNamespace(
            returncode=1,
            stdout=json.dumps(
                {"generalDiagnostics": diagnostics, "summary": {"errorCount": len(diagnostics)}}
            ),
            stderr="",
        )

    monkeypatch.setattr(baseline.subprocess, "run", run_pyright)
    assert baseline.main() == 0
    diagnostics.append(dict(diagnostic, message="Injected type error"))
    assert baseline.main() == 1
    assert "Injected type error" in capsys.readouterr().err
