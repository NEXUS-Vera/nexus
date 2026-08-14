"""Phase 4 — the analyzer. Backend/01 §7."""
from __future__ import annotations

import networkx as nx
import pytest

from conftest import accept, edge, node
from conftest import validate as val_event
from mindgraph.analyzer import (adamic_adar, analyze, centrality, cocitation,
                                communities, contradiction_sweep,
                                crossover_score, crossovers, staleness_sweep,
                                unlinked_mentions)
from mindgraph.graph import to_networkx
from mindgraph.projector import project


@pytest.fixture
def g(led):
    accept(led, [
        node("imp", "Concept", project_id="p1"),
        node("cap", "Concept", project_id="p1"),
        node("ind", "Concept", project_id="p1"),
        node("mcu", "Concept", project_id="p2"),
        node("uart", "Concept", project_id="p2"),
        node("paper", "Source", kind="paper"),
        node("bench", "Artifact", kind="run"),
        node("C1"),
    ], [
        edge("cap", "relates_to", "imp"), edge("ind", "relates_to", "imp"),
        edge("mcu", "relates_to", "uart"),
        edge("paper", "supports", "C1"), edge("bench", "supports", "C1"),
    ])
    return project(led.read()), led


# ── clustering with stable identity ─────────────────────────────────────────

def test_communities_are_internally_connected(g):
    """⚠️ Louvain can emit disconnected communities, and a region drawn around
    one is a lie rendered as a shape. We split them."""
    state, _ = g
    und = to_networkx(state).to_undirected()
    for members in communities(state).values():
        assert nx.is_connected(und.subgraph(members))


def test_community_identity_survives_a_rerun(g):
    """⭐ A region that silently becomes a different region is worse than no
    regions at all."""
    state, led = g
    first = communities(state)
    accept(led, [node("noise", "Concept", project_id="p1")],
           [edge("noise", "relates_to", "imp")])
    second = communities(project(led.read()), previous=first)
    imp_before = next(c for c, m in first.items() if "imp" in m)
    imp_after = next(c for c, m in second.items() if "imp" in m)
    assert imp_before == imp_after          # same region, one new member


def test_communities_are_deterministic(g):
    state, _ = g
    assert {k: sorted(v) for k, v in communities(state).items()} == \
           {k: sorted(v) for k, v in communities(state).items()}


# ── centrality ──────────────────────────────────────────────────────────────

def test_centrality_uses_approximate_betweenness(g):
    """Exact is ~118s at 10k nodes and feeds a RANKING function, not a truth
    claim — so sampling is correct on the merits (Q11)."""
    state, _ = g
    c = centrality(state)
    assert set(c["imp"]) == {"pagerank", "betweenness", "eigenvector"}
    assert c["imp"]["pagerank"] > 0


def test_centrality_is_empty_not_broken_on_an_empty_graph():
    from mindgraph.projector import GraphState
    assert centrality(GraphState()) == {}


# ── the crossover scorer ────────────────────────────────────────────────────

def test_source_to_artifact_scores_high(g):
    """⭐ 'Connects a published claim to your own measurement' is the signal
    nobody else can produce."""
    state, led = g
    accept(led, [], [edge("paper", "relates_to", "bench",
                          confidence="INFERRED", score=0.75)])
    state = project(led.read())
    e = next(e for e in state.edges.values()
             if e.src == "paper" and e.dst == "bench")
    score, why = crossover_score(state, "paper", "bench", e)
    assert score >= 5
    assert any("your own measurement" in w for w in why)


def test_cross_project_edges_score(g):
    state, led = g
    accept(led, [], [edge("imp", "relates_to", "mcu", confidence="INFERRED",
                          score=0.75)])
    state = project(led.read())
    e = next(e for e in state.edges.values()
             if e.src == "imp" and e.dst == "mcu")
    _, why = crossover_score(state, "imp", "mcu", e)
    assert any("two of your projects" in w for w in why)


def test_resolver_noise_is_suppressed(g):
    """⚠️ Label-matched INFERRED edges are resolver pollution, not insight.
    Without this the top of every crossover list is near-duplicates."""
    state, led = g
    accept(led, [], [edge("imp", "same_as", "mcu", confidence="INFERRED",
                          score=0.75,
                          provenance={"actor": "resolver"})])
    state = project(led.read())
    e = next(e for e in state.edges.values() if e.relation.value == "same_as")
    score, _ = crossover_score(state, "imp", "mcu", e)
    assert score <= 2


