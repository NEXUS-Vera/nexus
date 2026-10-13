"""The agent layer. Backend/05.

The tests that matter here are the ones proving an agent CANNOT do something,
because that is the whole contract.
"""
from __future__ import annotations

import pytest
from conftest import accept, edge, node
from mindgraph.agents import (
    DEFAULT_ROLES,
    NEVER_GRANTED,
    Cap,
    Role,
    Tier,
    gate,
    project_view,
    route_turn,
    run_turn,
    spans_for,
)
from mindgraph.projector import project
from mindgraph.schema import Confidence


@pytest.fixture
def g(led):
    accept(led, [node("S1", "Source", kind="paper", label="Chen 2019"),
                 node("C1", label="47 kOhm means hydrated"),
                 node("R1", "Artifact", kind="run", label="forearm sweep")],
           [edge("S1", "supports", "C1", eid="e1",
                 provenance={"span": "chen.pdf:p3", "citation_state":
                             "present_relevant"}),
            edge("R1", "supports", "C1", eid="e2")])
    return project(led.read())


LABELS = {"S1": "Chen 2019", "C1": "47 kOhm means hydrated",
          "R1": "forearm sweep"}
IDS = ["S1", "C1", "R1"]


class FakeAgent:
    """Emits whatever it is told to. The point is that the GATE decides."""

    def __init__(self, by_role: dict[str, dict] | None = None) -> None:
        self.by_role = by_role or {}
        self.seen: list[tuple[str, dict]] = []

    def run(self, role: Role, payload: dict, question: str) -> dict:
        self.seen.append((role.name, payload))
        return {**{"answer": f"{role.name} says so", "tokens_in": 100,
                   "tokens_out": 20, "proposals": []},
                **self.by_role.get(role.name, {})}


# ── project_view: the security model, in one function ───────────────────────

def test_structure_only_roles_never_see_bodies(g):
    """⭐ And this is also the cost filter — it is why the frontier-tier call
    never carries the content payload."""
    v = project_view(g, frozenset({Cap.READ_STRUCTURE}), IDS, LABELS)
    assert v["nodes"] and all("label" not in n for n in v["nodes"])
    assert all("span" not in e for e in v["edges"])


def test_read_content_sees_labels_and_spans(g):
    v = project_view(g, frozenset({Cap.READ_STRUCTURE, Cap.READ_CONTENT}),
                     IDS, LABELS)
    assert any(n.get("label") == "Chen 2019" for n in v["nodes"])
    assert any(e.get("span") == "chen.pdf:p3" for e in v["edges"])


def test_no_read_structure_sees_nothing(g):
    assert project_view(g, frozenset(), IDS, LABELS) == {"nodes": [], "edges": []}


def test_deprecated_edges_are_not_shown(g):
    from mindgraph.cascade import cascade_retract
    cascade_retract(g, "R1", seq=99)
    v = project_view(g, frozenset({Cap.READ_STRUCTURE}), IDS)
    assert not any(e["id"] == "e2" for e in v["edges"])


def test_verify_span_returns_only_cited_spans(g):
    assert spans_for(g, ["e1"]) == {"e1": "chen.pdf:p3"}
    assert spans_for(g, ["nope"]) == {}


# ── the gate: what an agent CANNOT do ───────────────────────────────────────

def _p(**kw):
    return {"id": "p1", "confidence": "INFERRED", "score": 0.85,
            "basis": ["C1"], **kw}


def test_a_structure_only_role_cannot_claim_extracted(g):
    """⭐ It has never seen a source, so it cannot say something was stated in
    one. A prompt is a request; a capability check is a fact about the call."""
    r = gate([_p(confidence="EXTRACTED", score=1.0, span="x:1",
                 citation_state="present_relevant")],
             DEFAULT_ROLES["synthesiser"])
    assert not r.accepted
    assert "READ_CONTENT" in r.rejected[0].reason


def test_the_grounder_may_claim_extracted(g):
    r = gate([_p(confidence="EXTRACTED", score=1.0, span="x:1",
                 citation_state="present_relevant")],
             DEFAULT_ROLES["grounder"])
    assert len(r.accepted) == 1


def test_extracted_without_a_span_is_rejected(g):
    r = gate([_p(confidence="EXTRACTED", score=1.0,
                 citation_state="present_relevant")],
             DEFAULT_ROLES["grounder"])
    assert "span" in r.rejected[0].reason


def test_a_planner_cannot_propose_anything(g):
    """It decides what happens; it does not get to decide what is true."""
    r = gate([_p()], DEFAULT_ROLES["planner"])
    assert "cannot propose" in r.rejected[0].reason


def test_validate_and_retract_are_never_granted():
    for role in DEFAULT_ROLES.values():
        assert not (role.caps & NEVER_GRANTED)


def test_no_basis_is_rejected(g):
    """An agent that cannot name its basis has produced an unjustified claim."""
    p = _p()
    p.pop("basis")
    assert "basis" in gate([p], DEFAULT_ROLES["grounder"]).rejected[0].reason


def test_a_weak_citation_is_capped_not_dropped(g):
    r = gate([_p(score=0.95, citation_state="present_weak")],
             DEFAULT_ROLES["grounder"])
    assert r.accepted[0]["score"] == 0.75 and r.downgrades


