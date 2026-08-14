"""Snapshot + tail == full replay. Backend/02 §7, §9.

A snapshot is a cache. The invariant here is what lets it be one safely — and
it is also what makes LRU eviction free under concurrency (Backend/07 §4.6).
"""
from __future__ import annotations

from conftest import accept, edge, node, validate
from mindgraph import snapshot
from mindgraph.projector import project, state_hash


def _build(led):
    accept(led, [node("M1", "Artifact"), node("M2", "Artifact"), node("C")],
           [edge("M1", "supports", "C"), edge("M2", "supports", "C")])
    validate(led, "M1", ["C"])
    validate(led, "M2", ["C"])


def test_snapshot_roundtrips(led):
    _build(led)
    g = project(led.read())
    assert state_hash(snapshot.loads(snapshot.dumps(g))) == state_hash(g)


def test_snapshot_plus_tail_equals_full_replay(led):
    _build(led)
    half = project(led.read(since=0))
    cut = half.last_seq

    restored = snapshot.loads(snapshot.dumps(half))
    accept(led, [node("M3", "Artifact")], [edge("M3", "supports", "C")])
    validate(led, "M3", ["C"])

    topped_up = project(led.read(since=cut), restored)
    full = project(led.read())
    assert state_hash(topped_up) == state_hash(full)


def test_snapshot_preserves_edge_index(led):
    """The (src, rel, dst) index is rebuilt on load — without it, a re-assertion
    after a restore would duplicate the edge instead of incrementing weight."""
    _build(led)
    g = snapshot.loads(snapshot.dumps(project(led.read())))
    accept(led, [], [edge("M1", "supports", "C")])
    g2 = project(led.read(since=g.last_seq), g)
    from mindgraph.schema import Relation
    assert g2.edges[g2.edge_key[("M1", Relation.SUPPORTS, "C")]].weight == 2
