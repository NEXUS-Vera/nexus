"""Cold start. Backend/07 §1.

    ⭐ The graph is never empty, because it starts as a structured QUESTION
       rather than an empty container.

An empty graph is worse than no graph: it makes the product look broken at
exactly the moment a student decides whether to continue. At t=0 nothing is
validated — and that is correct, not a deficiency. The first screen shows what
you don't know yet, which is what the frontier engine is for.

Three seeding sources, in order of availability:
    ① the question itself   always available
    ② the concept skeleton  any embedded project
    ③ a transcript          optional — and a PRIOR, never a state
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .crypto import encrypt
from .events import EventType
from .ids import uuid7
from .schema import Confidence, Relation
from .skeleton import Skeleton, load

NODE_CAP = 25          # half the comprehension limit, deliberately
MAX_SUBQUESTIONS = 6

# "How will you know it worked?" is the single most useful question to ask an
# undergraduate — and it fixes the cold start as a side effect.
MEASURABLE = re.compile(
    r"\b(\d|measure|accuracy|within|percent|%|hz|khz|mhz|ohm|volt|amp|"
    r"second|ms|error|threshold|detect|track|compare|distinguish)\b", re.I)


@dataclass
class ColdStart:
    project_id: str
    root: str
    subquestions: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    exposures: list[str] = field(default_factory=list)
    matched: bool = True
    vague: bool = False
    capped: int = 0

    def as_dict(self) -> dict:
        return {"project": self.project_id, "root": self.root,
                "subquestions": len(self.subquestions),
                "concepts": len(self.concepts),
                "exposures": len(self.exposures),
                "skeleton_matched": self.matched, "vague": self.vague,
                "capped_from": self.capped}


def is_vague(question: str) -> bool:
    """⚠️ "Build a robot" produces a generic decomposition and a useless graph.

    The guard is Queries/07's verifiability rule arriving as an onboarding
    step: demand a measurable success criterion before seeding anything.
    """
    return not MEASURABLE.search(question)


def decompose(question: str, llm=None) -> list[str]:
    """3-6 sub-questions. With no endpoint, falls back to a structural
    decomposition — worse than a model's, but never empty."""
    if llm is not None:
        try:
            out = llm.extract(question, "coldstart:decompose")
            qs = [n["label"] for n in out.get("nodes", [])
                  if n.get("type") == "Question"]
            if qs:
                return qs[:MAX_SUBQUESTIONS]
        except Exception:
            pass
    stem = question.rstrip("?").strip()
    return [f"What has to be true for: {stem}?",
            f"What would you measure to test: {stem}?",
            f"What could confound that measurement?",
            f"What accuracy would be enough to be useful?"]


