"""Frontier and the Disagreement Engine. Backend/01 §8.

Two classes of next action: **gaps** (what you don't know) and **tensions**
(what disagrees). Ranked by information gain per unit of effort.

    knowledge_state K = { c : Concept | ESTABLISHED(c) }   ⭐ not merely supported
    outer_fringe      = { c not in K | every `requires` prereq of c is in K }
    open_questions    = Question nodes with no answering Claim
    dead ends         = suppressed, and RESURRECTED when their blocker changes
    tensions          = every live `contradicts` edge, framed by kind (§8.2)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .projector import GraphState
from .schema import (Confidence, NodeType, Rank, Relation, Strength, Support)

# Six kinds. The trigger is WIDE — kind decides framing, never whether it fires.
FRAMING = {
    "CHECK": "most likely your setup — check it before doubting the source",
    "CONFLICT": "two of your own runs disagree. What changed between them?",
    "STALE": "you concluded the opposite earlier",
    "BOUNDARY": "the source may not apply in your conditions",
    "FINDING": "this may be real — escalate",
    "LITERATURE": "two sources disagree. Which applies to you?",
}


def knowledge_state(state: GraphState) -> set[str]:
    """⭐ ESTABLISHED, not SUPPORTED. One lucky measurement must not mark a
    concept learned — that is what the corroboration gate is for."""
    return {nid for nid, n in state.nodes.items()
            if n.type is NodeType.CONCEPT and n.strength is Strength.ESTABLISHED
            and n.rank is not Rank.DEPRECATED}


def outer_fringe(state: GraphState, known: set[str] | None = None) -> list[str]:
    """Knowledge Space Theory: concepts whose every prerequisite is demonstrated.

    A formal definition of "ready to learn next" — and at t=0 it is the only
    signal in the system that is not empty.
    """
    known = knowledge_state(state) if known is None else known
    out = []
    for nid, n in state.nodes.items():
        if n.type is not NodeType.CONCEPT or nid in known \
                or n.rank is Rank.DEPRECATED:
            continue
        prereqs = [e.src for e in state.edges.values()
                   if e.dst == nid and e.relation is Relation.REQUIRES
                   and e.rank is not Rank.DEPRECATED]
        if all(p in known for p in prereqs):
            out.append(nid)
    return sorted(out)


def open_questions(state: GraphState) -> list[str]:
    answered = {e.dst for e in state.edges.values()
                if e.relation is Relation.ANSWERS
                and e.rank is not Rank.DEPRECATED}
    return sorted(nid for nid, n in state.nodes.items()
                  if n.type is NodeType.QUESTION and nid not in answered
                  and n.rank is not Rank.DEPRECATED)


# ── dead ends: suppression, and resurrection ────────────────────────────────

def dead_end_nodes(state: GraphState) -> set[str]:
    """⚠️ The frontier SUPPRESSES these. Re-suggesting the thing that wasted a
    student's Tuesday is the fastest way to destroy trust in a recommender."""
    return {n for d in state.dead_ends.values() for n in d["nodes"]}


def resurrected(state: GraphState) -> list[dict]:
    """⭐ Nearly free: the justification index already tracks the dependency.

    If anything in `resurrect_if` has since gained support, the dead end comes
    back flagged — "you tried this before it was possible; the blocker has
    changed."
    """
    out = []
    for did, d in sorted(state.dead_ends.items()):
        changed = [nid for nid in d.get("resurrect_if", [])
                   if (n := state.nodes.get(nid))
                   and n.support is Support.SUPPORTED
                   and n.created_seq > d["seq"]]
        if changed:
            out.append({"dead_end": did, "question": d["question"],
                        "unblocked_by": sorted(changed),
                        "why": "you tried this before it was possible — "
                               "the blocker has changed"})
    return out


# ── the Disagreement Engine ─────────────────────────────────────────────────

def _backing(state: GraphState, nid: str) -> set[NodeType]:
    return {state.nodes[e.src].type for e in state.edges.values()
            if e.dst == nid and e.src in state.nodes
            and e.rank is not Rank.DEPRECATED}


def _kind(state: GraphState, a: str, b: str) -> str:
    """⭐ Fires on ANY live `contradicts` edge. The original design fired only
    on the three-way source-vs-bench case, which a hand-walk of a real project
    showed would catch ~2 of ~8-12 genuine disagreements. The corroboration
    gate governs what counts as KNOWN; it must not govern what is worth
    FLAGGING."""
    na, nb = state.nodes[a], state.nodes[b]
    ba, bb = _backing(state, a), _backing(state, b)

    if {na.type, nb.type} == {NodeType.SOURCE} or \
            (NodeType.SOURCE in ba and NodeType.SOURCE in bb
             and NodeType.ARTIFACT not in ba | bb):
        return "LITERATURE"

    bench = [n for n, bk in ((na, ba), (nb, bb))
             if NodeType.ARTIFACT in bk or n.type is NodeType.ARTIFACT]
    lit = [n for n, bk in ((na, ba), (nb, bb))
           if NodeType.SOURCE in bk or n.type is NodeType.SOURCE]

    if len(bench) == 2:
        return "CONFLICT"
    if bench and lit:
        corr = max(n.corroboration for n in bench)
        if corr < 2:
            return "CHECK"                     # ⭐ fires in week 1
        return "BOUNDARY" if bench[0].single_method else "FINDING"
    if bench and not lit:
        return "STALE"
    return "CHECK"


