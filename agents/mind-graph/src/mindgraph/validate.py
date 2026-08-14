"""The code gate. Backend/03 §4.

Runs on every fragment before anything reaches the proposal queue.
**Rejection is normal, not exceptional.**

Two classes of failure, and the difference matters:
  HARD  the item dies and is quarantined
  SOFT  the item is DEMOTED rather than discarded — a weakly-cited claim
        becomes a low-confidence claim, not silence
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ledger import canonical
from .schema import LEGAL_SCORES, Confidence, NodeType, Relation

MAX_FRAGMENT_BYTES = 200_000
KEY_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,79}")

KINDS: dict[str, set[str | None]] = {
    "Concept": {None},
    "Question": {None},
    "Claim": {None, "observation", "conclusion", "hypothesis"},
    "Artifact": {None, "code", "circuit", "run", "measurement", "document",
                 "method"},
    "Source": {None, "paper", "datasheet", "video", "course", "web", "book"},
    "Note": {None},
}

SENTENCE_MARKERS = re.compile(
    r"\b(is|are|was|were|has|have|should|would|could|will|did|does|because|"
    r"therefore|so that|which|that we|we|i)\b", re.I)

RUNG = [1.0, 0.95, 0.85, 0.75, 0.65, 0.55, 0.3, 0.2, 0.1]


def is_sentence_like(label: str) -> bool:
    """A label is a NAME, not a sentence.

    Ported from Graphify's hard-won heuristic. This is the #1 failure mode of
    LLM-built graphs: prose becomes nodes and the graph turns into a pile of
    unjoinable sentences that no two documents ever agree on.
    """
    return (len(label) > 60
            or label.rstrip().endswith((".", "!", "?"))
            or label.count(" ") > 7
            or bool(SENTENCE_MARKERS.search(label)))


def demote_one_rung(score: float) -> float:
    i = RUNG.index(score) if score in RUNG else 0
    return RUNG[min(i + 1, len(RUNG) - 1)]


def truncate_to_noun_phrase(label: str) -> str:
    head = re.split(r"[.,;:(]| that | which | because ", label, maxsplit=1)[0]
    return " ".join(head.split()[:8]).strip() or label[:60]


@dataclass
class Reject:
    item: dict
    reason: str


@dataclass
class Validated:
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    rejects: list[Reject] = field(default_factory=list)
    demotions: list[str] = field(default_factory=list)


def validate(fragment: dict, known_keys: set[str] | None = None) -> Validated:
    out = Validated()
    known_keys = known_keys or set()

    if not isinstance(fragment, dict):
        out.rejects.append(Reject({}, "not an object"))
        return out
    if len(canonical(fragment)) > MAX_FRAGMENT_BYTES:
        out.rejects.append(Reject({}, "oversize"))
        return out

    for n in fragment.get("nodes", []):
        n = dict(n)
        if n.get("type") not in {t.value for t in NodeType}:
            out.rejects.append(Reject(n, "unknown type")); continue
        if n.get("kind") not in KINDS[n["type"]]:
            out.rejects.append(Reject(n, "bad kind")); continue
        if not (n.get("key") and KEY_RE.fullmatch(n["key"])):
            out.rejects.append(Reject(n, "malformed key")); continue
        label = n.get("label") or ""
        if not label:
            out.rejects.append(Reject(n, "missing label")); continue

        # SOFT — demote rather than discard.
        if n["type"] != "Note" and is_sentence_like(label):
            n["type"], n["kind"] = "Note", None
            n["body"] = label
            n["label"] = truncate_to_noun_phrase(label)
            out.demotions.append(f"{n['key']}: sentence-like label -> Note")
        elif len(label) > 60:
            n["body"] = label
            n["label"] = truncate_to_noun_phrase(label)
        out.nodes.append(n)

    frag_keys = {n["key"] for n in out.nodes} | known_keys
    types = {n["key"]: n["type"] for n in out.nodes}

    for e in fragment.get("edges", []):
        e = dict(e)
        if e.get("relation") not in {r.value for r in Relation}:
            out.rejects.append(Reject(e, "unknown relation")); continue
        if e.get("score") not in LEGAL_SCORES:
            out.rejects.append(Reject(e, "off-rubric score")); continue
        if e.get("confidence") not in {c.value for c in Confidence}:
            out.rejects.append(Reject(e, "unknown confidence tier")); continue
        if e["confidence"] == "EXTRACTED" and e["score"] != 1.0:
            out.rejects.append(Reject(e, "false certainty")); continue

        # Citation state gates the tier (Backend/08 §5.1). This closes the most
        # likely route to a confident, well-cited, WRONG edge.
        cs = e.get("citation_state")
        if e["confidence"] == "EXTRACTED" and cs != "present_relevant":
            out.rejects.append(
                Reject(e, "EXTRACTED requires a directly-supporting passage"))
            continue
        if cs in ("present_weak", "anchor_unavailable") and e["score"] > 0.75:
            e["score"] = 0.75
            out.demotions.append(f"{e.get('src_key')}->{e.get('dst_key')}: weak citation")
        if cs == "missing" and e["score"] > 0.65:
            e["score"] = 0.65
            out.demotions.append(f"{e.get('src_key')}->{e.get('dst_key')}: no source")
        if cs == "wrong_source":
            e["confidence"], e["score"] = "AMBIGUOUS", 0.3
            out.demotions.append(f"{e.get('src_key')}->{e.get('dst_key')}: wrong source")

        if e["relation"] == "requires" and not all(
                types.get(k, "Concept") == "Concept"
                for k in (e.get("src_key"), e.get("dst_key")) if k in types):
            out.rejects.append(Reject(e, "requires is Concept->Concept only")); continue
        if e.get("src_key") == e.get("dst_key"):
            out.rejects.append(Reject(e, "self-loop")); continue
        if e.get("src_key") not in frag_keys or e.get("dst_key") not in frag_keys:
            out.rejects.append(Reject(e, "dangling endpoint")); continue
        if e.get("span") is None and e["confidence"] != "EXTRACTED":
            e["score"] = demote_one_rung(e["score"])

        out.edges.append(e)

    return out
