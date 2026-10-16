"""Phase 5 — frontier and the Disagreement Engine. Backend/01 §8."""

from __future__ import annotations

import pytest
from conftest import accept, edge, node
from conftest import validate as val_event
from mindgraph.events import EventType
from mindgraph.frontier import (
    dead_end_nodes,
    frontier,
    knowledge_state,
    open_questions,
    outer_fringe,
    resurrected,
    tensions,
)
from mindgraph.projector import project


def _establish(led, concept, tag):
    """Two matching results — the corroboration gate for `established`."""
    accept(
        led,
        [node(f"{tag}1", "Artifact", kind="run"), node(f"{tag}2", "Artifact", kind="run")],
        [edge(f"{tag}1", "supports", concept), edge(f"{tag}2", "supports", concept)],
    )
    val_event(led, f"{tag}1", [concept])
    val_event(led, f"{tag}2", [concept])


@pytest.fixture
def led_kst(led):
    accept(
        led,
        [
            node("cap", "Concept", project_id="p1"),
            node("ind", "Concept", project_id="p1"),
            node("imp", "Concept", project_id="p1"),
            node("bio", "Concept", project_id="p1"),
        ],
        [
            edge("cap", "requires", "imp"),
            edge("ind", "requires", "imp"),
            edge("imp", "requires", "bio"),
        ],
    )
    return led


# ── knowledge state and the outer fringe ────────────────────────────────────


def test_knowledge_needs_established_not_supported(led_kst):
    """⭐ One lucky measurement must not mark a concept learned."""
    accept(led_kst, [node("R1", "Artifact")], [edge("R1", "supports", "cap")])
    val_event(led_kst, "R1", ["cap"])
    assert knowledge_state(project(led_kst.read())) == set()  # corroboration 1
    _establish(led_kst, "cap", "x")
    assert "cap" in knowledge_state(project(led_kst.read()))


def test_outer_fringe_is_exactly_what_is_ready(led_kst):
    _establish(led_kst, "cap", "a")
    _establish(led_kst, "ind", "b")
    g = project(led_kst.read())
    fringe = outer_fringe(g)
    assert "imp" in fringe  # both prerequisites demonstrated
    assert "bio" not in fringe  # blocked on imp
    assert "cap" not in fringe  # already known


def test_roots_are_always_ready(led_kst):
    assert "cap" in outer_fringe(project(led_kst.read()))


def test_open_questions_need_an_answering_claim(led):
    accept(
        led,
        [node("Q1", "Question"), node("Q2", "Question"), node("C1")],
        [edge("C1", "answers", "Q1")],
    )
    assert open_questions(project(led.read())) == ["Q2"]


# ── dead ends ───────────────────────────────────────────────────────────────


def test_the_frontier_never_resuggests_a_dead_end(led_kst):
    """⚠️ Re-suggesting the thing that wasted a student's Tuesday is the
    fastest way to destroy trust in a recommender."""
    g = project(led_kst.read())
    assert "cap" in [a.id for a in frontier(g, limit=10)]
    led_kst.append(
        "user",
        EventType.DEAD_END,
        {"id": "d1", "question": "cap route?", "nodes": ["cap"], "resurrect_if": ["shield"]},
    )
    g2 = project(led_kst.read())
    assert dead_end_nodes(g2) == {"cap"}
    assert "cap" not in [a.id for a in frontier(g2, limit=10)]


def test_a_dead_end_resurrects_when_its_blocker_changes(led_kst):
    """⭐ Nearly free — the justification index already tracks the dependency."""
    led_kst.append(
        "user",
        EventType.DEAD_END,
        {"id": "d1", "question": "400 kHz I2C?", "nodes": ["cap"], "resurrect_if": ["shield"]},
    )
    assert resurrected(project(led_kst.read())) == []
    accept(
        led_kst,
        [node("shield", "Concept", project_id="p1"), node("R9", "Artifact")],
        [edge("R9", "supports", "shield")],
    )
    r = resurrected(project(led_kst.read()))
    assert r and r[0]["unblocked_by"] == ["shield"]
    assert "blocker has changed" in r[0]["why"]


def test_a_resurrection_reaches_the_frontier(led_kst):
    led_kst.append(
        "user",
        EventType.DEAD_END,
        {"id": "d1", "question": "x", "nodes": ["cap"], "resurrect_if": ["shield"]},
    )
    accept(
        led_kst,
        [node("shield", "Concept", project_id="p1"), node("R9", "Artifact")],
        [edge("R9", "supports", "shield")],
    )
    assert any(a.kind == "RESURRECTED" for a in frontier(project(led_kst.read()), limit=10))


# ── the six kinds ───────────────────────────────────────────────────────────


def _kind_of(led, extra_nodes, extra_edges):
    accept(led, extra_nodes, extra_edges)
    t = tensions(project(led.read()))
    return t[0].kind if t else None


def test_check_fires_in_week_one(led):
    """⭐ One measurement and one datasheet is enough. The corroboration gate
    governs what counts as KNOWN; it must not govern what is worth FLAGGING."""
    k = _kind_of(
        led,
        [node("R1", "Artifact", kind="run"), node("S1", "Source"), node("Cm"), node("Cs")],
        [
            edge("R1", "supports", "Cm"),
            edge("S1", "supports", "Cs"),
            edge("Cm", "contradicts", "Cs"),
        ],
    )
    assert k == "CHECK"


