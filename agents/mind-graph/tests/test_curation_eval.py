"""Structuring nudge, promotion, hyperedges, export, and the eval harness."""
from __future__ import annotations

import json

import pytest
from conftest import accept, edge, node
from mindgraph.artifact import Session
from mindgraph.crypto import KeyStore
from mindgraph.curation import (
    MAX_REFUSALS,
    export,
    joint_support,
    promote_concepts,
    refuse_nudge,
    structuring_nudge,
)
from mindgraph.evaluation import (
    Prediction,
    calibration_error,
    cost_per_accepted,
    evaluate_prereg,
    extraction_quality,
    frontier_quality,
    interval_coverage,
    ndcg,
    reliability_curve,
    retrieval_vs_baseline,
)
from mindgraph.ledger import Ledger
from mindgraph.projector import project
from mindgraph.schema import Origin, Scope


@pytest.fixture
def s(tmp_path):
    sess = Session(user="u1", ledger=Ledger(tmp_path / "l.db"),
                   keys=KeyStore(tmp_path / "k.json"))
    sess.keys.create("u1")
    yield sess
    sess.close()


# ── the structuring nudge (Q3) ──────────────────────────────────────────────

def test_a_healthy_graph_is_not_nudged(s):
    accept(s.ledger, [node("C1"), node("C2"), node("C3"), node("n1", "Note")])
    assert not structuring_nudge(s.state()).triggered


def test_note_drift_triggers_an_offer(s):
    """⚠️ A graph of Notes has none of the differentiators — we'd be Obsidian
    with extra steps."""
    accept(s.ledger, [node(f"n{i}", "Note") for i in range(8)] + [node("C1")])
    nudge = structuring_nudge(s.state())
    assert nudge.triggered and nudge.ratio > 0.4
    assert len(nudge.outstanding) == 8


def test_a_note_that_resists_twice_is_left_alone_permanently(s):
    """⭐ Asking a third time is how the feature gets turned off."""
    accept(s.ledger, [node(f"n{i}", "Note") for i in range(8)] + [node("C1")])
    ids = structuring_nudge(s.state()).outstanding
    for _ in range(MAX_REFUSALS):
        refuse_nudge(s, ids)
    assert structuring_nudge(s.state()).outstanding == []


def test_the_nudge_is_an_offer_not_a_gate(s):
    """Refusing changes nothing about the notes themselves."""
    accept(s.ledger, [node(f"n{i}", "Note") for i in range(8)] + [node("C1")])
    before = len(s.state().nodes)
    refuse_nudge(s, structuring_nudge(s.state()).outstanding)
    assert len(s.state().nodes) == before


# ── concept promotion (Q4) ──────────────────────────────────────────────────

def test_a_concept_in_two_projects_is_promoted(s):
    """Extracted concepts start project-scoped and become global on a second
    appearance at >=0.95 — no confirmation step, so no organisational tax."""
    accept(s.ledger, [node("a", "Concept", project_id="p1"),
                      node("b", "Concept", project_id="p2")],
           [edge("a", "same_as", "b", score=0.95)])
    promoted = promote_concepts(s)
    assert promoted
    n = s.state().nodes[promoted[0]]
    assert n.origin is Origin.PROMOTED
    assert n.scope is Scope.GLOBAL and n.project_id is None


def test_one_project_is_not_enough(s):
    accept(s.ledger, [node("a", "Concept", project_id="p1"),
                      node("b", "Concept", project_id="p1")],
           [edge("a", "same_as", "b", score=0.95)])
    assert promote_concepts(s) == []


def test_a_weak_match_does_not_promote(s):
    """The blast radius stays contained: only high-confidence repeats go global."""
    accept(s.ledger, [node("a", "Concept", project_id="p1"),
                      node("b", "Concept", project_id="p2")],
           [edge("a", "same_as", "b", score=0.75)])
    assert promote_concepts(s) == []


# ── hyperedges ──────────────────────────────────────────────────────────────

def test_joint_support_is_one_relationship(s):
    accept(s.ledger, [node("C1"), node("m1", "Artifact"),
                      node("m2", "Artifact"), node("m3", "Artifact")])
    hid = joint_support(s, ["m1", "m2", "m3"], "C1")
    g = s.state()
    assert g.hyper[hid].members == ["m1", "m2", "m3"]
    assert g.hyper[hid].target == "C1"


def test_joint_support_needs_three_members(s):
    accept(s.ledger, [node("C1"), node("m1", "Artifact")])
    with pytest.raises(ValueError, match="3\\+"):
        joint_support(s, ["m1", "m1"], "C1")


def test_a_hyperedge_survives_replay(s):
    accept(s.ledger, [node("C1"), node("m1", "Artifact"),
                      node("m2", "Artifact"), node("m3", "Artifact")])
    joint_support(s, ["m1", "m2", "m3"], "C1")
    from mindgraph.projector import state_hash
    assert state_hash(project(s.ledger.read())) == \
           state_hash(project(s.ledger.read()))


# ── export ──────────────────────────────────────────────────────────────────

def test_the_graph_can_leave_as_data(s):
    """⭐ An Atlas map cannot leave Atlas as data. A graph you cannot get out
    of a product is a graph you do not own."""
    accept(s.ledger, [node("C1"), node("R1", "Artifact")],
           [edge("R1", "supports", "C1")])
    d = json.loads(export(s.state(), {"C1": "hydration claim"}))
    assert d["schema_version"] == 1
    assert any(n["label"] == "hydration claim" for n in d["nodes"])
    assert d["edges"][0]["relation"] == "supports"


def test_export_omits_retracted_material(s):
    from mindgraph.cascade import cascade_retract
    accept(s.ledger, [node("C1"), node("R1", "Artifact")],
           [edge("R1", "supports", "C1")])
    g = s.state()
    cascade_retract(g, "R1", seq=99)
    d = json.loads(export(g))
    assert not any(n["id"] == "R1" for n in d["nodes"])


