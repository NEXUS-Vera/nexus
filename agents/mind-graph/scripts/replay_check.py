#!/usr/bin/env python3
"""CI gate. Backend/02 §7.

Nightly, over every user ledger: rebuild from zero, compare `state_hash` to the
stored snapshot, verify the hash chain, and replay the golden fixtures for every
schema version.

⚠️ Any divergence without a corresponding upcaster is a P0 — it means the
projector changed behaviour, and every downstream number is suspect.

    python3 scripts/replay_check.py [users_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mindgraph import snapshot                                    # noqa: E402
from mindgraph.ledger import Ledger                               # noqa: E402
from mindgraph.projector import project, state_hash               # noqa: E402

GOLDEN = ROOT / "tests" / "golden"


def check_ledger(path: Path) -> list[str]:
    problems: list[str] = []
    led = Ledger(path)
    try:
        if not led.verify_chain():
            problems.append(f"{path}: HASH CHAIN BROKEN — the log was edited")
        rebuilt = project(led.read())
        snap = path.parent / "graph.snapshot"
        if snap.exists():
            stored = snapshot.load(snap)
            if state_hash(stored) != state_hash(rebuilt):
                problems.append(
                    f"{path}: snapshot disagrees with a full replay "
                    f"(snapshot {state_hash(stored)[:12]} vs "
                    f"replay {state_hash(rebuilt)[:12]})")
    finally:
        led.close()
    return problems


def check_golden() -> list[str]:
    """Every frozen ledger must still project to its recorded hash."""
    problems: list[str] = []
    manifest = GOLDEN / "manifest.json"
    if not manifest.exists():
        return [f"{manifest}: missing — golden fixtures are the upcaster's only proof"]
    for name, expected in sorted(json.loads(manifest.read_text()).items()):
        db = GOLDEN / name
        if not db.exists():
            problems.append(f"{db}: listed in manifest but absent")
            continue
        led = Ledger(db)
        try:
            got = state_hash(project(led.read()))
            if got != expected:
                problems.append(
                    f"{name}: PROJECTOR BEHAVIOUR CHANGED — expected "
                    f"{expected[:12]}, got {got[:12]}. Add an upcaster or "
                    f"revert; do not update this hash to make CI green.")
        finally:
            led.close()
    return problems


def main(argv: list[str]) -> int:
    problems = check_golden()
    users = Path(argv[1]) if len(argv) > 1 else ROOT / "users"
    if users.exists():
        for led_path in sorted(users.glob("*/ledger.db")):
            problems.extend(check_ledger(led_path))

    if problems:
        print("REPLAY CHECK FAILED\n")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("replay check: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
