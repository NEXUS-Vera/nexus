"""Embedding storage. Backend/01 §10.

A sidecar: derived, disposable, recomputable. Deleting it costs an embedding
backfill, never data — so it lives beside the graph snapshot and is never
backed up.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors (
    node_id TEXT PRIMARY KEY,
    model   TEXT NOT NULL,
    dim     INTEGER NOT NULL,
    vec     TEXT NOT NULL
);
"""


class VectorStore:
    """Brute-force cosine over a per-user file.

    ⚠️ Deliberately not an ANN index. At 10^3-10^4 nodes a linear scan is
    microseconds and the graph is already ~100x off the critical path
    (Backend/09 Q11) — an index here is complexity bought with nothing.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def put(self, node_id: str, vec: list[float], model: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)",
                (node_id, model, len(vec), json.dumps(vec)),
            )

    def all(self) -> dict[str, list[float]]:
        return {
            nid: json.loads(v)
            for nid, v in self.db.execute("SELECT node_id, vec FROM vectors ORDER BY node_id")
        }

    def missing(self, node_ids) -> list[str]:
        have = {r[0] for r in self.db.execute("SELECT node_id FROM vectors")}
        return sorted(set(node_ids) - have)

    def backfill(self, labels: dict, embedder, model: str = "") -> int:
        """⭐ Async by design — a partial backfill degrades retrieval QUALITY
        and never correctness, because the lexical seed always runs."""
        done = 0
        for nid in self.missing(sorted(labels)):
            if not labels.get(nid):
                continue
            self.put(
                nid, embedder.embed(labels[nid]), model or getattr(embedder, "model", "unknown")
            )
            done += 1
        return done

    def close(self) -> None:
        self.db.close()
