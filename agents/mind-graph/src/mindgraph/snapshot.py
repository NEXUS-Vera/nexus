"""Serialise and restore a GraphState. Backend/02 §1.

A snapshot is a cache, never a source of truth. It carries `last_seq` so a
restore can be topped up from the ledger tail, and the invariant tested in CI
is: snapshot + tail == full replay.

⚠️ Backup the ledger, not this (Backend/07 §4.4). A restored snapshot can
disagree with the log; a replayed one cannot.
"""
from __future__ import annotations

import json
from pathlib import Path

from .projector import GraphState
from .schema import Edge, Hyperedge, Node


def dumps(state: GraphState) -> str:
    return json.dumps({
        "last_seq": state.last_seq,
        "nodes": {k: state.nodes[k].model_dump(mode="json")
                  for k in sorted(state.nodes)},
        "edges": {k: state.edges[k].model_dump(mode="json")
                  for k in sorted(state.edges)},
        "hyper": {k: state.hyper[k].model_dump(mode="json")
                  for k in sorted(state.hyper)},
        "alias": dict(sorted(state.alias.items())),
        "merged_into": dict(sorted(state.merged_into.items())),
        "justified_by": {k: sorted(v) for k, v in sorted(state.justified_by.items())},
        "dead_ends": {k: state.dead_ends[k] for k in sorted(state.dead_ends)},
        "access": {k: state.access[k] for k in sorted(state.access)},
    }, sort_keys=True, separators=(",", ":"))


def loads(blob: str) -> GraphState:
    d = json.loads(blob)
    state = GraphState(
        nodes={k: Node(**v) for k, v in d["nodes"].items()},
        edges={k: Edge(**v) for k, v in d["edges"].items()},
        hyper={k: Hyperedge(**v) for k, v in d["hyper"].items()},
        alias=dict(d["alias"]),
        merged_into=dict(d["merged_into"]),
        justified_by={k: set(v) for k, v in d["justified_by"].items()},
        dead_ends=dict(d["dead_ends"]),
        access={k: list(v) for k, v in d.get("access", {}).items()},
        last_seq=d["last_seq"],
    )
    for eid in sorted(state.edges):
        e = state.edges[eid]
        state.edge_key[(e.src, e.relation, e.dst)] = eid
    return state


def save(state: GraphState, path: str | Path) -> None:
    Path(path).write_text(dumps(state))


def load(path: str | Path) -> GraphState:
    return loads(Path(path).read_text())
