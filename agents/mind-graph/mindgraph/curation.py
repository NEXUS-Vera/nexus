"""Structuring nudge, concept promotion, joint support, export.

The three resolutions that had specs but no code (Q3, Q4, hyperedges), plus
the export the design promises.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .events import EventType
from .ids import uuid7
from .projector import GraphState
from .schema import (MERGE_HARD, Confidence, NodeType, Origin, Rank, Relation,
                     Scope)

NOTE_RATIO_TRIGGER = 0.40      # unstructured share of recent nodes
NOTE_COUNT_TRIGGER = 15
RECENT_WINDOW = 50             # in seq
MAX_REFUSALS = 2               # a note that resists twice is left alone


@dataclass
class Nudge:
    triggered: bool
    ratio: float
    outstanding: list[str]
    reason: str = ""


def structuring_nudge(state: GraphState) -> Nudge:
    """Q3. ⭐ An OFFER, never a requirement.

    A `Note` cannot hold predicted/measured, cannot be corroborated, cannot be
    contradicted — so a graph of Notes has none of the differentiators and we
    are Obsidian with extra steps. But requiring structure at capture is what
    *Formality Considered Harmful* says kills adoption, so the only shape that
    gets both is a threshold-triggered batch offer.
    """
    cutoff = state.last_seq - RECENT_WINDOW
    recent = [n for n in state.nodes.values() if n.created_seq > cutoff
              and n.rank is not Rank.DEPRECATED]
    notes = [n for n in recent if n.type is NodeType.NOTE]
    outstanding = sorted(n.id for n in state.nodes.values()
                         if n.type is NodeType.NOTE
                         and n.rank is not Rank.DEPRECATED
                         and int(n.labels_at.get("refusals", 0)) < MAX_REFUSALS
                         and not n.labels_at.get("structured"))
    ratio = len(notes) / len(recent) if recent else 0.0
    if ratio > NOTE_RATIO_TRIGGER and outstanding:
        return Nudge(True, round(ratio, 3), outstanding,
                     f"{len(notes)} of the last {len(recent)} nodes are "
                     f"unstructured notes")
    if len(outstanding) >= NOTE_COUNT_TRIGGER:
        return Nudge(True, round(ratio, 3), outstanding,
                     f"{len(outstanding)} notes are still unstructured")
    return Nudge(False, round(ratio, 3), outstanding)


def refuse_nudge(s, note_ids: list[str]) -> None:
    """⭐ A note that resists structuring twice is left alone PERMANENTLY.

    Asking a third time is how the feature gets turned off.
    """
    st = s.state()
    fields = {}
    for nid in sorted(note_ids):
        if (n := st.nodes.get(nid)) is not None:
            fields[nid] = int(n.labels_at.get("refusals", 0)) + 1
    for nid, count in fields.items():
        s.ledger.append(s.user, EventType.CORRECTION,
                        {"target": nid,
                         "fields": {"labels_at": {"refusals": str(count)}}})


def promote_concepts(s, min_projects: int = 2,
                     min_score: float = MERGE_HARD) -> list[str]:
    """Q4. An EXTRACTED concept seen in a second project at >=0.95 becomes global.

    ⭐ No confirmation step, so no organisational tax — and the blast radius
    stays contained because only high-confidence repeats are promoted.
    """
    st = s.state()
    by_label: dict[str, set[str]] = {}
    for nid, n in st.nodes.items():
        if n.type is not NodeType.CONCEPT or n.origin is not Origin.EXTRACTED:
            continue
        key = nid
        for e in st.edges.values():
            if (e.relation is Relation.SAME_AS and e.score >= min_score
                    and e.rank is not Rank.DEPRECATED and nid in (e.src, e.dst)):
                key = min(key, e.src, e.dst)
        by_label.setdefault(key, set()).add(n.project_id or "")

    promoted = sorted(k for k, projects in by_label.items()
                      if len({p for p in projects if p}) >= min_projects)
    for nid in promoted:
        s.ledger.append(s.user, EventType.CORRECTION,
                        {"target": nid,
                         "fields": {"origin": Origin.PROMOTED.value,
                                    "scope": Scope.GLOBAL.value,
                                    "project_id": None}})
    return promoted


def joint_support(s, members: list[str], target: str, *,
                  score: float = 0.85, justification: list[str] | None = None
                  ) -> str:
    """A hyperedge. "These five measurements JOINTLY support this" is ONE
    relationship, not five.

    ⚠️ The difference shows on retraction: with five separate edges, removing
    one leaves four and the conclusion still looks well supported. With a
    hyperedge the joint justification is either satisfied or it is not.
    """
    if len(set(members)) < 3:
        raise ValueError("joint support needs 3+ distinct members")
    hid = uuid7()
    s.ledger.append(s.user, EventType.ACCEPTED, {
        "nodes": [], "edges": [],
        "hyperedges": [{"id": hid, "relation": "jointly_support",
                        "members": sorted(members), "target": target,
                        "confidence": Confidence.INFERRED.value, "score": score,
                        "justification": sorted(justification or [])}]})
    return hid


def export(state: GraphState, labels: dict[str, str] | None = None) -> str:
    """Structured export. ⭐ An Atlas map cannot leave Atlas as data; ours can.

    Nothing downstream can consume a PNG, and a graph you cannot get out of a
    product is a graph you do not own.
    """
    labels = labels or {}
    return json.dumps({
        "schema_version": 1,
        "nodes": [{"id": nid, "type": n.type.value, "kind": n.kind,
                   "label": labels.get(nid), "support": n.support.value,
                   "strength": n.strength.value,
                   "corroboration": n.corroboration,
                   "single_method": n.single_method,
                   "scope": n.scope.value, "origin": n.origin.value,
                   "external_ids": n.external_ids,
                   "outcome": n.labels_at.get("outcome")}
                  for nid, n in sorted(state.nodes.items())
                  if n.rank is not Rank.DEPRECATED],
        "edges": [{"id": eid, "src": e.src, "dst": e.dst,
                   "relation": e.relation.value,
                   "confidence": e.confidence.value, "score": e.score,
                   "weight": e.weight,
                   "citation_state": e.provenance.get("citation_state"),
                   "span": e.provenance.get("span")}
                  for eid, e in sorted(state.edges.items())
                  if e.rank is not Rank.DEPRECATED],
        "hyperedges": [{"id": hid, "relation": h.relation,
                        "members": h.members, "target": h.target,
                        "score": h.score}
                       for hid, h in sorted(state.hyper.items())],
        "dead_ends": [{"id": did, **d} for did, d in
                      sorted(state.dead_ends.items())],
    }, indent=2, sort_keys=True)
