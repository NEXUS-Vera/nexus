"""Auth, tenancy, backup and restore. Backend/07 §4.

    users/{user_id}/
    ├── ledger.db        append-only, hash-chained   ← the ONLY thing that matters
    ├── graph.snapshot   derived — regenerable, never authoritative
    ├── sidecars/        salience, communities, centrality
    └── blobs/           encrypted bodies
    keys.json            ⚠️ OUTSIDE the data directory

Tenancy isolation is a filesystem property plus a path check. Boring,
auditable, and it makes per-user backup and per-user deletion trivial.

⭐ Restore = REPLAY, not snapshot restoration. A restored snapshot could
disagree with the ledger; a replayed one cannot.
"""

from __future__ import annotations

import os
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path

from .crypto import KeyStore
from .errors import MindGraphError
from .ledger import Ledger
from .projector import project, state_hash

USER_RE = __import__("re").compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
RESIDENT_CAP_MB = 250  # measured 144-240 MB per live graph (Q11)


class TenancyError(MindGraphError):
    pass


def user_dir(root: str | Path, user: str) -> Path:
    """⚠️ The path check IS the isolation. A user id that escapes its directory
    reads someone else's ledger, so this is validated before any I/O."""
    if not USER_RE.match(user or ""):
        raise TenancyError(f"illegal user id {user!r}")
    base = Path(root).resolve()
    d = (base / user).resolve()
    if not str(d).startswith(str(base) + os.sep):
        raise TenancyError(f"path escape attempt: {user!r}")
    return d


def keystore(root: str | Path) -> KeyStore:
    """Keys live OUTSIDE the data directory, and are never in a user folder."""
    return KeyStore(Path(root) / "keys.json")


def provision(root: str | Path, user: str) -> Path:
    d = user_dir(root, user)
    (d / "sidecars").mkdir(parents=True, exist_ok=True)
    (d / "blobs").mkdir(parents=True, exist_ok=True)
    keystore(root).create(user)
    Ledger(d / "ledger.db").close()
    return d


# ── backup and restore ──────────────────────────────────────────────────────


def backup(root: str | Path, user: str, dest: str | Path) -> Path:
    """⭐ Backs up the LEDGER only. Snapshots and sidecars are deliberately
    excluded — they are recomputable, and including them invites restoring one
    that disagrees with the log."""
    d = user_dir(root, user)
    dest = Path(dest)
    with tarfile.open(dest, "w:gz") as t:
        t.add(d / "ledger.db", arcname="ledger.db")
        if (d / "blobs").exists():
            t.add(d / "blobs", arcname="blobs")
    return dest


def restore(root: str | Path, user: str, archive: str | Path) -> str:
    """Restore by REPLAY. Returns the rebuilt state hash."""
    d = user_dir(root, user)
    d.mkdir(parents=True, exist_ok=True)
    for stale in ("graph.snapshot",):
        (d / stale).unlink(missing_ok=True)
    shutil.rmtree(d / "sidecars", ignore_errors=True)
    with tarfile.open(archive, "r:gz") as t:
        t.extractall(d, filter="data")
    led = Ledger(d / "ledger.db")
    try:
        if not led.verify_chain():
            raise TenancyError("restored ledger fails its hash chain")
        return state_hash(project(led.read()))
    finally:
        led.close()


def verify_key_separation(root: str | Path, archive: str | Path) -> bool:
    """⚠️ The rule that makes or breaks crypto-shredding.

    If one restore can recover both the data and the key, erasure is defeated
    by your own disaster recovery and the guarantee was fictional all along.
    So: assert no archive ever contains the keystore.
    """
    with tarfile.open(archive, "r:gz") as t:
        names = {Path(n).name for n in t.getnames()}
    return "keys.json" not in names


# ── concurrency: the constraint the load test actually found ───────────────


@dataclass
class _Live:
    state: object
    last_used: int


class GraphCache:
    """LRU over in-process graphs. Backend/07 §4.6.

    ⭐ CPU was never the limit — memory was. A live graph costs 144-240 MB, so
    ten concurrent students is ~2.4 GB, and the design said "one graph per
    user, in memory" without ever asking how many fit at once.

    Eviction is free because a full 60k-event replay is 122 ms: drop the graph,
    rebuild on the next request. The property that makes the storage choice
    reversible is the same one that makes it multi-tenant.
    """

    def __init__(self, root: str | Path, capacity: int = 8) -> None:
        self.root = Path(root)
        self.capacity = capacity
        self._live: dict[str, _Live] = {}
        self._tick = 0
        self.evictions = 0
        self.rebuilds = 0

    def get(self, user: str):
        self._tick += 1
        if (hit := self._live.get(user)) is not None:
            hit.last_used = self._tick
            return hit.state
        led = Ledger(user_dir(self.root, user) / "ledger.db")
        try:
            state = project(led.read())
        finally:
            led.close()
        self.rebuilds += 1
        self._live[user] = _Live(state, self._tick)
        self._evict()
        return state

    def _evict(self) -> None:
        while len(self._live) > self.capacity:
            victim = min(self._live, key=lambda u: self._live[u].last_used)
            del self._live[victim]
            self.evictions += 1

    def drop(self, user: str) -> None:
        self._live.pop(user, None)

    @property
    def resident(self) -> int:
        return len(self._live)


# ── erasure ────────────────────────────────────────────────────────────────


def erase(root: str | Path, user: str) -> None:
    """GDPR Art. 17. Destroy the key, then record that it happened.

    The ledger stays: its structural half is not personal data, and the
    aggregate outcome signal it carries outlives the request.
    """
    from .events import EventType

    keystore(root).destroy(user)
    led = Ledger(user_dir(root, user) / "ledger.db")
    try:
        led.append("system", EventType.SHREDDED, {"user": user})
    finally:
        led.close()


def health(root: str | Path) -> dict:
    base = Path(root)
    users = sorted(p.name for p in base.glob("*/ledger.db") for p in [p.parent])
    ks = keystore(root)
    return {
        "users": len(users),
        "keys_outside_data_dir": (base / "keys.json").exists(),
        "shredded": [u for u in users if not ks.exists(u)],
    }
