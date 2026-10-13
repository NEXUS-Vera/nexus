"""Per-operation instrumentation. Backend/02 §8.

Nobody in this field has published real cost or curation data (Research/06
§1.1). This table is how we get to be the ones who can — so it goes in from
day one rather than being added once the numbers would be interesting.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ops (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    op_type  TEXT NOT NULL,
    wall_ms  INTEGER NOT NULL,
    cpu_ms   INTEGER NOT NULL,
    tags     TEXT NOT NULL
);
"""


_DEFAULT: CostLog | None = None


def default() -> CostLog:
    """Process-wide sink so instrumentation is opt-out, not opt-in.

    ⚠️ Nobody in this field has published real cost or curation data, and the
    reason is always the same: the table gets added once the numbers would
    have been interesting. It goes in on day one or it never goes in.
    """
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = CostLog()
    return _DEFAULT


def use(path) -> CostLog:
    """Open a file-backed log.

    ⚠️ An in-memory log looks like it is working and records nothing that
    survives the process — for a CLI, every row is discarded the instant it is
    written. The whole point is a table that accumulates.

    ⚠️⚠️ This deliberately does NOT set a process-wide sink any more. Pinning a
    global to one user's directory means operating on user B after opening user
    A writes B's rows into A's file — a tenancy leak in the one table meant to
    prove we can measure ourselves. Ownership belongs to the Session.
    """
    return CostLog(path)


def for_session(s) -> CostLog:
    """The session's own log, or the process default when there is no session."""
    return getattr(s, "costs", None) or default()


class CostLog:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA_SQL)

    def write(self, rec: dict) -> None:
        tags = {k: v for k, v in rec.items()
                if k not in ("op_type", "wall_ms", "cpu_ms")}
        with self.db:
            self.db.execute(
                "INSERT INTO ops (op_type, wall_ms, cpu_ms, tags) VALUES (?,?,?,?)",
                (rec["op_type"], rec["wall_ms"], rec["cpu_ms"],
                 json.dumps(tags, sort_keys=True)))

    def rows(self) -> list[tuple]:
        return self.db.execute(
            "SELECT op_type, wall_ms, cpu_ms, tags FROM ops ORDER BY id").fetchall()

    @contextmanager
    def measure(self, op_type: str, **tags):
        t0, c0 = time.perf_counter(), time.process_time()
        rec = {"op_type": op_type, **tags}
        try:
            yield rec
        finally:
            rec["wall_ms"] = int((time.perf_counter() - t0) * 1000)
            rec["cpu_ms"] = int((time.process_time() - c0) * 1000)
            self.write(rec)
