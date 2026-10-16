"""The append-only store and its hash chain. Backend/02 §4.

This is the asset. The graph is a view over it and can be thrown away; this
cannot. Three properties matter:

  * tamper evidence  — verify_chain() detects any edit or reorder
  * `seq` is the ONLY ordering — never sort by `ts`, clocks lie
  * the clock is injected — so tests are byte-stable
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from .events import Event, EventType
from .schema import SCHEMA_VERSION

GENESIS = "0" * 64

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    seq            INTEGER PRIMARY KEY,
    ts             TEXT NOT NULL,
    actor          TEXT NOT NULL,
    type           TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    structural     TEXT NOT NULL,
    content        BLOB,
    caused_by      INTEGER,
    prev_hash      TEXT NOT NULL,
    hash           TEXT NOT NULL
);
"""


def canonical(obj) -> str:
    """Byte-stable JSON. Sorted keys, no whitespace, no NaN.

    Every hash in the system is taken over this, so any change to it
    invalidates every stored hash. Don't.
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def event_hash(
    prev: str,
    seq: int,
    ts: str,
    actor: str,
    etype,
    ver: int,
    structural: dict,
    content: bytes | None,
) -> str:
    h = hashlib.sha256()
    h.update(prev.encode())
    h.update(f"{seq}|{ts}|{actor}|{etype}|{ver}|".encode())
    h.update(canonical(structural).encode())
    h.update(hashlib.sha256(content).hexdigest().encode() if content else b"-")
    return h.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Ledger:
    def __init__(
        self, path: str | Path = ":memory:", clock: Callable[[], str] | None = None
    ) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SCHEMA_SQL)
        self._clock = clock or _utc_now

    def head(self) -> tuple[int, str]:
        row = self.db.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        return row if row else (0, GENESIS)

    def append(
        self,
        actor: str,
        etype: EventType,
        structural: dict,
        content: bytes | None = None,
        caused_by: int | None = None,
    ) -> int:
        with self.db:  # single transaction
            prev_seq, prev_hash = self.head()
            seq, ts = prev_seq + 1, self._clock()
            h = event_hash(
                prev_hash, seq, ts, actor, str(etype), SCHEMA_VERSION, structural, content
            )
            self.db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    seq,
                    ts,
                    actor,
                    str(etype),
                    SCHEMA_VERSION,
                    canonical(structural),
                    content,
                    caused_by,
                    prev_hash,
                    h,
                ),
            )
            return seq

    def read(self, since: int = 0) -> Iterator[Event]:
        rows = self.db.execute(
            "SELECT seq, ts, actor, type, schema_version, structural, content,"
            " caused_by, prev_hash, hash FROM events WHERE seq > ? ORDER BY seq",
            (since,),
        )
        for seq, ts, actor, etype, ver, structural, content, caused_by, prev_hash, h in rows:
            yield Event(
                seq=seq,
                ts=ts,
                actor=actor,
                type=EventType(etype),
                schema_version=ver,
                structural=json.loads(structural),
                content=content,
                caused_by=caused_by,
                prev_hash=prev_hash,
                hash=h,
            )

    def verify_chain(self) -> bool:
        prev = GENESIS
        for e in self.read():
            if e.prev_hash != prev:
                return False
            if e.hash != event_hash(
                prev, e.seq, e.ts, e.actor, str(e.type), e.schema_version, e.structural, e.content
            ):
                return False
            prev = e.hash
        return True

    def close(self) -> None:
        self.db.close()