def test_two_of_your_own_runs_disagreeing_is_a_conflict(led):
    k = _kind_of(
        led,
        [node("R1", "Artifact"), node("R2", "Artifact"), node("C1"), node("C2")],
        [
            edge("R1", "supports", "C1"),
            edge("R2", "supports", "C2"),
            edge("C1", "contradicts", "C2"),
        ],
    )
    assert k == "CONFLICT"


def test_source_versus_source_is_literature(led):
    k = _kind_of(
        led,
        [node("S1", "Source"), node("S2", "Source"), node("C1"), node("C2")],
        [
            edge("S1", "supports", "C1"),
            edge("S2", "supports", "C2"),
            edge("C1", "contradicts", "C2"),
        ],
    )
    assert k == "LITERATURE"


def test_corroborated_single_method_is_a_boundary(led):
    """Two results, one rig, disagreeing with a source: the source may simply
    not apply in your conditions."""
    accept(
        led,
        [
            node("MTH", "Artifact", kind="method"),
            node("R1", "Artifact"),
            node("R2", "Artifact"),
            node("S1", "Source"),
            node("Cm"),
            node("Cs"),
        ],
        [
            edge("R1", "uses_method_in", "MTH"),
            edge("R2", "uses_method_in", "MTH"),
            edge("R1", "supports", "Cm"),
            edge("R2", "supports", "Cm"),
            edge("S1", "supports", "Cs"),
        ],
    )
    val_event(led, "R1", ["Cm"])
    val_event(led, "R2", ["Cm"])
    accept(led, [], [edge("Cm", "contradicts", "Cs")])
    assert tensions(project(led.read()))[0].kind == "BOUNDARY"


def test_corroborated_across_methods_is_a_finding(led):
    """⭐ Two methods agreeing against the literature — this may be real."""
    accept(
        led,
        [
            node("M1", "Artifact", kind="method"),
            node("M2", "Artifact", kind="method"),
            node("R1", "Artifact"),
            node("R2", "Artifact"),
            node("S1", "Source"),
            node("Cm"),
            node("Cs"),
        ],
        [
            edge("R1", "uses_method_in", "M1"),
            edge("R2", "uses_method_in", "M2"),
            edge("R1", "supports", "Cm"),
            edge("R2", "supports", "Cm"),
            edge("S1", "supports", "Cs"),
        ],
    )
    val_event(led, "R1", ["Cm"])
    val_event(led, "R2", ["Cm"])
    accept(led, [], [edge("Cm", "contradicts", "Cs")])
    t = tensions(project(led.read()))[0]
    assert t.kind == "FINDING"
    assert "may be real" in t.framing


def test_every_live_contradiction_fires(led):
    """The trigger is WIDE. Kind decides framing, never whether it fires."""
    accept(led, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    assert len(tensions(project(led.read()))) == 1


def test_a_retracted_contradiction_stops_firing(led):
    from mindgraph.cascade import cascade_retract

    accept(led, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    g = project(led.read())
    cascade_retract(g, "A", seq=99)
    assert tensions(g) == []


# ── priority, computed separately from kind ─────────────────────────────────


def test_focus_makes_a_tension_p0(led):
    accept(led, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    g = project(led.read())
    assert tensions(g)[0].level != "P0"
    assert tensions(g, focus={"A"})[0].level == "P0"


def test_dismissals_lower_priority(led):
    accept(led, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    g = project(led.read())
    eid = tensions(g)[0].edge
    assert tensions(g, dismissed={eid: 3})[0].priority < tensions(g)[0].priority


def test_findings_outrank_checks(led):
    accept(led, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    g = project(led.read())
    base = tensions(g)[0].priority
    from mindgraph.frontier import _priority

    assert _priority(g, "A", "B", "FINDING") > base


# ── one ranking, not two queues ─────────────────────────────────────────────


def test_tensions_compete_with_gaps_for_the_same_slots(led_kst):
    """⭐ One notion of "what matters now" — not a frontier and an alert
    system disagreeing with each other."""
    accept(
        led_kst,
        [node("R1", "Artifact"), node("S1", "Source"), node("A"), node("B")],
        [edge("R1", "supports", "A"), edge("S1", "supports", "B"), edge("A", "contradicts", "B")],
    )
    acts = frontier(project(led_kst.read()), limit=10)
    kinds = {a.kind.split("/")[0] for a in acts}
    assert "GAP" in kinds and "TENSION" in kinds


def test_an_ambient_tension_is_never_pushed(led_kst):
    """P3 means "only relevant when you are already nearby". A bare
    contradiction between two unsupported claims is real but not worth
    interrupting anyone for — it stays out of the ranked frontier and lives
    inline instead."""
    accept(led_kst, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    g = project(led_kst.read())
    assert tensions(g)[0].level == "P3"
    assert not any(a.kind.startswith("TENSION") for a in frontier(g, limit=10))


def test_the_frontier_is_capped_and_ranked(led_kst):
    acts = frontier(project(led_kst.read()), limit=3)
    assert len(acts) <= 3
    assert acts == sorted(acts, key=lambda a: (-a.priority, a.kind, a.id))


def test_every_action_carries_a_why(led_kst):
    accept(led_kst, [node("A"), node("B")], [edge("A", "contradicts", "B")])
    for a in frontier(project(led_kst.read()), limit=10):
        assert a.why


def test_the_frontier_is_deterministic(led_kst):
    g = project(led_kst.read())
    assert [a.id for a in frontier(g, limit=10)] == [a.id for a in frontier(g, limit=10)]
