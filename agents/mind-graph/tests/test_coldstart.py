"""Phase 6 — cold start. Backend/07 §1."""

from __future__ import annotations

import pytest
from mindgraph.artifact import Session
from mindgraph.coldstart import (
    NODE_CAP,
    decompose,
    exposure_marks,
    is_vague,
    seed_project,
)
from mindgraph.crypto import KeyStore
from mindgraph.frontier import frontier, knowledge_state, outer_fringe
from mindgraph.ledger import Ledger, canonical
from mindgraph.schema import Origin, Scope, Support
from mindgraph.skeleton import load, parse

Q = "Can skin impedance track hydration to within 10 percent?"


@pytest.fixture
def s(tmp_path):
    sess = Session(user="u1", ledger=Ledger(tmp_path / "l.db"), keys=KeyStore(tmp_path / "k.json"))
    sess.keys.create("u1")
    yield sess
    sess.close()


@pytest.fixture
def sk():
    return load()


# ── the skeleton ────────────────────────────────────────────────────────────


def test_the_skeleton_loads(sk):
    # 213 (v0, embedded) + robotics and life-sciences packs (v0.2)
    assert len(sk) == 278
    assert sk.concepts["impedance"].requires == ("capacitance", "inductance", "complex_numbers")


def test_closure_pulls_prerequisites_two_levels_up(sk):
    """⭐ This is what makes the frontier computable at t=0."""
    out = sk.closure({"impedance"}, levels=2)
    assert {"capacitance", "inductance", "complex_numbers"} <= out
    assert "charge_current_voltage" in out  # second level
    assert "algebra_manipulation" in out


def test_match_finds_concepts_by_label_and_alias(sk):
    ids = {cid for cid, _ in sk.match("skin impedance and bioimpedance")}
    assert "impedance" in ids and "bioimpedance" in ids


def test_parse_survives_a_malformed_row():
    assert len(parse("- {label: no id here}\n")) == 0


# ── the guard ───────────────────────────────────────────────────────────────


def test_a_vague_question_is_flagged():
    """⚠️ "Build a robot" produces a generic decomposition and a useless graph.
    "How will you know it worked?" is the fix, asked at onboarding."""
    assert is_vague("build a robot")
    assert not is_vague(Q)


def test_decomposition_never_returns_nothing():
    """No endpoint: worse than a model's, but never empty."""
    subs = decompose(Q, llm=None)
    assert 3 <= len(subs) <= 6


# ── the resulting graph ─────────────────────────────────────────────────────


def test_the_graph_is_never_empty(s):
    cs = seed_project(s, Q)
    g = s.state()
    assert len(g.nodes) > 10
    assert cs.matched


def test_the_node_cap_holds(s):
    """Half the comprehension limit, deliberately."""
    cs = seed_project(s, Q)
    assert len(s.state().nodes) <= NODE_CAP
    assert cs.capped >= 0


def test_nothing_is_validated_at_t_zero(s):
    """⭐ Correct, not a deficiency — the first screen shows what you do NOT
    know yet."""
    seed_project(s, Q)
    g = s.state()
    assert knowledge_state(g) == set()
    assert all(n.support is not Support.SUPPORTED for n in g.nodes.values())


def test_the_frontier_is_computable_immediately(s):
    """The whole point of seeding the requires-closure."""
    seed_project(s, Q)
    g = s.state()
    assert outer_fringe(g)
    acts = frontier(g, limit=3)
    assert acts and all(a.why for a in acts)


def test_curated_concepts_are_global_by_construction(s):
    """Q4: curated concepts carry no project_id and never need promoting."""
    seed_project(s, Q)
    concepts = [n for n in s.state().nodes.values() if n.type.value == "Concept"]
    assert concepts
    for c in concepts:
        assert c.scope is Scope.GLOBAL
        assert c.origin is Origin.CURATED
        assert c.project_id is None
        assert c.external_ids.get("skeleton")


def test_the_root_question_is_project_scoped(s):
    cs = seed_project(s, Q)
    assert s.state().nodes[cs.root].project_id == cs.project_id


def test_no_skeleton_match_degrades_instead_of_failing(s):
    """⚠️ A student outside embedded systems still gets a graph — and the
    count of these is the honest measure of when to fund a second skeleton."""
    cs = seed_project(s, "Can I improve sonnet meter detection accuracy by 10 percent?")
    assert cs.subquestions
    assert len(s.state().nodes) >= 4


# ── the transcript is a prior, not a state ─────────────────────────────────


def test_exposure_never_becomes_knowledge(s):
    """⚠️ A passed course is evidence of EXPOSURE, not knowledge. Structurally
    prevented: it writes an annotation, never a `supports` edge."""
    cs = seed_project(s, Q, transcript="capacitance inductance complex numbers")
    assert cs.exposures
    g = s.state()
    assert exposure_marks(s) == set(cs.exposures)
    assert knowledge_state(g) == set()
    for nid in cs.exposures:
        assert g.nodes[nid].support is not Support.SUPPORTED