def _priority(state: GraphState, a: str, b: str, kind: str,
              focus: set[str] | None = None, dismissed: int = 0) -> int:
    """Computed continuously, and SEPARATE from kind. Kind says what it is;
    priority says where and when it surfaces."""
    na, nb = state.nodes[a], state.nodes[b]
    score = 0
    if focus and (a in focus or b in focus):
        score += 100                            # blocking the current path
    score += sum(e.weight for e in state.edges.values()
                 if e.dst in (a, b) and e.rank is not Rank.DEPRECATED)
    conf = {Confidence.EXTRACTED: 3, Confidence.INFERRED: 2,
            Confidence.AMBIGUOUS: 1}
    strengths = [max((conf[e.confidence] for e in state.edges.values()
                      if e.dst == n and e.rank is not Rank.DEPRECATED),
                     default=0) for n in (a, b)]
    score += min(strengths)                     # two STRONG claims is worse
    score += max(na.created_seq, nb.created_seq) // 100      # recency
    if kind == "FINDING":
        score += 20                             # "this may be real" escalates
    return score - 10 * dismissed


# ⚠️ Calibrated against real shapes, not guessed. A week-1 CHECK — one
# measurement and one datasheet, each with a single supporting edge — scores 5,
# and the design says it must be visible. A bare contradiction between two
# unsupported claims scores 3 and must stay ambient. The gap between those two
# is the only thing these cutoffs have to separate today; revisit once real
# graphs exist (Backend/07 §5.2).
P1_MIN, P2_MIN = 12, 4


def _level(score: int, focus_hit: bool) -> str:
    if focus_hit:
        return "P0"
    if score >= P1_MIN:
        return "P1"
    if score >= P2_MIN:
        return "P2"
    return "P3"


@dataclass
class Tension:
    a: str
    b: str
    edge: str
    kind: str
    priority: int
    level: str
    framing: str


def tensions(state: GraphState, focus: set[str] | None = None,
             dismissed: dict[str, int] | None = None) -> list[Tension]:
    dismissed = dismissed or {}
    out = []
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if e.relation not in (Relation.CONTRADICTS, Relation.REFUTES):
            continue
        if e.rank is Rank.DEPRECATED or e.src not in state.nodes \
                or e.dst not in state.nodes:
            continue
        kind = _kind(state, e.src, e.dst)
        p = _priority(state, e.src, e.dst, kind, focus, dismissed.get(eid, 0))
        hit = bool(focus and (e.src in focus or e.dst in focus))
        out.append(Tension(a=e.src, b=e.dst, edge=eid, kind=kind, priority=p,
                           level=_level(p, hit), framing=FRAMING[kind]))
    return sorted(out, key=lambda t: (t.level, -t.priority, t.edge))


# ── the ranked frontier ─────────────────────────────────────────────────────

@dataclass
class Action:
    id: str
    kind: str
    priority: float
    why: str
    unlocks: int = 0
    detail: dict = field(default_factory=dict)


def _unlocks(state: GraphState, nid: str) -> int:
    return sum(1 for e in state.edges.values()
               if e.src == nid and e.relation is Relation.REQUIRES
               and e.rank is not Rank.DEPRECATED)


def frontier(state: GraphState, focus: set[str] | None = None,
             limit: int = 3) -> list[Action]:
    """Gaps and tensions in ONE ranking.

    ⭐ Tensions do not get their own queue — they compete with gaps for the
    same slots, so the product has a single notion of "what matters now"
    rather than a frontier and an alert system disagreeing with each other.
    """
    known = knowledge_state(state)
    suppressed = dead_end_nodes(state)
    actions: list[Action] = []

    for nid in outer_fringe(state, known):
        if nid in suppressed:
            continue                    # never re-suggest a known dead end
        u = _unlocks(state, nid)
        # ⚠️ Every root is "ready", so without this a day-one frontier offers
        # "Algebraic manipulation" to a student asking about bioimpedance.
        # Skeleton tier is a usable proxy for specificity: tier 0-1 is
        # background almost every undergraduate already has, tier 3-4 is what
        # they are actually reaching for. Ranking by it puts the domain concept
        # first without pretending we know what they know.
        tier = int(state.nodes[nid].labels_at.get("tier", 2))
        actions.append(Action(
            id=nid, kind="GAP", priority=1.0 + u + 0.4 * tier,
            why=f"ready to learn — unlocks {u} thing(s)" if u
                else "ready to learn", unlocks=u,
            detail={"tier": tier}))

    for t in tensions(state, focus):
        if t.level == "P3":
            continue                    # ambient: never pushed
        actions.append(Action(
            id=t.edge, kind=f"TENSION/{t.kind}",
            priority=3.0 + t.priority / 10, why=t.framing,
            detail={"a": t.a, "b": t.b, "level": t.level}))

    for q in open_questions(state):
        actions.append(Action(id=q, kind="QUESTION", priority=1.5,
                              why="open question with no answering claim"))

    for r in resurrected(state):
        actions.append(Action(id=r["dead_end"], kind="RESURRECTED",
                              priority=4.0, why=r["why"], detail=r))

    return sorted(actions, key=lambda a: (-a.priority, a.kind, a.id))[:limit]
