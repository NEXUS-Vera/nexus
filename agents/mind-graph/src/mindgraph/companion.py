"""The companion — the four things a supervisor does that a chatbot cannot.

⭐ **Why this module exists at all.** In software the feedback loop closes
inside the machine: write code, run it, read the error, fix it. A language
model sits inside that loop, which is why it is so strong there. In embedded,
robotics and the life sciences the loop runs **through the physical world** —
you flash the firmware, put a scope on the pin, and the world answers. No model
is in that loop, and the record of what the world said is not on the internet.

So the defensible functions are the ones that need *that record*:

    impact()          what falls over if this turns out to be wrong
    recall_failures() you have hit this shape of problem before
    bias()            your predictions are wrong in a consistent direction
    transfer()        two of your projects have the same problem

None of these are model calls. They are graph and arithmetic over outcomes the
student produced, which is exactly why a competitor with a better model cannot
copy them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .graph import GraphState
from .schema import Relation, Support

# ── ① impact — `git blame` for beliefs ──────────────────────────────────────


@dataclass
class Impact:
    """What rests on a node, and what would lose its footing without it."""

    id: str
    direct: list[str] = field(default_factory=list)
    cascade: list[str] = field(default_factory=list)
    unsupported_after: list[str] = field(default_factory=list)
    load_bearing: bool = False


def impact(state: GraphState, node_id: str) -> Impact:
    """⭐ "What falls over if this is wrong?" — before you retract it.

    Retraction already cascades (`cascade.py`); this shows the cascade as a
    PREVIEW. ⚠️ The difference matters more than it sounds: a student who can
    see that withdrawing one sweep un-supports four claims will think about it,
    and one who finds out afterwards learns to distrust the tool instead.

    "Unsupported after" is the honest part — a conclusion that loses its last
    support is not disproved, it is **unfooted**, and the two are different
    epistemic states the ATMS is built to keep apart.
    """
    out = Impact(id=node_id)
    if node_id not in state.nodes:
        return out

    supports_of: dict[str, set[str]] = {}
    for e in state.edges.values():
        if e.relation in (Relation.SUPPORTS, Relation.MEASURED_BY):
            supports_of.setdefault(e.dst, set()).add(e.src)

    out.direct = sorted(d for d, srcs in supports_of.items() if node_id in srcs)

    # walk outward: anything left with no support becomes a new source of loss
    lost = {node_id}
    frontier_ = list(out.direct)
    seen = set(out.direct)
    while frontier_:
        nxt = []
        for nid in frontier_:
            remaining = supports_of.get(nid, set()) - lost
            if remaining:
                continue  # still standing on something
            out.unsupported_after.append(nid)
            lost.add(nid)
            for d, srcs in supports_of.items():
                if nid in srcs and d not in seen:
                    seen.add(d)
                    nxt.append(d)
        frontier_ = nxt

    out.cascade = sorted(seen - set(out.direct))
    out.unsupported_after = sorted(set(out.unsupported_after))
    # ⚠️ "load bearing" is a threshold on consequence, not on popularity. One
    # unfooted conclusion is worth a warning; ten citations that all survive
    # are not.
    out.load_bearing = len(out.unsupported_after) > 0
    return out


# ── ② recall — the immune-memory move ───────────────────────────────────────

_WORD = re.compile(r"[a-z0-9]+")
_NOISE = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "and",
        "or",
        "is",
        "it",
        "at",
        "my",
        "this",
        "that",
        "was",
        "not",
        "but",
        "from",
        "by",
        "as",
        "we",
        "i",
    }
)


def _shape(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _NOISE and len(w) > 2}


@dataclass
class Recall:
    id: str
    label: str
    reason: str
    overlap: float
    kind: str


def recall_failures(
    state: GraphState,
    text: str,
    labels: dict[str, str],
    reasons: dict[str, str] | None = None,
    limit: int = 3,
) -> list[Recall]:
    """⭐ "You have hit this shape of problem before."

    An immune system does not store every pathogen; it stores the *shape* of
    past threats and recognises recurrence. This does the same over dead ends
    and retractions — the two node states that record what did not work.

    ⚠️ Deliberately lexical, not semantic. A model-based similarity would fire
    on topic ("both about impedance") when what matters is the failure MODE
    ("both were a spurious reading you could not distinguish from a real
    event"). Until there is real data to tune against, a shared-vocabulary
    overlap is honest about what it knows; a model call here would be
    confident and unfalsifiable.
    """
    reasons = reasons or {}
    q = _shape(text)
    if not q:
        return []
    out: list[Recall] = []

    # ⭐ Dead ends are first-class in the projector (`state.dead_ends`), and
    # they carry the QUESTION that was being asked plus what would make the
    # approach worth revisiting. That is the richest failure record we have —
    # far better than a node flag, because it holds the intent, not just the
    # object.
    for did, d in state.dead_ends.items():
        why = d.get("question", "")
        blob = _shape(why) | {t for nid in d.get("nodes", []) for t in _shape(labels.get(nid, ""))}
        if not blob:
            continue
        overlap = len(q & blob) / len(q | blob)
        if overlap >= 0.12:
            out.append(
                Recall(
                    id=did,
                    label=labels.get(did, why[:60] or did),
                    reason=why,
                    overlap=round(overlap, 3),
                    kind="dead_end",
                )
            )

    # Retractions are the other half: not "this did not work" but "this lost
    # its footing", and a student about to repeat an un-supported measurement
    # wants to know that before they run it again.
    # ⚠️ UNSUPPORTED, not a "retracted" state — there isn't one. A conclusion
    # that lost its last support is unfooted, not disproved, and the ATMS keeps
    # those apart on purpose.
    for nid, n in state.nodes.items():
        if n.support is not Support.UNSUPPORTED:
            continue
        why = reasons.get(nid) or ""
        blob = _shape(f"{labels.get(nid, '')} {why}")
        if not blob:
            continue
        overlap = len(q & blob) / len(q | blob)
        if overlap >= 0.12:
            out.append(
                Recall(
                    id=nid,
                    label=labels.get(nid, nid),
                    reason=why,
                    overlap=round(overlap, 3),
                    kind="unsupported",
                )
            )

    out.sort(key=lambda r: (-r.overlap, r.id))
    return out[:limit]


# ── ③ bias — the loop that makes the system get better at YOU ───────────────


@dataclass
class Bias:
    quantity: str
    n: int
    matched: int
    direction: str  # "optimistic" | "pessimistic" | "calibrated"
    median_error: float | None
    advice: str


def bias(artifacts: list[dict], min_n: int = 3) -> list[Bias]:
    """⭐ **The seventh vector, and the one I would bet on.**

    Everything else here tells the student what they know. This tells them how
    they are *habitually wrong* — and it is computable only from a record
    nobody else has: predictions locked before the measurement, grouped by what
    was being predicted.

    A student is rarely wrong at random. They are wrong in a DIRECTION, and
    usually a different direction per quantity: optimistic about timing,
    conservative about noise, wildly off on thermal. A supervisor learns that
    about you in a term and starts saying *"double your ISR estimate."* Nothing
    else in the product can say it, because it needs your outcomes.

    ⚠️ `min_n` is not tuning politeness — it is the difference between a
    finding and a coincidence. Two misses in one direction is a coin landing
    heads twice, and telling a student they are "systematically optimistic" on
    that basis teaches them to ignore the system.

    ⭐ Where this pays out is the prediction lock (`F8`): the moment the
    student types an interval is the only moment this advice can change
    anything.
    """
    groups: dict[str, list[dict]] = {}
    for a in artifacts:
        p, m = a.get("predicted"), a.get("measured")
        if not p or not m or m.get("value") is None:
            continue
        q = (p.get("quantity") or a.get("kind") or "unspecified").lower()
        groups.setdefault(q, []).append(a)

    out: list[Bias] = []
    for q, items in sorted(groups.items()):
        if len(items) < min_n:
            continue
        errs, matched = [], 0
        for a in items:
            p, m = a["predicted"], a["measured"]
            lo, hi, v = float(p["low"]), float(p["high"]), float(m["value"])
            if lo <= v <= hi:
                matched += 1
                errs.append(0.0)
            else:
                # signed, normalised by the interval's own width — so a 2 kΩ
                # miss on a 5 kΩ interval is not compared against a 2 ms miss
                width = max(hi - lo, 1e-9)
                errs.append((v - hi) / width if v > hi else (v - lo) / width)
        errs.sort()
        med = errs[len(errs) // 2]
        if matched / len(items) >= 0.7 or abs(med) < 0.25:
            direction, advice = (
                "calibrated",
                (f"Your {q} predictions are holding — {matched} of {len(items)}."),
            )
        elif med > 0:
            direction, advice = (
                "optimistic",
                (
                    f"Your {q} predictions run LOW — the real value landed above "
                    f"your interval in most misses. Consider widening upward."
                ),
            )
        else:
            direction, advice = (
                "pessimistic",
                (
                    f"Your {q} predictions run HIGH — the real value landed below "
                    f"your interval in most misses. You may be over-padding."
                ),
            )
        out.append(
            Bias(
                quantity=q,
                n=len(items),
                matched=matched,
                direction=direction,
                median_error=round(med, 3),
                advice=advice,
            )
        )
    return out


# ── ④ transfer — the most supervisor-like sentence in the product ───────────


def transfer(state: GraphState, labels: dict[str, str], limit: int = 3) -> list[dict]:
    """⭐ "The noise problem in your lidar build is the same shape as the
    contact-drift problem in your impedance rig."

    Crossovers already exist in `analyzer.py`; this narrows them to the pair
    that is actually worth interrupting for — two nodes in DIFFERENT projects
    that share a failure vocabulary. ⚠️ A crossover between two things you were
    already thinking about is not news; a crossover between two projects you
    keep in separate parts of your head is the whole point.
    """
    by_project: dict[str, list[str]] = {}
    for nid, n in state.nodes.items():
        pid = n.labels_at.get("project")
        if pid:
            by_project.setdefault(pid, []).append(nid)

    out = []
    projects = sorted(by_project)
    for i, pa in enumerate(projects):
        for pb in projects[i + 1 :]:
            for a in by_project[pa]:
                sa = _shape(labels.get(a, ""))
                if len(sa) < 2:
                    continue
                for b in by_project[pb]:
                    sb = _shape(labels.get(b, ""))
                    if len(sb) < 2:
                        continue
                    ov = len(sa & sb) / len(sa | sb)
                    if ov >= 0.3:
                        out.append(
                            {
                                "a": a,
                                "b": b,
                                "a_project": pa,
                                "b_project": pb,
                                "overlap": round(ov, 3),
                                "shared": sorted(sa & sb),
                            }
                        )
    out.sort(key=lambda d: (-d["overlap"], d["a"]))
    return out[:limit]