def test_wrong_source_becomes_ambiguous(g):
    r = gate([_p(score=0.95, citation_state="wrong_source")],
             DEFAULT_ROLES["grounder"])
    assert r.accepted[0]["confidence"] == Confidence.AMBIGUOUS.value


def test_the_critic_may_downgrade_a_citation(g):
    r = gate([_p(citation_state="present_weak", score=0.75)],
             DEFAULT_ROLES["critic"], prior={"p1": "present_relevant"})
    assert len(r.accepted) == 1


def test_the_critic_may_never_raise_one(g):
    """⚠️ A Critic that could RAISE a citation would become a second,
    unaccountable Grounder."""
    r = gate([_p(citation_state="present_relevant", score=0.95)],
             DEFAULT_ROLES["critic"], prior={"p1": "missing"})
    assert not r.accepted
    assert "never raise" in r.rejected[0].reason


# ── the router: free, and off the latency path ──────────────────────────────

def test_a_simple_turn_does_not_escalate(g):
    caps, hard = route_turn("what is the impedance of C1?", g)
    assert not hard and Cap.READ_STRUCTURE in caps


def test_a_hard_turn_escalates(g):
    _, hard = route_turn("why does my whole hydration hypothesis keep failing?", g)
    assert hard


def test_timeline_access_is_only_granted_when_asked_for(g):
    assert Cap.READ_TIMELINE not in route_turn("what is X?", g)[0]
    assert Cap.READ_TIMELINE in route_turn("what did I conclude earlier?", g)[0]


# ── the turn ────────────────────────────────────────────────────────────────

def test_a_simple_turn_never_wakes_opus(g):
    """⭐ The cheap path is the default; the expensive path is opt-in, decided
    by a free heuristic rather than by a model deciding what to spend."""
    a = FakeAgent()
    t = run_turn(g, "what is C1?", IDS, a, labels=LABELS)
    tiers = {r["model_tier"] for r in t.cost_rows}
    assert Tier.T3.value not in tiers
    assert "planner" not in t.role_calls


def test_a_hard_turn_plans_then_executes(g):
    a = FakeAgent({"synthesiser": {"proposals": [_p()]}})
    t = run_turn(g, "why does my whole hypothesis keep failing across projects?",
                 IDS, a, labels=LABELS)
    assert t.escalated
    assert t.role_calls[0] == "planner"
    assert "synthesiser" in t.role_calls


def test_the_synthesiser_call_carries_no_bodies(g):
    """The capability filter is the cost filter, proven at the call site."""
    a = FakeAgent({"synthesiser": {"proposals": [_p()]}})
    run_turn(g, "why does everything keep failing across projects?", IDS, a,
             labels=LABELS)
    payloads = {name: p for name, p in a.seen}
    assert any("label" in n for n in payloads["grounder"]["nodes"])
    assert all("label" not in n for n in payloads["synthesiser"]["nodes"])


def test_the_critic_is_non_suppressible_on_a_conclusion(g):
    a = FakeAgent({"grounder": {"proposals": [_p()]}})
    t = run_turn(g, "what is C1?", IDS, a, labels=LABELS)
    assert "critic" in t.role_calls


def test_no_conclusion_means_no_critic(g):
    a = FakeAgent()
    assert "critic" not in run_turn(g, "what is C1?", IDS, a).role_calls


def test_the_critic_receives_only_already_cited_spans(g):
    a = FakeAgent({"grounder": {"proposals": [_p(id="e1")]}})
    run_turn(g, "what is C1?", IDS, a, labels=LABELS)
    critic_payload = [p for name, p in a.seen if name == "critic"][0]
    assert critic_payload["spans"] == {"e1": "chen.pdf:p3"}
    assert all("label" not in n for n in critic_payload["nodes"])


def test_the_answer_streams_before_the_critic_runs(g):
    """⭐ Display and acceptance are decoupled. The student reads early; the
    graph waits."""
    order: list[str] = []
    a = FakeAgent({"grounder": {"proposals": [_p()]}})
    real = a.run
    def spy(role, payload, q):
        order.append(f"call:{role.name}")
        return real(role, payload, q)
    a.run = spy
    run_turn(g, "what is C1?", IDS, a, labels=LABELS,
             on_token=lambda s: order.append("stream"))
    assert order.index("stream") < order.index("call:critic")


def test_every_call_gets_a_fresh_payload(g):
    """Invariant 3 — nothing from a previous call is threaded into the next."""
    a = FakeAgent({"grounder": {"proposals": [_p()]}})
    run_turn(g, "what is C1?", IDS, a, labels=LABELS)
    assert len({id(p) for _, p in a.seen}) == len(a.seen)


def test_a_budget_breach_degrades_visibly(g):
    """⚠️ A cheaper answer presented identically to an expensive one is the one
    failure a student cannot detect — so `degraded` is a recorded field."""
    a = FakeAgent({"synthesiser": {"proposals": [_p()]}})
    t = run_turn(g, "why does everything keep failing across projects?", IDS, a,
                 labels=LABELS, budget_usd=0.0)
    assert t.degraded
    assert "planner" not in t.role_calls
    assert any(r["degraded"] for r in t.cost_rows)


def test_cost_rows_record_the_tier(g):
    a = FakeAgent()
    t = run_turn(g, "what is C1?", IDS, a, labels=LABELS)
    assert t.cost_rows and all(
        {"role", "model_tier", "tokens_in", "escalated"} <= set(r)
        for r in t.cost_rows)
