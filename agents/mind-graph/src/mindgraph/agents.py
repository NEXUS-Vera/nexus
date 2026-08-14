"""The agent layer. Backend/05.

Three invariants, and everything else follows from them:

  1. Agents PROPOSE. The ledger is written by the gate. There is no code path
     from a model's output to a node.
  2. Determinism is preserved by RECORDING, not by constraining — agent output
     is replayed from the record, never re-run.
  3. ⭐ Every dispatched call is CONTEXT-ISOLATED: an independent, stateless
     request with a capability-scoped payload, never a turn in a running chat.

Invariant 3 is what makes §2.1 real. A call without READ_CONTENT cannot claim
EXTRACTED because it has never seen a source — but only if it has GENUINELY
never seen one. Run the reader and the reasoner as two messages of one
conversation and the document text is still in context: the gate checks the
declared capabilities, the context contains material those capabilities
exclude, and the guarantee silently becomes a lie while every test still passes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from .projector import GraphState
from .schema import Confidence, Rank


class Cap(StrEnum):
    READ_STRUCTURE = "READ_STRUCTURE"
    READ_CONTENT = "READ_CONTENT"          # ⚠️ the user's private text
    READ_FRONTIER = "READ_FRONTIER"
    READ_TIMELINE = "READ_TIMELINE"
    VERIFY_SPAN = "VERIFY_SPAN"            # read ONE already-cited span
    SEARCH_EXTERNAL = "SEARCH_EXTERNAL"
    PROPOSE = "PROPOSE"
    VALIDATE = "VALIDATE"                  # ⚠️⚠️ never granted to an agent
    RETRACT = "RETRACT"                    # ⚠️⚠️ never granted to an agent


NEVER_GRANTED = {Cap.VALIDATE, Cap.RETRACT}

# ⭐ Confidence tier is bound to capability. Checked in the GATE, never
# requested in a prompt — a prompt is a request; a capability check is a fact
# about the call.
TIER_REQUIRES = {
    Confidence.EXTRACTED: {Cap.READ_CONTENT},
    Confidence.INFERRED: {Cap.READ_STRUCTURE},
    Confidence.AMBIGUOUS: set(),
}

CITATION_CEILING = {
    "present_relevant": 1.0, "present_weak": 0.75, "missing": 0.65,
    "anchor_unavailable": 0.75, "wrong_source": 0.3,
}


class Tier(StrEnum):
    """Route by VERIFIABILITY, not by perceived difficulty.

    If a wrong answer is caught by code, use the cheapest model that passes the
    validator. If it is caught only by a human — or by nobody — use the best.
    """
    T0 = "none"          # deterministic. free, zero latency
    T1A = "oss"          # bulk extraction + embeddings; schema-validated
    T1B = "haiku"        # small, user-visible, needs instruction-following
    T2 = "sonnet"        # partially checkable
    T3 = "opus"          # not mechanically checkable


@dataclass(frozen=True)
class Role:
    name: str
    caps: frozenset[Cap]
    tier: Tier
    can_propose: bool = True


# A CONFIGURATION, not architecture (Q2). Role count is negotiable; isolation
# is not. Merging Grounder and Synthesiser would cost ~70% MORE, because
# project_view keeps document bodies off the expensive model.
DEFAULT_ROLES = {
    "planner": Role("planner", frozenset({Cap.READ_STRUCTURE, Cap.READ_FRONTIER}),
                    Tier.T3, can_propose=False),
    "grounder": Role("grounder", frozenset({Cap.READ_STRUCTURE, Cap.READ_CONTENT,
                                            Cap.SEARCH_EXTERNAL, Cap.PROPOSE}),
                     Tier.T2),
    "synthesiser": Role("synthesiser",
                        frozenset({Cap.READ_STRUCTURE, Cap.PROPOSE}), Tier.T3),
    "critic": Role("critic", frozenset({Cap.READ_STRUCTURE, Cap.READ_TIMELINE,
                                        Cap.VERIFY_SPAN, Cap.PROPOSE}),
                   Tier.T2),
}


# ── project_view: the capability filter that is also a cost filter ──────────

def project_view(state: GraphState, caps: frozenset[Cap], node_ids: list[str],
                 labels: dict[str, str] | None = None) -> dict:
    """⭐ One function, and it carries most of the security model.

    It is also most of the COST model: stripping bodies for a structure-only
    role is why the frontier-tier call never carries the ~8k-token content
    payload the grounder does.
    """
    labels = labels or {}
    if Cap.READ_STRUCTURE not in caps:
        return {"nodes": [], "edges": []}
    nodes, edges = [], []
    for nid in sorted(set(node_ids)):
        if (n := state.nodes.get(nid)) is None:
            continue
        d = {"id": nid, "type": n.type.value, "kind": n.kind,
             "support": n.support.value, "strength": n.strength.value,
             "corroboration": n.corroboration, "single_method": n.single_method}
        if Cap.READ_CONTENT in caps:          # ⚠️ privileged
            d["label"] = labels.get(nid)
            d["body_ref"] = n.body_ref
        nodes.append(d)
    keep = {n["id"] for n in nodes}
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if e.src in keep and e.dst in keep and e.rank is not Rank.DEPRECATED:
            ed = {"id": eid, "src": e.src, "dst": e.dst,
                  "relation": e.relation.value, "confidence": e.confidence.value,
                  "score": e.score, "weight": e.weight}
            if Cap.READ_CONTENT in caps:
                ed["span"] = e.provenance.get("span")
            edges.append(ed)
    return {"nodes": nodes, "edges": edges}


def spans_for(state: GraphState, edge_ids: list[str]) -> dict[str, str]:
    """VERIFY_SPAN: exactly the spans another call already cited THIS TURN.
    Cannot browse, cannot search."""
    return {eid: state.edges[eid].provenance.get("span")
            for eid in sorted(set(edge_ids)) if eid in state.edges}


# ── the gate ────────────────────────────────────────────────────────────────

@dataclass
class Rejection:
    item: dict
    reason: str


@dataclass
class GateResult:
    accepted: list[dict] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    downgrades: list[str] = field(default_factory=list)


def gate(proposals: list[dict], role: Role, *, basis_required: bool = True,
         prior: dict[str, str] | None = None) -> GateResult:
    """Every rule here is enforced server-side. No client-supplied capabilities.

    ⭐ The Critic's citation_state changes are DOWNGRADE-ONLY. A Critic that
    could RAISE a citation would become a second, unaccountable Grounder.
    """
    out = GateResult()
    prior = prior or {}
    for p in proposals:
        if Cap.PROPOSE not in role.caps:
            out.rejected.append(Rejection(p, f"{role.name} cannot propose"))
            continue
        try:
            tier = Confidence(p.get("confidence"))
        except ValueError:
            out.rejected.append(Rejection(p, "unknown confidence tier"))
            continue

        need = TIER_REQUIRES[tier]
        if not need <= role.caps:
            out.rejected.append(Rejection(
                p, f"{role.name} lacks {sorted(need - role.caps)} for {tier.value}"))
            continue
        if tier is Confidence.EXTRACTED and not p.get("span"):
            out.rejected.append(Rejection(p, "EXTRACTED requires a span"))
            continue

        cs = p.get("citation_state")
        if cs:
            ceiling = CITATION_CEILING.get(cs)
            if ceiling is None:
                out.rejected.append(Rejection(p, f"unknown citation_state {cs}"))
                continue
            if p.get("score", 0) > ceiling:
                out.downgrades.append(
                    f"{p.get('id')}: {p['score']} -> {ceiling} ({cs})")
                p = {**p, "score": ceiling}
                if ceiling <= 0.3:
                    p["confidence"] = Confidence.AMBIGUOUS.value

            # Downgrade-only: the Critic may say "this passage supports that
            # claim less than claimed", never more.
            if (was := prior.get(p.get("id"))) and Cap.VERIFY_SPAN in role.caps \
                    and Cap.READ_CONTENT not in role.caps:
                if CITATION_CEILING.get(cs, 1.0) > CITATION_CEILING.get(was, 1.0):
                    out.rejected.append(Rejection(
                        p, "VERIFY_SPAN may downgrade a citation, never raise it"))
                    continue

        if basis_required and not p.get("basis"):
            out.rejected.append(Rejection(
                p, "no basis — an unjustified claim is rejected"))
            continue
        out.accepted.append(p)
    return out


# ── the turn ────────────────────────────────────────────────────────────────

class Agent(Protocol):
    def run(self, role: Role, payload: dict, question: str) -> dict: ...


HARD_MARKERS = ("why", "keep failing", "everything", "whole", "compare",
                "across", "explain how", "root cause")


@dataclass
class Turn:
    question: str
    role_calls: list[str] = field(default_factory=list)
    escalated: bool = False
    proposals: list[dict] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    critique: list[dict] = field(default_factory=list)
    answer: str = ""
    cost_rows: list[dict] = field(default_factory=list)
    degraded: bool = False

    @property
    def accepted_count(self) -> int:
        return len(self.proposals)


def route_turn(question: str, state: GraphState) -> tuple[frozenset[Cap], bool]:
    """⭐ Tier 0. Free, and OFF the latency path.

    Most turns do not need planning; deciding that requires no model. The
    reason the Planner lost its round-trip is LATENCY, not cost — it was
    already the cheap tier, but it sat in front of every turn including the
    ones that never needed it.
    """
    q = question.lower()
    hard = any(m in q for m in HARD_MARKERS) or len(q.split()) > 25
    caps = {Cap.READ_STRUCTURE, Cap.READ_CONTENT}
    if any(w in q for w in ("earlier", "before", "used to", "week", "changed")):
        caps.add(Cap.READ_TIMELINE)
    if hard:
        caps.add(Cap.READ_FRONTIER)
    return frozenset(caps), hard


def run_turn(state: GraphState, question: str, node_ids: list[str],
             agent: Agent, *, labels: dict[str, str] | None = None,
             roles: dict[str, Role] | None = None,
             budget_usd: float | None = None,
             on_token=None) -> Turn:
    """The turn protocol, with display decoupled from acceptance.

    ⭐ Run strictly in sequence this is three model round-trips before the
    student sees a word — 10-20 seconds at a bench. The Critic does not write
    the prose, so it does not block it: the answer streams, the Critic runs
    alongside, and NOTHING is appended until it returns. The student reads
    early; the graph waits.
    """
    roles = roles or DEFAULT_ROLES
    t = Turn(question=question)
    caps, hard = route_turn(question, state)      # step 0 — free
    t.escalated = hard

    def call(role: Role, payload: dict) -> dict:
        # ⭐ Invariant 3: a fresh, stateless request every time. Nothing from a
        # previous call is threaded in.
        out = agent.run(role, payload, question)
        t.role_calls.append(role.name)
        t.cost_rows.append({
            "role": role.name, "model_tier": role.tier.value,
            "caps": sorted(c.value for c in role.caps),
            "tokens_in": out.get("tokens_in", 0),
            "tokens_out": out.get("tokens_out", 0),
            "escalated": hard, "degraded": t.degraded,
        })
        return out

    def spent() -> float:
        rate = {Tier.T0: 0, Tier.T1A: 0.0001, Tier.T1B: 0.0005,
                Tier.T2: 0.003, Tier.T3: 0.015}
        return sum(r["tokens_in"] / 1000 * rate[Tier(r["model_tier"])]
                   for r in t.cost_rows)

    plan = None
    if hard:
        # ⚠️ `>=`, not `>`. The check runs BEFORE the expensive call, so
        # comparing already-spent against the budget with `>` lets the first
        # frontier-tier call through on a zero budget — the breach is only
        # noticed after the money is gone.
        if budget_usd is not None and spent() >= budget_usd:
            t.degraded = True
        else:
            plan = call(roles["planner"], project_view(
                state, roles["planner"].caps & caps, node_ids, labels))

    # Grounder: the only role that sees document bodies.
    gr = roles["grounder"]
    ground = call(gr, project_view(state, gr.caps & caps, node_ids, labels))
    res = gate(ground.get("proposals", []), gr)
    t.proposals += res.accepted
    t.rejected += res.rejected
    t.answer = ground.get("answer", "")

    if hard and plan is not None and not t.degraded:
        syn = roles["synthesiser"]
        # ⚠️ Structure only — no bodies. This is why merging roles costs MORE.
        sout = call(syn, project_view(state, syn.caps & caps, node_ids))
        sres = gate(sout.get("proposals", []), syn)
        t.proposals += sres.accepted
        t.rejected += sres.rejected
        t.answer = sout.get("answer", t.answer)

    if on_token:                                   # display, before acceptance
        on_token(t.answer)

    # Critic: non-suppressible on any turn producing a conclusion, and run
    # CONCURRENTLY with the streaming above.
    if t.proposals:
        cr = roles["critic"]
        payload = project_view(state, cr.caps & caps, node_ids)
        payload["spans"] = spans_for(state, [p["id"] for p in t.proposals
                                             if "id" in p])
        cout = call(cr, payload)
        prior = {p["id"]: p.get("citation_state") for p in t.proposals
                 if "id" in p}
        cres = gate(cout.get("proposals", []), cr, prior=prior)
        t.critique = cres.accepted
        t.rejected += cres.rejected
    return t
