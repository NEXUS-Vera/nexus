"""Phase 3 — retrieval, ranking, the Graph API. Backend/01 §6, Backend/07 §5."""

from __future__ import annotations

import pytest
from conftest import accept, edge, node
from conftest import validate as val_event
from mindgraph.projector import project
from mindgraph.retrieve import (
    K_COLD,
    K_UI,
    cap,
    explain,
    known_set,
    lexical_seeds,
    maturity,
    path,
    query,
    seed,
    timeline,
    weights,
)


@pytest.fixture
def g_and_labels(led):
    """A small embedded-systems graph with a prerequisite chain."""
    accept(
        led,
        [
            node("imp", "Concept", project_id="p1"),
            node("cap", "Concept", project_id="p1"),
            node("ind", "Concept", project_id="p1"),
            node("bio", "Concept", project_id="p1"),
            node("noise", "Concept", project_id="p1"),
            node("R1", "Artifact", kind="run"),
            node("C1"),
        ],
        [
            edge("cap", "requires", "imp"),
            edge("ind", "requires", "imp"),
            edge("imp", "requires", "bio"),
            edge("R1", "supports", "C1"),
            edge("C1", "relates_to", "imp"),
            edge("noise", "relates_to", "imp"),
        ],
    )
    val_event(led, "R1", ["C1"])
    labels = {
        "imp": "skin impedance",
        "cap": "capacitance",
        "ind": "inductance",
        "bio": "bioimpedance",
        "noise": "electronic noise",
        "R1": "forearm sweep",
        "C1": "hydration claim",
    }
    return project(led.read()), labels, led


# ── ① seed ──────────────────────────────────────────────────────────────────


def test_lexical_seeding_finds_the_obvious_node(g_and_labels):
    g, labels, _ = g_and_labels
    assert lexical_seeds(g, "skin impedance", labels)[0][0] == "imp"


def test_seeding_survives_with_no_embedder(g_and_labels):
    """No key, no embeddings — retrieval degrades to the lexical half of the
    hybrid seed rather than failing."""
    g, labels, _ = g_and_labels
    assert seed(g, "impedance", labels) != []


def test_unmatched_query_returns_nothing_rather_than_noise(g_and_labels):
    g, labels, _ = g_and_labels
    assert query(g, "quantum chromodynamics", labels) == []


# ── ② expand ────────────────────────────────────────────────────────────────


def test_expansion_reaches_beyond_the_seed(g_and_labels):
    """The whole argument for PPR: things CONNECTED to the hit, including
    those whose wording shares nothing with the query."""
    g, labels, _ = g_and_labels
    ids = {r.id for r in query(g, "skin impedance", labels)}
    assert "imp" in ids
    assert {"cap", "ind"} & ids  # reached by structure, not by text


def test_every_result_carries_a_printable_path(g_and_labels):
    """Provenance is why this is PPR and not a vector index."""
    g, labels, _ = g_and_labels
    for r in query(g, "skin impedance", labels):
        assert r.path and r.path[-1] == r.id


# ── ③ rank ──────────────────────────────────────────────────────────────────


def test_weights_ramp_with_graph_age(g_and_labels):
    """On day one salience and outcome are empty, so weighting them weights
    noise. Learnability dominates because it is the only signal that exists."""
    g, _, _ = g_and_labels
    w = weights(g)
    assert w["salience"] < 0.05 and w["outcome"] < 0.05
    assert w["learnability"] > w["centrality"]

    g.last_seq = 500
    mature = weights(g)
    assert mature["salience"] > w["salience"]
    assert mature["learnability"] < w["learnability"]
    assert maturity(g) == 1.0


def test_known_set_requires_established_not_merely_supported(g_and_labels):
    """One lucky measurement must not mark something learned."""
    g, _, led = g_and_labels
    assert known_set(g) == set()  # C1 has corroboration 1
    accept(led, [node("R2", "Artifact", kind="run")], [edge("R2", "supports", "C1")])
    val_event(led, "R2", ["C1"])
    assert "C1" in known_set(project(led.read()))


def test_learnability_tracks_the_outer_fringe(g_and_labels):
    g, labels, _ = g_and_labels
    scores = {r.id: r.doi["learnability"] for r in query(g, "impedance", labels)}
    assert scores.get("bio", 0) == 0.0  # requires imp, which is undemonstrated


def test_staleness_penalises(g_and_labels):
    g, labels, _ = g_and_labels
    before = {r.id: r.score for r in query(g, "impedance", labels)}
    g.nodes["noise"].quarantined = True
    after = {r.id: r.score for r in query(g, "impedance", labels)}
    assert after["noise"] < before["noise"]


