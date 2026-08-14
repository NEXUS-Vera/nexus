"""Re-assertion increments weight rather than duplicating. Backend/02 §7.

The bug this prevents: the same relationship arriving from five documents
becoming five edges, so the graph looks five times as connected as it is.
"""
from __future__ import annotations

from conftest import accept, edge, edge_id, node, validate
from mindgraph.projector import project
from mindgraph.schema import Relation


def test_reassertion_increments_weight_not_duplicates(led):
    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    accept(led, [], [edge("M", "supports", "C")])       # a second source says so
    g = project(led.read())
    supports = [e for e in g.edges.values() if e.relation is Relation.SUPPORTS]
    assert len(supports) == 1
    assert g.edges[edge_id(g, "M", "supports", "C")].weight == 2


def test_same_event_does_not_double_count(led):
    """Weight counts distinct sources, not repetitions of one."""
    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    g = project(list(led.read()) + list(led.read()))
    assert g.edges[edge_id(g, "M", "supports", "C")].weight == 1


def test_best_evidence_wins_on_reassertion(led):
    accept(led, [node("M", "Artifact"), node("C")],
           [edge("M", "supports", "C", score=0.65)])
    accept(led, [], [edge("M", "supports", "C", score=0.95)])
    g = project(led.read())
    assert g.edges[edge_id(g, "M", "supports", "C")].score == 0.95


def test_corroboration_survives_merge(led):
    """Merging two claims must not lose the results that backed either."""
    accept(led, [node("A"), node("B"),
                 node("R1", "Artifact"), node("R2", "Artifact"),
                 node("R3", "Artifact")],
           [edge("R1", "supports", "A"), edge("R2", "supports", "A"),
            edge("R3", "supports", "B")])
    validate(led, "R1", ["A"])
    validate(led, "R2", ["A"])
    validate(led, "R3", ["B"])
    from mindgraph.events import EventType
    led.append("user", EventType.MERGED, {"kept": "A", "absorbed": "B"})
    g = project(led.read())
    assert g.nodes["A"].corroboration == 3          # 2 + 1
    assert "B" not in g.nodes
