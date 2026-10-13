"""NetworkX wrapper and indices. Backend/02 §1.

The graph library is deliberately kept behind this one module. Because the
graph is a projection of the ledger, swapping the library (or a real graph DB)
costs one re-projection — but only if nothing else imports networkx directly.

Load-tested at 10k and 25k nodes (Backend/09 Q11): per-turn retrieval is 27 ms,
a full 60k-event replay is 122 ms. Storage is ~100x off the critical path.
"""

from __future__ import annotations

import networkx as nx

from .projector import GraphState
from .schema import Rank


def to_networkx(state: GraphState, live_only: bool = True) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for nid in sorted(state.nodes):
        n = state.nodes[nid]
        if live_only and n.rank is Rank.DEPRECATED:
            continue
        g.add_node(
            nid,
            type=str(n.type),
            kind=n.kind,
            support=str(n.support),
            strength=str(n.strength),
            corroboration=n.corroboration,
            single_method=n.single_method,
            evidence_mass=n.evidence_mass,
        )
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if live_only and e.rank is Rank.DEPRECATED:
            continue
        if e.src in g and e.dst in g:
            g.add_edge(
                e.src, e.dst, key=eid, relation=str(e.relation), weight=e.weight, score=e.score
            )
    return g


def neighbors(state: GraphState, node_id: str, hops: int = 1) -> set[str]:
    g = to_networkx(state)
    if node_id not in g:
        return set()
    return set(
        nx.single_source_shortest_path_length(g.to_undirected(as_view=True), node_id, cutoff=hops)
    )


def stats(state: GraphState) -> dict:
    live_n = [n for n in state.nodes.values() if n.rank is not Rank.DEPRECATED]
    live_e = [e for e in state.edges.values() if e.rank is not Rank.DEPRECATED]
    return {
        "nodes": len(live_n),
        "edges": len(live_e),
        "hyperedges": len(state.hyper),
        "dead_ends": len(state.dead_ends),
        "deprecated_nodes": len(state.nodes) - len(live_n),
        "deprecated_edges": len(state.edges) - len(live_e),
        "established": sum(1 for n in live_n if n.strength.value == "established"),
        "contested": sum(1 for n in live_n if n.support.value == "contested"),
        "single_method": sum(1 for n in live_n if n.single_method),
        "last_seq": state.last_seq,
    }