def seed_project(s, question: str, *, project_id: str | None = None,
                 transcript: str = "", llm=None,
                 skeleton: Skeleton | None = None) -> ColdStart:
    """60 seconds after one typed sentence: a graph with a computable frontier."""
    sk = skeleton if skeleton is not None else load()
    pid = project_id or uuid7()
    root = uuid7()
    cs = ColdStart(project_id=pid, root=root, vague=is_vague(question))

    subs = decompose(question, llm)
    cs.subquestions = [uuid7() for _ in subs]

    # ② skeleton match + requires-closure two levels up
    hits = sk.match(question + " " + " ".join(subs), limit=NODE_CAP)
    matched_ids = sk.closure({cid for cid, _ in hits}, levels=2)

    nodes = [{"id": root, "type": "Question", "project_id": pid}]
    edges = []
    labels = {root: question}
    for qid, text in zip(cs.subquestions, subs):
        nodes.append({"id": qid, "type": "Question", "project_id": pid})
        labels[qid] = text
        edges.append({"id": uuid7(), "src": root, "dst": qid,
                      "relation": Relation.RAISES.value,
                      "confidence": Confidence.INFERRED.value, "score": 0.75,
                      "weight_source_nodes": [root],
                      "provenance": {"actor": "coldstart"}})

    # ⭐ Curated concepts are GLOBAL by construction — no project_id (Q4).
    id_of = {cid: uuid7() for cid in sorted(matched_ids)}
    budget = NODE_CAP - len(nodes)
    ranked = sorted(matched_ids, key=lambda c: (sk.concepts[c].tier, c))
    cs.capped = max(0, len(ranked) - budget)
    kept_ids = _prerequisite_closed(sk, ranked[:budget])
    for cid in kept_ids:
        c = sk.concepts[cid]
        nodes.append({"id": id_of[cid], "type": "Concept", "kind": None,
                      "scope": "global", "origin": "curated",
                      "project_id": None,
                      "external_ids": {"skeleton": cid},
                      "labels_at": {"domain": c.domain, "tier": str(c.tier)}})
        labels[id_of[cid]] = c.label
        cs.concepts.append(id_of[cid])

    kept = set(cs.concepts)
    for cid in kept_ids:
        for p in sk.concepts[cid].requires:
            if p in id_of and id_of[p] in kept:
                edges.append({"id": uuid7(), "src": id_of[p],
                              "dst": id_of[cid],
                              "relation": Relation.REQUIRES.value,
                              "confidence": Confidence.EXTRACTED.value,
                              "score": 1.0,
                              "weight_source_nodes": [id_of[p]],
                              "provenance": {
                                  "actor": "skeleton",
                                  "citation_state": "present_relevant",
                                  "span": f"Backend/04:{cid}"}})

    s.ledger.append(s.user, EventType.ACCEPTED,
                    {"nodes": nodes, "edges": edges, "project_id": pid},
                    content=encrypt(s.keys, s.user, {"labels": labels}))

    # ⚠️ `matched` reports what was SEEDED, not what was hit. A question can
    # match the skeleton and still seed nothing once the prerequisite-closed
    # filter and the node cap have run — and a student who gets no lattice and
    # no warning concludes the product is broken rather than out of scope.
    cs.matched = bool(cs.concepts)

    # ③ transcript — a PRIOR, not a state.
    if transcript:
        cs.exposures = _mark_exposure(s, sk, transcript, id_of)
    return cs


def _prerequisite_closed(sk: Skeleton, chosen: list[str]) -> list[str]:
    """⚠️ Drop anything whose prerequisites the cap cut away.

    The outer fringe asks "are all `requires` prerequisites known?" — and a
    prerequisite that was never seeded has no edge, so the check passes
    vacuously. A concept then presents as READY TO LEARN when in fact the
    graph simply cannot see what it depends on, which is the worst kind of
    wrong: confidently, invisibly.

    Keeping only the prerequisite-closed subset makes the fringe honest. The
    dropped concepts are not lost — they arrive as the student's knowledge
    state grows and the closure reaches them.
    """
    have = set(chosen)
    while True:
        ok = {c for c in have
              if all(p in have or p not in sk.concepts
                     for p in sk.concepts[c].requires)}
        if ok == have:
            return sorted(ok, key=lambda c: (sk.concepts[c].tier, c))
        have = ok


def _mark_exposure(s, sk: Skeleton, transcript: str,
                   id_of: dict[str, str]) -> list[str]:
    """⚠️ A passed course is evidence of EXPOSURE, not knowledge.

    Structurally prevented from becoming knowledge: this writes an annotation,
    never a `supports` edge, so nothing reaches Support.SUPPORTED and nothing
    enters the knowledge state without a Claim or an Artifact behind it.
    """
    hit = [cid for cid, _ in sk.match(transcript, limit=50) if cid in id_of]
    if not hit:
        return []
    s.ledger.append(s.user, EventType.ANNOTATED,
                    {"exposure": sorted(id_of[c] for c in hit),
                     "basis": "transcript"})
    return sorted(id_of[c] for c in hit)


def exposure_marks(s) -> set[str]:
    out: set[str] = set()
    for e in s.ledger.read():
        if e.type is EventType.ANNOTATED:
            out |= set(e.structural.get("exposure", []))
    return out
