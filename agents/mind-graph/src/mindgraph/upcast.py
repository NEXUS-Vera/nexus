"""Read-time schema migration. Backend/07 §2.

Stored events are NEVER rewritten — the hash chain is computed over the stored
bytes, so editing one breaks tamper evidence for everything after it. Instead
old payloads are upcast on read, by a chain of pure functions.

Rules:
  * upcasters are append-only; you add one, you never edit one
  * each is pure — same input, same output, forever
  * a golden ledger per schema version is frozen in tests/golden/, and CI
    asserts each still projects to its recorded state_hash
"""

from __future__ import annotations

from collections.abc import Callable

from .schema import SCHEMA_VERSION

# version -> function turning a vN payload into a v(N+1) payload
UPCASTERS: dict[int, Callable[[dict], dict]] = {}


def register(from_version: int):
    def deco(fn):
        if from_version in UPCASTERS:
            raise RuntimeError(f"upcaster for v{from_version} already registered")
        UPCASTERS[from_version] = fn
        return fn

    return deco


def upcast(payload: dict, version: int) -> dict:
    if version > SCHEMA_VERSION:
        raise ValueError(f"event schema v{version} is newer than this code (v{SCHEMA_VERSION})")
    while version < SCHEMA_VERSION:
        fn = UPCASTERS.get(version)
        if fn is None:
            raise ValueError(f"no upcaster from schema v{version}")
        payload = fn(payload)
        version += 1
    return payload


@register(1)
def _v1_to_v2(payload: dict) -> dict:
    """v1 -> v2: edges gain `weight_source_nodes`.

    ⭐ The first real upcaster, and the proof the mechanism works. v1 recorded
    only `weight_sources` (event seqs), but independence is a property of WHO
    asserted a link, not of when — so `independent_weight()` needs source
    NODES. A v1 edge has no such record, and the only honest reconstruction is
    the edge's own `src`: it is exactly one asserter, which is what a v1 edge
    always was before re-assertion existed.

    ⚠️ Note what this does NOT do: it does not invent multiple asserters to
    make old edges look better-evidenced than they were. An upcaster that
    improves the past is worse than no upcaster, because every downstream
    number silently shifts.
    """
    out = dict(payload)
    edges = []
    for e in out.get("edges", []):
        e = dict(e)
        if "weight_source_nodes" not in e and e.get("src"):
            e["weight_source_nodes"] = [e["src"]]
        edges.append(e)
    if edges:
        out["edges"] = edges
    return out
