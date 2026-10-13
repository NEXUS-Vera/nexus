"""Entity resolution. Backend/01 §5.3, Backend/09 Q4.

The commonest way knowledge graphs rot is one thing appearing as five nodes:
I2C, I²C, IIC, TWI, Inter-Integrated Circuit.

    MinHash / LSH blocking     cuts millions of comparisons to thousands
    similarity scoring         a match probability
    >=0.95   merge into one node
    0.70-0.95  ⭐ `same_as` edge — BOTH nodes survive
    <0.70    leave them alone

⭐ The middle band is the important one. A wrong merge is node surgery to undo;
a wrong `same_as` edge is one deletion. When unsure, prefer the mistake that is
cheap to reverse.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict

from .schema import MERGE_HARD, MERGE_SOFT

_PERM = [(1 + 2 * i, 7 + 13 * i) for i in range(64)]
_MASK = (1 << 32) - 1
_STRIP = re.compile(r"[^a-z0-9 ]+")


def normalise(text: str) -> str:
    """Fold the surface forms that mean nothing: case, accents, punctuation.

    I²C -> i2c, so the cheap exact path catches most of the work before any
    statistics are involved.
    """
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("²", "2").replace("³", "3")
    return " ".join(_STRIP.sub(" ", t).split())


def trigrams(text: str) -> set[str]:
    t = f"  {normalise(text)}  "
    return {t[i : i + 3] for i in range(len(t) - 2)} or {t}


def minhash(text: str) -> tuple[int, ...]:
    grams = trigrams(text)
    base = [int(hashlib.blake2b(g.encode(), digest_size=4).hexdigest(), 16) for g in sorted(grams)]
    return tuple(min(((a * h + b) & _MASK) for h in base) for a, b in _PERM)


def jaccard(a: str, b: str) -> float:
    ga, gb = trigrams(a), trigrams(b)
    return len(ga & gb) / len(ga | gb) if (ga | gb) else 0.0


def similarity(a: str, b: str, a_aliases=(), b_aliases=()) -> float:
    """1.0 on an exact normalised match or a shared alias; Jaccard otherwise."""
    na, nb = normalise(a), normalise(b)
    if na == nb:
        return 1.0
    sa = {normalise(x) for x in (*a_aliases, a)}
    sb = {normalise(x) for x in (*b_aliases, b)}
    if sa & sb:
        return 1.0
    return round(jaccard(a, b), 4)


def block(labels: dict[str, str], bands: int = 16) -> list[tuple[str, str]]:
    """LSH blocking. Returns candidate pairs only — the cheap half of the job.

    Without this, resolution is O(n²) comparisons; with it, near-duplicates
    land in the same bucket and everything else is never compared at all.
    """
    rows = len(_PERM) // bands
    buckets: dict[tuple, set[str]] = defaultdict(set)
    sigs = {k: minhash(v) for k, v in labels.items()}
    for key, sig in sigs.items():
        for b in range(bands):
            buckets[(b, sig[b * rows : (b + 1) * rows])].add(key)
    pairs: set[tuple[str, str]] = set()
    for members in buckets.values():
        if len(members) > 1:
            ms = sorted(members)
            pairs.update((a, b) for i, a in enumerate(ms) for b in ms[i + 1 :])
    return sorted(pairs)


def band_for(score: float) -> str:
    if score >= MERGE_HARD:
        return "merge"
    if score >= MERGE_SOFT:
        return "same_as"
    return "distinct"


def resolve_candidates(
    labels: dict[str, str], aliases: dict[str, list[str]] | None = None
) -> list[dict]:
    """Score every blocked pair and assign it a band."""
    aliases = aliases or {}
    out = []
    for a, b in block(labels):
        s = similarity(labels[a], labels[b], aliases.get(a, ()), aliases.get(b, ()))
        band = band_for(s)
        if band != "distinct":
            out.append({"a": a, "b": b, "score": s, "band": band})
    return sorted(out, key=lambda d: (-d["score"], d["a"], d["b"]))
