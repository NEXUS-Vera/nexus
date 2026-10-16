#!/usr/bin/env python3
"""Gate Pyright errors against a reviewed baseline, independent of line numbers."""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts/pyright-baseline.json"
Signature = tuple[str, str, str]


def normalize_errors(diagnostics: list[dict], root: Path) -> list[Signature]:
    return [
        (
            Path(item["file"]).resolve().relative_to(root).as_posix(),
            item.get("rule", ""),
            item["message"],
        )
        for item in diagnostics
        if item["severity"] == "error"
    ]


def error_counts(current: list[Signature]) -> dict[str, int]:
    return dict(sorted(Counter(f"{file}::{rule}" for file, rule, _ in current).items()))


def new_errors(current: list[Signature], baseline: dict[str, int]) -> list[Signature]:
    """Report current diagnostics for keys whose error count increased."""
    increased = {
        key for key, count in error_counts(current).items() if count > baseline.get(key, 0)
    }
    return sorted(item for item in current if f"{item[0]}::{item[1]}" in increased)


def python_files() -> list[str]:
    return sorted(
        path.relative_to(ROOT).as_posix()
        for directory in ("agents", "apps", "packages", "tools", "scripts")
        for path in (ROOT / directory).rglob("*.py")
        if not {"generated", ".venv", "node_modules"}.intersection(path.parts)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="regenerate the reviewed baseline")
    parser.add_argument(
        "files", nargs="*", help="Python files (defaults to run-typecheck.sh scope)"
    )
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["pyright", "--outputjson", *(args.files or python_files())],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise ValueError(f"Pyright exited {result.returncode}: {result.stderr.strip()}")
        report = json.loads(result.stdout)
        current = normalize_errors(report["generalDiagnostics"], ROOT)
        if report["summary"]["errorCount"] != len(current):
            raise ValueError("Pyright error count does not match diagnostics")
        if result.returncode == 1 and not current:
            raise ValueError("Pyright failed without error diagnostics")
        if args.update:
            BASELINE.write_text(json.dumps(error_counts(current), indent=2) + "\n")
            print(f"typecheck: baseline updated ({len(current)} errors)")
            return 0
        baseline = json.loads(BASELINE.read_text())
        if not isinstance(baseline, dict) or any(
            not isinstance(key, str) or type(count) is not int or count < 0
            for key, count in baseline.items()
        ):
            raise ValueError("Baseline must be an object mapping file::rule to error counts")
        added = new_errors(current, baseline)
        for file, rule, message in added:
            print(f"{file}: {rule or 'error'}: {message}", file=sys.stderr)
        print(f"typecheck: {len(current)} errors, {len(added)} diagnostics for increased keys")
        return 1 if added else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"typecheck: baseline check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
