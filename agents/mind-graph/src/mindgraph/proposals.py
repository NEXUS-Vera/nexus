"""Routing to the human. Backend/03 §5, Backend/09 Q1.

    EXTRACTED        auto-accept
    all INFERRED     auto-accept, flagged, one-click reversible
    ⭐ AMBIGUOUS     ALWAYS asked of the student — never auto-accepted,
                     never dropped
    contradicts      always review — cheap to check, expensive to get wrong
    quarantined      review queue, low priority

⚠️ Review is far more expensive than it looks. Trained professional pods manage
2,000–12,000 outputs/day; our reviewer is one unpaid undergraduate with a
project due. Budget 20–30 decisions per session, which makes aggressive,
well-calibrated auto-accept a requirement rather than an optimisation.

The queue holds ONLY what nobody but the student can settle. That is what turns
it from an integrity gate into a thinking prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .crypto import encrypt
from .events import EventType
from .extract import Fragment
from .ids import uuid7
from .resolve import resolve_candidates
from .validate import Validated, validate

REVIEW_SOFT_CAP = 50  # above this we stop proposing anything below 0.85


@dataclass
class IngestReport:
    source_ref: str
    lane: str
    accepted_nodes: int = 0
    accepted_edges: int = 0
    review: list[dict] = field(default_factory=list)
    quarantined: list[dict] = field(default_factory=list)
    demotions: list[str] = field(default_factory=list)
    same_as: list[dict] = field(default_factory=list)
    duplicate: bool = False

    def as_dict(self) -> dict:
        return {
            "source": self.source_ref,
            "lane": self.lane,
            "accepted": {"nodes": self.accepted_nodes, "edges": self.accepted_edges},
            "review": len(self.review),
            "quarantined": len(self.quarantined),
            "demoted": len(self.demotions),
            "same_as": len(self.same_as),
            "duplicate": self.duplicate,
        }


def _seen_hashes(s) -> set[str]:
    return {e.structural.get("sha256") for e in s.ledger.read() if e.structural.get("sha256")}


def _key_to_id(s, key: str, cache: dict[str, str]) -> str:
    if key not in cache:
        cache[key] = uuid7()
    return cache[key]


def _route(edge: dict) -> str:
    """One place, so the rule cannot drift between callers."""
    if edge["confidence"] == "AMBIGUOUS":
        return "review"
    if edge["relation"] in ("contradicts", "refutes"):
        return "review"
    return "accept"


def ingest(s, frag: Fragment, *, project_id: str = "p1") -> IngestReport:
    from .costlog import for_session

    with for_session(s).measure("ingest", lane=frag.lane, source=frag.source_ref):
        return _ingest(s, frag, project_id=project_id)


def _ingest(s, frag: Fragment, *, project_id: str = "p1") -> IngestReport:
    rep = IngestReport(source_ref=frag.source_ref, lane=frag.lane)

    if frag.sha256 in _seen_hashes(s):
        rep.duplicate = True  # cheap filter, runs first
        return rep

    v: Validated = validate(frag.payload)
    rep.demotions = v.demotions
    rep.quarantined = [{"item": r.item, "reason": r.reason} for r in v.rejects]

    st = s.state()
    keymap: dict[str, str] = {}
    nodes, labels = [], {}
    for n in v.nodes:
        nid = _key_to_id(s, n["key"], keymap)
        d = {"id": nid, "type": n["type"]}
        if n.get("kind"):
            d["kind"] = n["kind"]
        if n["type"] == "Concept":
            d["project_id"] = project_id  # extracted -> project-scoped
        nodes.append(d)
        labels[nid] = n["label"]  # user text: encrypted below

    accept_edges, review_edges = [], []
    for e in v.edges:
        payload = {
            "id": uuid7(),
            "src": keymap[e["src_key"]],
            "dst": keymap[e["dst_key"]],
            "relation": e["relation"],
            "confidence": e["confidence"],
            "score": e["score"],
            "weight_source_nodes": [keymap[e["src_key"]]],
            "provenance": {
                "citation_state": e.get("citation_state"),
                "span": e.get("span"),
                "actor": "extractor",
            },
        }
        (accept_edges if _route(e) == "accept" else review_edges).append(payload)

    # Entity resolution against what is already in the graph, plus this batch.
    existing = {nid: st.nodes[nid].label for nid in st.nodes if st.nodes[nid].label}
    for cand in resolve_candidates({**existing, **labels}):
        if cand["band"] == "same_as":
            accept_edges.append(
                {
                    "id": uuid7(),
                    "src": cand["a"],
                    "dst": cand["b"],
                    "relation": "same_as",
                    "confidence": "INFERRED",
                    "score": 0.75,
                    "weight_source_nodes": [cand["a"]],
                    "provenance": {"actor": "resolver", "similarity": cand["score"]},
                }
            )
            rep.same_as.append(cand)
        elif cand["band"] == "merge":
            s.ledger.append(s.user, EventType.MERGED, {"kept": cand["a"], "absorbed": cand["b"]})

    if nodes or accept_edges:
        s.ledger.append(
            s.user,
            EventType.ACCEPTED,
            {
                "nodes": nodes,
                "edges": accept_edges,
                "sha256": frag.sha256,
                "source_ref_id": uuid7(),
            },
            content=encrypt(s.keys, s.user, {"labels": labels, "source_ref": frag.source_ref}),
        )
        rep.accepted_nodes, rep.accepted_edges = len(nodes), len(accept_edges)

    if review_edges or rep.quarantined:
        s.ledger.append(
            s.user,
            EventType.PROPOSED,
            {
                "edges": review_edges,
                "quarantine": [{"reason": q["reason"]} for q in rep.quarantined],
                "sha256": frag.sha256,
            },
            content=encrypt(s.keys, s.user, {"quarantine_raw": rep.quarantined}),
        )
    rep.review = review_edges
    return rep


def pending_review(s) -> list[dict]:
    """Everything proposed and not yet decided. Small by construction."""
    proposed: dict[str, dict] = {}
    for e in s.ledger.read():
        if e.type is EventType.PROPOSED:
            for ed in e.structural.get("edges", []):
                proposed[ed["id"]] = {**ed, "seq": e.seq}
        elif e.type in (EventType.ACCEPTED, EventType.REJECTED):
            for ed in e.structural.get("edges", []):
                proposed.pop(ed.get("id"), None)
            for rid in e.structural.get("decided", []):
                proposed.pop(rid, None)
    return [proposed[k] for k in sorted(proposed)]


def decide(s, edge_ids: list[str], accept: bool) -> int:
    """Bulk accept/reject. Batch, never interrupt."""
    pend = {e["id"]: e for e in pending_review(s)}
    chosen = [pend[i] for i in edge_ids if i in pend]
    if not chosen:
        return 0
    if accept:
        s.ledger.append(
            s.user,
            EventType.ACCEPTED,
            {
                "nodes": [],
                "edges": [{k: v for k, v in c.items() if k != "seq"} for c in chosen],
                "decided": [c["id"] for c in chosen],
            },
        )
    else:
        s.ledger.append(
            s.user, EventType.REJECTED, {"edges": [], "decided": [c["id"] for c in chosen]}
        )
    return len(chosen)