# ── evaluation ──────────────────────────────────────────────────────────────

def test_extraction_quality_names_the_fabrications():
    r = extraction_quality([("a", "supports", "b"), ("a", "cites", "z")],
                           [("a", "supports", "b")])
    assert r["precision"] == 0.5 and r["recall"] == 1.0
    assert r["fabricated"] == [("a", "cites", "z")]


def test_ndcg_rewards_ranking_not_just_recall():
    assert ndcg(["a", "x", "y"], {"a"}) > ndcg(["x", "y", "a"], {"a"})


def test_retrieval_is_compared_against_a_2003_algorithm(s):
    """⭐ If we cannot beat Adamic-Adar, the graph is not earning its cost."""
    accept(s.ledger, [node("a"), node("b"), node("c"), node("d")],
           [edge("a", "relates_to", "b"), edge("b", "relates_to", "c"),
            edge("a", "relates_to", "d")])
    r = retrieval_vs_baseline(s.state(), ["c", "b"], {"c"}, "a")
    assert set(r) == {"ndcg", "baseline_ndcg", "beats_baseline", "margin"}


def test_frontier_uptake():
    r = frontier_quality(["a", "b", "c"], {"a", "b"}, {"a": 3, "b": 1})
    assert r["uptake"] == pytest.approx(0.6667, abs=1e-3)
    assert r["mean_unblocked"] == 2.0


def test_the_reliability_curve_conditions_on_stated_confidence():
    """⭐ Kills difficulty drift by construction — a harder prediction the
    student was appropriately less sure about does not penalise them."""
    preds = [Prediction(0.9, i < 5) for i in range(10)] + \
            [Prediction(0.5, i < 5) for i in range(10)]
    curve = reliability_curve(preds)
    over = next(b for b in curve if b["stated"] > 0.85)
    assert over["observed"] == 0.5 and over["gap"] < 0     # overconfident
    good = next(b for b in curve if 0.35 <= b["stated"] < 0.7)
    assert abs(good["gap"]) < 0.05                          # well calibrated


def test_a_perfectly_calibrated_student_scores_near_zero():
    preds = [Prediction(0.9, i < 9) for i in range(10)]
    assert calibration_error(preds) < 0.05


def test_interval_coverage_moves_first():
    """Undergraduates land far below nominal — a large gap means a large
    effect size, detectable at much smaller n."""
    r = interval_coverage([(0, 1, 0.5), (0, 1, 2.0), (0, 1, 3.0)])
    assert r["coverage"] == pytest.approx(0.3333, abs=1e-3)
    assert r["shortfall"] > 0.4


def test_the_null_is_pre_registered_and_power_is_checked():
    """⭐ A null is not a failure — calibration is the measurement, not the
    mechanism."""
    before = [Prediction(0.9, i < 5) for i in range(20)]
    after = [Prediction(0.9, i < 9) for i in range(20)]
    r = evaluate_prereg(before, after, n_students=10)
    assert r["decrease"] > 0.05 and r["meets_prereg"]

    underpowered = evaluate_prereg(before[:3], after[:3], n_students=2)
    assert not underpowered["sufficiently_powered"]
    assert not underpowered["meets_prereg"]


def test_cost_is_measured_per_accepted_proposal():
    """⭐ Not per turn — this is the one that says whether the graph is
    earning its keep."""
    rows = [{"model_tier": "opus", "tokens_in": 3000, "tokens_out": 1500},
            {"model_tier": "sonnet", "tokens_in": 8000, "tokens_out": 1500}]
    r = cost_per_accepted(rows, accepted=5)
    assert r["usd_per_accepted"] == round(r["usd"] / 5, 6)
    assert r["by_tier"]["opus"] > r["by_tier"]["sonnet"]   # the driver


def test_zero_accepted_does_not_divide_by_zero():
    assert cost_per_accepted([], accepted=0)["usd_per_accepted"] is None


# ── the correction handler ──────────────────────────────────────────────────

def test_a_correction_coerces_types(s):
    """⚠️ A raw setattr bypasses pydantic, so origin="promoted" lands as a
    STRING and every `is Origin.PROMOTED` downstream quietly fails — the enum
    prints right and behaves wrong."""
    from mindgraph.events import EventType
    accept(s.ledger, [node("a", "Concept", project_id="p1")])
    s.ledger.append("u1", EventType.CORRECTION,
                    {"target": "a", "fields": {"origin": "promoted",
                                               "scope": "global",
                                               "project_id": None}})
    n = s.state().nodes["a"]
    assert n.origin is Origin.PROMOTED and n.scope is Scope.GLOBAL


def test_a_correction_merges_dicts_instead_of_replacing_them(s):
    """Setting one key of labels_at must not erase the rest."""
    from mindgraph.events import EventType
    accept(s.ledger, [node("a", "Concept", project_id="p1",
                           labels_at={"domain": "electrical", "tier": "1"})])
    s.ledger.append("u1", EventType.CORRECTION,
                    {"target": "a", "fields": {"labels_at": {"refusals": "1"}}})
    la = s.state().nodes["a"].labels_at
    assert la == {"domain": "electrical", "tier": "1", "refusals": "1"}


def test_an_invalid_correction_is_refused(s):
    """The ontology still applies after a correction."""
    import pydantic
    from mindgraph.events import EventType
    accept(s.ledger, [node("a", "Concept", project_id="p1")])
    s.ledger.append("u1", EventType.CORRECTION,
                    {"target": "a", "fields": {"scope": "global"}})
    with pytest.raises(pydantic.ValidationError):
        s.state()          # global scope with a project_id is illegal