def test_every_crossover_carries_its_why(g):
    """Never show a connection without the reason it is surprising — that is
    what turns a graph into a mentor."""
    state, led = g
    accept(led, [], [edge("paper", "relates_to", "bench",
                          confidence="INFERRED", score=0.75)])
    for c in crossovers(project(led.read())):
        assert c["why"]


def test_crossovers_dedupe_by_community_pair(g):
    """Without this, one high-betweenness hub dominates every result."""
    state, led = g
    for tgt in ("cap", "ind", "imp"):
        accept(led, [], [edge("paper", "relates_to", tgt,
                              confidence="INFERRED", score=0.75)])
    out = crossovers(project(led.read()))
    pairs = [(c["src"], c["dst"]) for c in out]
    assert len(pairs) == len(set(pairs))
    assert len(out) <= 5


# ── cheap proposal sources ──────────────────────────────────────────────────

def test_unlinked_mentions_need_no_model(g):
    """One string scan against the alias table — the cheapest proposal source
    in the system."""
    state, led = g
    accept(led, [node("n1", "Note")])
    state = project(led.read())
    out = unlinked_mentions(
        state, {"imp": "skin impedance", "cap": "capacitance"},
        {"n1": "the skin impedance reading drifted overnight"})
    assert any(m["dst"] == "imp" and m["src"] == "n1" for m in out)
    assert all(m["score"] == 0.75 for m in out)


def test_unlinked_mentions_skip_what_is_already_linked(g):
    state, led = g
    accept(led, [node("n1", "Note")], [edge("n1", "relates_to", "imp")])
    state = project(led.read())
    out = unlinked_mentions(state, {"imp": "skin impedance"},
                            {"n1": "skin impedance again"})
    assert out == []


def test_cocitation_weights_proximity(g):
    """Concepts thought about TOGETHER — complementary to Adamic-Adar's
    purely structural view."""
    state, _ = g
    out = cocitation(state, {"n1": ["imp", "cap"], "n2": ["imp", "cap"]},
                     same_sentence={"n1": [["imp", "cap"]]})
    assert out[0]["weight"] == 5.0          # 3.0 same sentence + 2.0 same note


def test_adamic_adar_predicts_missing_links(g):
    """The evaluation BASELINE. If retrieval cannot beat a 2003 algorithm,
    the graph is not earning its cost."""
    state, _ = g
    preds = adamic_adar(state)
    assert any({p["a"], p["b"]} == {"cap", "ind"} for p in preds)


# ── nightly sweeps ──────────────────────────────────────────────────────────

def test_contradiction_sweep_finds_contested_nodes(g):
    """⭐ The primary catch for auto-accepted inferences (Q1)."""
    state, led = g
    accept(led, [], [edge("paper", "contradicts", "C1")])
    out = contradiction_sweep(project(led.read()))
    conflict = next(c for c in out if c.get("node") == "C1")
    assert conflict["kind"] == "CONFLICT"
    assert "paper" in conflict["against"]


def test_contradiction_sweep_reports_unresolved_ambiguity(g):
    state, led = g
    accept(led, [], [edge("cap", "supports", "ind", confidence="AMBIGUOUS",
                          score=0.3)])
    out = contradiction_sweep(project(led.read()))
    assert any(c["kind"] == "AMBIGUOUS_UNRESOLVED" for c in out)


def test_staleness_sweep_flags_later_dependencies(led):
    accept(led, [node("C1")])
    for i in range(60):
        accept(led, [node(f"pad{i}")])
    accept(led, [node("late", "Artifact")], [edge("late", "supports", "C1")])
    out = staleness_sweep(project(led.read()))
    assert any(s["node"] == "C1" and "late" in s["changed_since"] for s in out)


# ── the sidecar ─────────────────────────────────────────────────────────────

def test_analyze_produces_a_disposable_sidecar(g):
    """Derived, disposable, recomputable — deleting it costs CPU, never data."""
    state, _ = g
    sc = analyze(state).as_dict()
    assert set(sc) == {"communities", "centrality", "crossovers",
                       "predictions", "contradictions", "stale"}
    assert sc["centrality"]


def test_analyze_is_deterministic(g):
    state, _ = g
    import json
    a = json.dumps(analyze(state).as_dict(), sort_keys=True)
    b = json.dumps(analyze(state).as_dict(), sort_keys=True)
    assert a == b


def test_analyze_never_touches_the_ledger(g):
    """It is off the request path and writes only sidecars."""
    state, led = g
    before = led.head()
    analyze(state)
    assert led.head() == before