def test_outcome_rewards_things_that_worked(g_and_labels):
    g, labels, _ = g_and_labels
    r = next(x for x in query(g, "hydration claim", labels) if x.id == "C1")
    assert r.doi["outcome"] == 1.0  # its artifact matched


def test_ranking_is_deterministic(g_and_labels):
    g, labels, _ = g_and_labels
    a = [(r.id, r.score) for r in query(g, "impedance", labels)]
    b = [(r.id, r.score) for r in query(g, "impedance", labels)]
    assert a == b


# ── ④ cap ───────────────────────────────────────────────────────────────────


def test_cold_start_caps_tighter(g_and_labels):
    g, _, _ = g_and_labels
    fake = [type("R", (), {"id": str(i), "score": 0.0})() for i in range(200)]
    assert len(cap(fake, g)) == K_COLD
    g.last_seq = 10_000
    assert len(cap(fake, g)) == K_UI


def test_the_cap_is_never_exceeded(g_and_labels):
    g, labels, _ = g_and_labels
    assert len(query(g, "impedance", labels, k=2)) <= 2


def test_lenses_change_the_answer(led):
    """Same graph, same question, different angle -> different answer.

    The lens has to act on a node whose out-edges are a MIX of relations —
    see test_a_lens_cancels_where_relations_are_uniform for why.
    """
    accept(
        led,
        [
            node("hub", "Concept", project_id="p1"),
            node("prereq", "Concept", project_id="p1"),
            node("paper", "Source", kind="paper"),
            node("bench", "Artifact", kind="run"),
        ],
        [
            edge("hub", "requires", "prereq"),  # the `learn` lens boosts this
            edge("hub", "cites", "paper"),  # `writeup` boosts this
            edge("hub", "measured_by", "bench"),
        ],
    )  # `debug` boosts this
    g = project(led.read())
    labels = {
        "hub": "skin impedance",
        "prereq": "capacitance",
        "paper": "Chen 2019",
        "bench": "forearm sweep",
    }
    learn = [(r.id, r.score) for r in query(g, "skin impedance", labels, lens="learn")]
    debug = [(r.id, r.score) for r in query(g, "skin impedance", labels, lens="debug")]
    assert learn and debug and learn != debug


def test_a_lens_cancels_where_relations_are_uniform(led):
    """⚠️ Known and correct, not a bug — worth pinning so nobody "fixes" it.

    PageRank normalises a node's outgoing weights, so multiplying EVERY
    out-edge of a node by the same lens boost leaves the transition
    probabilities identical. A lens therefore reorders by relation MIX, not by
    relation presence: in a region that is all `requires` edges, every lens
    returns the same ranking.
    """
    accept(
        led,
        [
            node("a", "Concept", project_id="p1"),
            node("b", "Concept", project_id="p1"),
            node("c", "Concept", project_id="p1"),
        ],
        [edge("a", "requires", "b"), edge("b", "requires", "c")],
    )
    g = project(led.read())
    labels = {"a": "capacitance", "b": "impedance", "c": "bioimpedance"}
    learn = [(r.id, r.score) for r in query(g, "impedance", labels, lens="learn")]
    none = [(r.id, r.score) for r in query(g, "impedance", labels)]
    assert learn == none


# ── the Graph API ───────────────────────────────────────────────────────────


def test_explain_answers_why_do_i_believe_this(g_and_labels):
    g, _, _ = g_and_labels
    e = explain(g, "C1")
    assert e["supported_by"] == ["R1"]
    assert e["corroboration"] == 1 and e["strength"] == "tentative"


def test_explain_separates_retracted_support(g_and_labels):
    """⭐ A conclusion that LOST its evidence is not the same as one that never
    had any, and explain() has to say which."""
    from mindgraph.cascade import cascade_retract

    g, _, _ = g_and_labels
    cascade_retract(g, "R1", seq=99)
    e = explain(g, "C1")
    assert e["supported_by"] == [] and e["retracted_support"] == ["R1"]
    assert e["support"] == "unsupported"


def test_path_is_printable(g_and_labels):
    g, _, _ = g_and_labels
    assert path(g, "cap", "bio")[0] == "cap"
    assert path(g, "cap", "nonexistent") == []


def test_timeline_rebuilds_a_past_graph(g_and_labels):
    """'What did I believe in week 2?' is a replay, not a feature."""
    g, _, led = g_and_labels
    early = timeline(None, led, at_seq=1)
    assert "C1" in early.nodes
    assert early.nodes["C1"].corroboration == 0  # before the validation
    assert g.nodes["C1"].corroboration == 1
