"""Shared builders. Kept deliberately thin — a fixture that hides the payload
shape makes the tests stop being a specification of it."""

from __future__ import annotations

import itertools

import pytest
from mindgraph.events import EventType
from mindgraph.ledger import Ledger

_ids = itertools.count(1)


def fixed_clock():
    """Frozen clock so hashes are byte-stable across runs."""
    return "2026-03-14T09:00:00Z"


@pytest.fixture
def led():
    return Ledger(":memory:", clock=fixed_clock)


def node(nid, ntype="Claim", **kw):
    d = {"id": nid, "type": ntype}
    if ntype == "Concept":
        d.setdefault("origin", "extracted")
        d.setdefault("scope", "project")
        d.setdefault("project_id", "p1")
    d.update(kw)
    return d


def edge(
    src,
    rel,
    dst,
    *,
    score=0.85,
    confidence="INFERRED",
    eid=None,
    justification=None,
    weight_source_nodes=None,
    **kw,
):
    return {
        "id": eid or f"e{next(_ids)}",
        "src": src,
        "dst": dst,
        "relation": rel,
        "confidence": confidence,
        "score": score,
        "justification": justification or [],
        "weight_source_nodes": weight_source_nodes or [src],
        **kw,
    }


def accept(led, nodes=(), edges=(), hyperedges=(), actor="test"):
    return led.append(
        actor,
        EventType.ACCEPTED,
        {"nodes": list(nodes), "edges": list(edges), "hyperedges": list(hyperedges)},
    )


def validate(led, artifact, validates, agreement="matched", actor="user"):
    return led.append(
        actor,
        EventType.VALIDATED,
        {"artifact_id": artifact, "agreement": agreement, "validates": list(validates)},
    )


def edge_id(state, src, rel, dst):
    from mindgraph.schema import Relation

    return state.edge_key[(src, Relation(rel), dst)]
