"""The ATMS retraction cascade. Backend/02 §6.

The part most likely to be built wrong, so the semantics are stated first:

  1. Edges deprecate; claims lose SUPPORT. An edge asserting "X supports Y"
     where X is gone is simply wrong. Y may still be true.
  2. BFS with a `seen` set. Cyclic justification (A supports B supports A) is a
     real thing students write, and naive recursion hangs on it.
  3. Support is a magnitude, not a boolean. Retracting one of five supports
     leaves a claim SUPPORTED; retracting the last leaves it UNSUPPORTED.
"""
from __future__ import annotations

from collections import deque

from .projector import GraphState, _recompute_support
from .schema import Rank


def cascade_retract(state: GraphState, target_id: str, seq: int) -> dict:
    """Retract `target_id`. Anything justified by it becomes UNSUPPORTED.

    NOT deprecated, NOT deleted. ⭐ A conclusion whose evidence vanished may
    still be true; it is simply no longer earned. Collapsing that distinction
    would silently deprecate conclusions that still hold, and a student would
    rightly stop trusting the system.
    """
    deprecated: set[str] = set()
    touched: set[str] = set()

    for store in (state.nodes, state.edges):
        if (obj := store.get(target_id)) is not None:
            obj.rank, obj.valid_to = Rank.DEPRECATED, str(seq)
            deprecated.add(target_id)

    # Retracting a node invalidates the edges that hang off it, and the nodes
    # those edges pointed at have to be re-scored.
    seeds: list[str] = [target_id]
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if (e.src == target_id or e.dst == target_id) \
                and e.rank is not Rank.DEPRECATED:
            e.rank, e.valid_to = Rank.DEPRECATED, str(seq)
            deprecated.add(eid)
            touched.add(e.dst)
            # ⭐ The edge itself must seed the walk. Downstream edges are
            # justified by THIS EDGE's id, not by the retracted node's — so a
            # walk seeded only with the node terminates immediately and the
            # cascade silently stops at depth one.
            seeds.append(eid)

    queue, seen = deque(seeds), set(seeds)
    while queue:
        dead = queue.popleft()
        for dependent in sorted(state.justified_by.get(dead, ())):
            if dependent in seen:
                continue                        # cyclic justification: stop
            seen.add(dependent)
            if (e := state.edges.get(dependent)) is not None:
                e.rank, e.valid_to = Rank.DEPRECATED, str(seq)
                deprecated.add(dependent)
                touched.add(e.dst)
                queue.append(dependent)
                queue.append(e.dst)             # follow the claim onward
            elif dependent in state.nodes:
                touched.add(dependent)
                queue.append(dependent)

    _recompute_support(state, touched)
    return {"deprecated": sorted(deprecated), "recomputed": sorted(touched)}
