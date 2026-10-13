"""Phase 0 acceptance. Backend/02 §9.

    "Phase 0 is done when a synthetic 500-event ledger replays deterministically,
     a retraction cascades correctly through three levels, a re-assertion
     increments weight instead of duplicating, a single result stays tentative,
     and a shred leaves the shape intact."

Each criterion is one test below. If these five are green, Phase 0 ships.
"""

from __future__ import annotations

from conftest import accept, edge, fixed_clock, node, validate
from mindgraph.events import EventType
from mindgraph.graph import stats
from mindgraph.ledger import Ledger
from mindgraph.projector import GraphState, project, state_hash
from mindgraph.schema import Rank, Strength, Support


def build_synthetic(n_events: int = 500) -> Ledger:
    """A ledger shaped like a real project: concepts, sources, runs, outcomes,
    re-assertions, a merge, a dead end and a retraction."""
    led = Ledger(":memory:", clock=fixed_clock)
    accept(led, [node("Q1", "Question"), node("root", "Concept")])
    i = 0
    while led.head()[0] < n_events:
        i += 1
        c, s, r = f"C{i}", f"S{i}", f"R{i}"
        accept(
            led,
            [
                node(c),
                node(s, "Source", kind="paper"),
                node(r, "Artifact", kind="run"),
                node(f"K{i}", "Concept", project_id="p1"),
            ],
            [
                edge(s, "supports", c, weight_source_nodes=[s]),
                edge(r, "measured_by", c, weight_source_nodes=[r]),
                edge(c, "relates_to", "root"),
            ],
        )
        if i % 3 == 0:  # a second result
            accept(
                led,
                [node(f"R{i}b", "Artifact", kind="run")],
                [edge(f"R{i}b", "supports", c, weight_source_nodes=[f"R{i}b"])],
            )
            validate(led, f"R{i}b", [c])
        if i % 4 == 0:  # a contradiction
            accept(led, [], [edge(s, "contradicts", f"C{max(1, i - 1)}")])
        if i % 5 == 0:  # a re-assertion
            accept(led, [], [edge(s, "supports", c, weight_source_nodes=[f"S{i}x"])])
        validate(led, r, [c])
    led.append("user", EventType.MERGED, {"kept": "C1", "absorbed": "C2"})
    led.append(
        "user",
        EventType.DEAD_END,
        {"id": "d1", "question": "400 kHz?", "nodes": ["C3"], "resurrect_if": ["shielding_added"]},
    )
    led.append("user", EventType.RETRACTED, {"target": "R3"})
    return led


def test_500_event_ledger_replays_deterministically():
    led = build_synthetic(500)
    assert led.head()[0] >= 500
    assert led.verify_chain()

    a, b = project(led.read()), project(led.read())
    assert state_hash(a) == state_hash(b)

    piecewise = GraphState()
    for e in led.read():
        piecewise = project([e], piecewise)
    assert state_hash(piecewise) == state_hash(a)

    s = stats(a)
    assert s["nodes"] > 100 and s["edges"] > 100
    assert s["established"] > 0 and s["contested"] > 0


def test_retraction_cascades_through_three_levels(led):
    accept(
        led,
        [node("M", "Artifact"), node("C1"), node("C2"), node("C3")],
        [
            edge("M", "supports", "C1", eid="e1"),
            edge("C1", "supports", "C2", eid="e2", justification=["e1"]),
            edge("C2", "supports", "C3", eid="e3", justification=["e2"]),
        ],
    )
    g = project(led.read())
    from mindgraph.cascade import cascade_retract

    out = cascade_retract(g, "M", seq=99)
    assert {"C1", "C2", "C3"} <= set(out["recomputed"])
    assert all(g.nodes[c].support is Support.UNSUPPORTED for c in ("C1", "C2", "C3"))
    assert all(
        g.nodes[c].rank is not Rank.DEPRECATED for c in ("C1", "C2", "C3")
    )  # unsupported, not false


def test_reassertion_increments_weight_instead_of_duplicating(led):
    accept(
        led,
        [node("Z", "Concept", project_id="p1"), node("C")],
        [edge("Z", "supports", "C", weight_source_nodes=["s1"])],
    )
    accept(led, [], [edge("Z", "supports", "C", weight_source_nodes=["s2"])])
    g = project(led.read())
    assert len(g.edges) == 1
    assert next(iter(g.edges.values())).weight == 2


def test_a_single_result_stays_tentative(led):
    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    validate(led, "M", ["C"])
    assert project(led.read()).nodes["C"].strength is Strength.TENTATIVE


def test_a_shred_leaves_the_shape_intact(led):
    accept(
        led,
        [node("M", "Artifact", label="forearm sweep"), node("C", label="47 kOhm means hydrated")],
        [edge("M", "supports", "C")],
    )
    before = project(led.read())
    led.append("system", EventType.SHREDDED, {"user": "u1"})
    after = project(led.read())
    assert set(after.nodes) == set(before.nodes)
    assert state_hash(after) == state_hash(before)