# ── hygiene ─────────────────────────────────────────────────────────────────


def test_question_text_never_reaches_the_plaintext_half(s):
    seed_project(s, Q)
    for e in s.ledger.read():
        assert "hydration" not in canonical(e.structural)


def test_cold_start_replays_deterministically(s):
    from mindgraph.projector import project, state_hash

    seed_project(s, Q)
    assert state_hash(project(s.ledger.read())) == state_hash(project(s.ledger.read()))
    assert s.ledger.verify_chain()


def test_no_concept_enters_with_dangling_prerequisites(s, sk):
    """⚠️ The outer fringe asks "are all prerequisites known?" — and a
    prerequisite that was never seeded has no edge, so the check passes
    VACUOUSLY. A concept then presents as ready to learn when the graph simply
    cannot see what it depends on: confidently, invisibly wrong.

    Before the fix, `sensor_interfacing` appeared on a day-one frontier with
    `adc` and `i2c` nowhere in the graph.
    """
    seed_project(s, Q)
    g = s.state()
    present = {
        n.external_ids["skeleton"] for n in g.nodes.values() if n.external_ids.get("skeleton")
    }
    for cid in present:
        missing = [p for p in sk.concepts[cid].requires if p not in present]
        assert not missing, f"{cid} seeded without prerequisites {missing}"


def test_the_fringe_only_contains_genuine_roots(s, sk):
    seed_project(s, Q)
    g = s.state()
    for nid in outer_fringe(g):
        cid = g.nodes[nid].external_ids.get("skeleton")
        if cid:
            assert not sk.concepts[cid].requires


def test_matched_reports_what_was_seeded_not_what_was_hit(s, sk):
    """⚠️ A question can hit the skeleton and still seed nothing once the
    prerequisite-closed filter and the 25-node cap have run. Reporting the hit
    leaves the student with no lattice AND no warning — which reads as broken
    rather than out of scope."""
    cs = seed_project(s, "Can electrode drift stay under 2 percent over 8 hours?")
    assert cs.matched == bool(cs.concepts)


# ── v0.2: does the frontier reach the other two verticals? ──────────────────


def test_every_named_vertical_seeds(sk):
    """⚠️ Measured before the packs existed: "I want to build a robot arm"
    matched ZERO concepts. A cold start that matches nothing recommends
    nothing, which is the worst possible first screen — and embedded was the
    only vertical that worked.

    ⭐ Asserted on the SEEDED GRAPH, not the raw match count. Two precise
    matches plus their prerequisite closure is a better first screen than six
    loose ones, so counting matches would reward the wrong behaviour.
    """
    import tempfile
    from pathlib import Path

    from mindgraph.artifact import Session
    from mindgraph.coldstart import seed_project

    for q in (
        "I want to build a robot arm that picks up objects within 5 mm",
        "Can a ROS lidar robot avoid obstacles at 1 m/s?",
        "Does my ELISA detect the antigen below 10 ng/mL?",
        "Can I detect protein binding with a quartz crystal microbalance?",
        "Can skin impedance track hydration to within 10 percent?",
    ):
        with tempfile.TemporaryDirectory() as tmp:
            s = Session.open("v", Path(tmp))
            cs = seed_project(s, q)
            n = len(s.state().nodes)
            s.close()
        assert cs.matched, q
        assert n >= 8, f"{q} seeded only {n} nodes"


def test_the_matcher_refuses_nonsense(sk):
    """⭐ A matcher that matches everything is worse than one that matches
    nothing — it seeds the graph with noise the student then has to disprove."""
    assert sk.match("what should I cook for dinner") == []


def test_short_acronyms_need_their_capitals(sk):
    """⚠️ Real false positive: `CAN bus` matched *"**Can** a ROS lidar robot"*
    on the English verb. Short aliases only count when actually written in
    caps."""
    assert not any(c == "can_bus" for c, _ in sk.match("Can a robot avoid this?"))
    assert any(c == "can_bus" for c, _ in sk.match("Is CAN bus fast enough?"))


def test_prerequisites_all_resolve_and_stay_acyclic(sk):
    """⚠️ A dangling `requires` silently drops a node from the closure, so the
    frontier recommends a concept whose prerequisite it never showed you."""
    import networkx as nx

    g = nx.DiGraph()
    for c in sk.concepts.values():
        g.add_node(c.id)
        for r in c.requires:
            assert r in sk.concepts, f"{c.id} requires missing {r}"
            g.add_edge(r, c.id)
    assert nx.is_directed_acyclic_graph(g)
