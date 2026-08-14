"""The portable graph — one ranking, two runtimes. `Open Questions §4.4`.

⭐ **The decision this implements, and the one it deliberately does not.**

The problem §4.4 named was NOT "we use the wrong graph library". It was that
graph logic could only run on the server, so the client either did without it
or **reimplemented it** — which is exactly what happened when the Map shipped a
second Degree-of-Interest in TypeScript, and exactly what will happen again the
next time the client needs graph reasoning.

The obvious fix — port `analyzer.py` and `retrieve.py` to a graphology-shaped
model — is two to three days and re-runs every expensive computation in a
browser. ⚠️ It also does not actually stop the drift: two ports of one
algorithm are still two implementations.

**What stops the drift is moving the SPLIT, not the library.**

    server   the expensive, divergent half — PPR, centrality, distances,
             corroboration, staleness. Computed once, per node, and SHIPPED.
    client   the cheap, exact half — a weighted sum and a distance penalty.
             Ten lines, and provably the same ten lines.

So the payload carries each node's DOI *components* plus the current weight
vector, and both runtimes do the identical final arithmetic. There is nothing
left to disagree about, because the part that could disagree is only computed
in one place.

⭐ **This is what buys offline.** The heavy work is already done by the time
the payload lands, so a student at a bench with no signal can re-rank against
a cached payload — change focus, re-sort the frontier, ask "what next" — with
no server and no model.

⚠️ **The conformance fixture is the load-bearing part** (`scripts/gen_conformance.py`).
It pins Python's ranking and the TypeScript ranking to identical output on the
same payload. If they ever diverge, a test fails rather than a student
silently seeing a Map ranked differently from their Bench.

Format is graphology's serialised shape (`{attributes, nodes, edges}`) so the
client can `Graph.from(payload)` directly and get a real graph object for
traversal, not a bag of dictionaries.
"""
from __future__ import annotations

from typing import Any

import networkx as nx

from .graph import GraphState
from .retrieve import MAX_HOPS, _confidence, _learnable, _outcome, _salience, _stale
from .retrieve import expand, known_set, weights

# ⚠️ Mirrored in `src/lib/frontier.ts`. The distance coefficient is part of the
# contract, not a tuning knob either side may change alone — the conformance
# fixture fails loudly if one moves without the other.
DISTANCE_PENALTY = 0.05


def doi_parts(state: GraphState, nid: str, known: set[str],
              ppr: dict[str, float], top: float) -> dict[str, float]:
    """The six components, exactly as `retrieve.rank` computes them.

    ⚠️ This function must stay the single source of these numbers. If `rank`
    ever computes them inline again, the portable payload becomes a second
    definition of "interesting" and we are back where we started.
    """
    return {
        "centrality": ppr.get(nid, 0.0) / top if top else 0.0,
        "salience": _salience(state, nid),
        "outcome": _outcome(state, nid),
        "confidence": _confidence(state, nid),
        "learnability": _learnable(state, nid, known),
        "staleness": _stale(state, nid),
    }


def to_portable(state: GraphState, seeds: list[str] | None = None,
                labels: dict[str, str] | None = None,
                lens: str | None = None) -> dict[str, Any]:
    """Serialise the graph plus everything needed to re-rank it client-side.

    `seeds` only sets the *initial* distances. The client can re-seed on any
    node it likes and recompute distances itself with a breadth-first walk —
    which is the whole point of shipping a real graph rather than a ranking.
    """
    seeds = [s for s in (seeds or []) if s in state.nodes]
    g, ppr = expand(state, seeds or sorted(state.nodes)[:5], lens)
    top = max(ppr.values()) if ppr else 1.0
    known = known_set(state)

    dist: dict[str, int] = {}
    if seeds:
        und = g.to_undirected(as_view=True)
        for s in seeds:
            if s in und:
                for nid, d in nx.single_source_shortest_path_length(
                        und, s, cutoff=MAX_HOPS).items():
                    dist[nid] = min(dist.get(nid, 99), d)

    nodes = []
    for nid, n in state.nodes.items():
        parts = doi_parts(state, nid, known, ppr, top)
        attrs: dict[str, Any] = {
            "type": str(n.type).split(".")[-1],
            "kind": n.kind,
            "support": str(n.support).split(".")[-1],
            "strength": str(n.strength).split(".")[-1],
            "corroboration": n.corroboration,
            "singleMethod": n.single_method,
            "doi": parts,
            "hops": dist.get(nid, MAX_HOPS + 1),
        }
        if labels and nid in labels:
            attrs["label"] = labels[nid]
        nodes.append({"key": nid, "attributes": attrs})

    edges = [{"key": eid, "source": e.src, "target": e.dst,
              "attributes": {"relation": str(e.relation).split(".")[-1]}}
             for eid, e in state.edges.items()
             if e.src in state.nodes and e.dst in state.nodes]

    return {
        # graphology's serialised shape — `Graph.from(payload)` consumes this
        "options": {"type": "directed", "multi": False, "allowSelfLoops": False},
        "attributes": {
            # ⭐ The weights ride WITH the payload. They ramp as the graph ages
            # (`Backend/07 §5`), so a client holding a stale copy would rank by
            # last month's definition of interesting — shipping them makes the
            # payload self-describing and the cache safe to keep.
            "weights": weights(state),
            "distancePenalty": DISTANCE_PENALTY,
            "seeds": seeds,
            "maxHops": MAX_HOPS,
            "nodeCount": len(state.nodes),
        },
        "nodes": nodes,
        "edges": edges,
    }


def rank_portable(payload: dict[str, Any]) -> list[tuple[str, float]]:
    """The client's arithmetic, in Python, so the fixture can pin both sides.

    ⚠️ Ten lines on purpose. Every line here has a twin in `frontier.ts`, and
    the only reason this is duplicated at all is to have something to compare
    against — a conformance oracle, not a second implementation of the design.
    """
    w = payload["attributes"]["weights"]
    dp = payload["attributes"]["distancePenalty"]
    out = []
    for n in payload["nodes"]:
        a = n["attributes"]
        api = sum(w[k] * v for k, v in a["doi"].items())
        out.append((n["key"], round(api - dp * a["hops"], 5)))
    out.sort(key=lambda kv: (-kv[1], kv[0]))
    return out
