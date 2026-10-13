"""fold(events) -> GraphState. Backend/02 §5. THE critical file.

Pure function. No I/O, no clock, no randomness, no network, no model calls.

Replaying a ledger from zero a year later, with a different model, must produce
a byte-identical graph. That property is what makes every failure repairable and
the database swappable — and it is easy to break. The rules in §5.3 are each a
bug someone has already written somewhere:

  1. Iterate sorted collections only — set order is not stable across runs.
  2. No wall-clock, no random, no uuid4 in here. Ids arrive in payloads.
  3. No floats derived by arithmetic. Scores come from the rubric.
  4. Unknown event types RAISE, never silently skip.
  5. last_seq guards replay, so applying an event twice is a no-op.
"""

from __future__ import annotations

import hashlib
import math
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from .errors import UnknownEventType
from .events import Event, EventType
from .ledger import canonical
from .schema import (
    EXTERNAL_TYPES,
    MIN_CORROBORATION,
    OPPOSING,
    SUPPORTING,
    Edge,
    Hyperedge,
    Node,
    NodeType,
    Rank,
    Relation,
    Strength,
    Support,
)
from .upcast import upcast


@dataclass
class GraphState:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    hyper: dict[str, Hyperedge] = field(default_factory=dict)
    alias: dict[str, str] = field(default_factory=dict)
    merged_into: dict[str, str] = field(default_factory=dict)
    justified_by: dict[str, set[str]] = field(default_factory=dict)
    edge_key: dict[tuple, str] = field(default_factory=dict)  # (src,rel,dst)->id
    dead_ends: dict[str, dict] = field(default_factory=dict)
    access: dict[str, list[int]] = field(default_factory=dict)  # salience
    last_seq: int = 0


def resolve(state: GraphState, nid: str) -> str:
    """Follow merge chains to the surviving node."""
    seen = set()
    while nid in state.merged_into and nid not in seen:
        seen.add(nid)
        nid = state.merged_into[nid]
    return nid


# ── evidence ────────────────────────────────────────────────────────────────


def _reaches(state: GraphState, src: str, dst: str, via: Relation) -> bool:
    """Is `dst` reachable from `src` following only live `via` edges?"""
    if src == dst:
        return False
    queue, seen = deque([src]), {src}
    while queue:
        cur = queue.popleft()
        for e in state.edges.values():
            if e.relation is via and e.src == cur and e.rank is not Rank.DEPRECATED:
                if e.dst == dst:
                    return True
                if e.dst not in seen:
                    seen.add(e.dst)
                    queue.append(e.dst)
    return False


def independent_weight(state: GraphState, edge: Edge) -> int:
    """Backend/09 Q6. `weight` counts DISTINCT sources; distinct is not independent.

    Five papers repeating one original claim is one fact — the citation cascade.
    Where we have the `cites` graph we can measure that directly instead of
    approximating it with a curve.

    ⚠️ Direction matters and the spec had it backwards. A source that CITES
    another is the derivative one; the cited original is the independent
    evidence. Inverting this would discount the original and keep the copies —
    exactly the failure the discount exists to prevent.
    """
    srcs = {s for s in edge.weight_source_nodes if s in state.nodes}
    if len(srcs) <= 1:
        return max(1, edge.weight)
    derivative = {
        b for b in srcs for a in srcs if a != b and _reaches(state, b, a, via=Relation.CITES)
    }
    return max(1, len(srcs - derivative))


def evidence_mass(state: GraphState, edges: Iterable[Edge]) -> float:
    """Damping over INDEPENDENT weight.

    sqrt rather than log2: our weights live in the 1-5 range, and there log2
    says the second source DOUBLES the evidence (w=2 -> 2.0), which is too
    generous when independence is uncertain. sqrt says +41%.
    """
    return sum(math.sqrt(independent_weight(state, e)) for e in edges)


def _derive_claim_kind(state: GraphState, nid: str, live_supporting) -> str:
    """Backend/09 Q5. Claim.kind is DERIVED from structure, never stored.

      observation  supported by evidence OUTSIDE your reasoning (Artifact|Source)
      conclusion   supported by other Claims
      hypothesis   no live support at all

    The extractor's guess is kept in provenance["kind_hint"] — recorded, not
    authoritative. Artifact.kind and Source.kind stay INTRINSIC: a firmware
    build vs a measurement is not derivable from the graph. Only Claim.kind is.
    """
    if not live_supporting:
        return "hypothesis"
    srcs = [state.nodes.get(e.src) for e in live_supporting]
    if any(n and n.type in EXTERNAL_TYPES for n in srcs):
        return "observation"
    return "conclusion"


def _recompute_support(state: GraphState, node_ids: Iterable[str]) -> None:
    """Support is an EXISTENCE question. Weight grades it; it never decides it.

    Also derives Claim.kind (Q5), single_method (Q12) and evidence_mass (Q6)
    in the same pass — one place, so they cannot drift apart.
    """
    for nid in sorted(set(node_ids)):
        if (n := state.nodes.get(nid)) is None:
            continue
        live = [e for e in state.edges.values() if e.dst == nid and e.rank is not Rank.DEPRECATED]
        pos = [e for e in live if e.relation in SUPPORTING]
        neg = [e for e in live if e.relation in OPPOSING]

        # Classification uses COUNTS, not weights — one live contradiction
        # always shows, however heavily the other side is cited.
        if pos and neg:
            n.support, n.strength = Support.CONTESTED, Strength.CONTESTED
        elif pos:
            n.support = Support.SUPPORTED
            # Strength depends on CORROBORATION (independent results), never on
            # edge weight (how many sources assert the link).
            n.strength = (
                Strength.ESTABLISHED if n.corroboration >= MIN_CORROBORATION else Strength.TENTATIVE
            )
        elif neg:
            n.support, n.strength = Support.UNSUPPORTED, Strength.TENTATIVE
        elif any(
            e.dst == nid and e.relation in SUPPORTING and e.rank is Rank.DEPRECATED
            for e in state.edges.values()
        ):
            # ⭐ It HAD support and lost it. That is not the same state as a
            # fresh hypothesis that never had any, and the difference is the
            # whole point of "conclusions lose support, not truth" — a claim
            # whose evidence just collapsed is exactly what a student needs
            # surfaced. The spec's classifier collapsed both into UNKNOWN,
            # which its own cascade test contradicted.
            n.support, n.strength = Support.UNSUPPORTED, Strength.TENTATIVE
        else:
            n.support, n.strength = Support.UNKNOWN, Strength.TENTATIVE

        if n.type is NodeType.CLAIM:
            n.kind = _derive_claim_kind(state, nid, pos)

        # Q12 — corroborated, but every result came from ONE method. Flags,
        # never blocks: same-method replication is a legitimate reproducibility
        # check, it just isn't independent evidence.
        n.single_method = n.corroboration >= MIN_CORROBORATION and len(n.corroborating_methods) == 1

        pm, nm = evidence_mass(state, pos), evidence_mass(state, neg)
        n.evidence_mass = round(pm, 4)
        n.contest_ratio = round(nm / (pm + nm), 4) if (pos and neg) else 0.0


def affected_nodes(p: dict) -> list[str]:
    out = [nd["id"] for nd in p.get("nodes", [])]
    out += [ed["dst"] for ed in p.get("edges", [])]
    out += [ed["src"] for ed in p.get("edges", [])]
    return out


def _merge_attrs(existing: Node, incoming: Node) -> None:
    """Later assertions fill blanks; they never overwrite what is already known."""
    for f in ("label", "body_ref", "kind", "project_id", "valid_from", "valid_to"):
        if getattr(existing, f) is None and getattr(incoming, f) is not None:
            setattr(existing, f, getattr(incoming, f))
    existing.aliases = sorted(set(existing.aliases) | set(incoming.aliases))
    existing.external_ids = {**incoming.external_ids, **existing.external_ids}
    existing.labels_at = {**existing.labels_at, **incoming.labels_at}


def _rebuild_edge_keys(state: GraphState) -> None:
    state.edge_key.clear()
    for eid in sorted(state.edges):
        e = state.edges[eid]
        e.src, e.dst = resolve(state, e.src), resolve(state, e.dst)
        state.edge_key[(e.src, e.relation, e.dst)] = eid


# ── handlers ────────────────────────────────────────────────────────────────


def _accepted(state: GraphState, p: dict, seq: int) -> None:
    for nd in sorted(p.get("nodes", []), key=lambda d: d["id"]):
        node = Node(**{**nd, "created_seq": seq})
        nid = resolve(state, node.id)
        if nid in state.nodes:
            _merge_attrs(state.nodes[nid], node)
        else:
            state.nodes[nid] = node
        for a in sorted(node.aliases):
            state.alias[a] = nid

    for ed in sorted(p.get("edges", []), key=lambda d: d["id"]):
        edge = Edge(**{**ed, "created_seq": seq})
        edge.src, edge.dst = resolve(state, edge.src), resolve(state, edge.dst)
        if edge.src == edge.dst:
            continue  # self-loop after a merge

        key = (edge.src, edge.relation, edge.dst)
        if (existing_id := state.edge_key.get(key)) is not None:
            # Re-assertion increments weight rather than duplicating the edge.
            ex = state.edges[existing_id]
            if seq not in ex.weight_sources:  # distinct sources only
                ex.weight += 1
                ex.weight_sources = sorted(set(ex.weight_sources) | {seq})
                ex.weight_source_nodes = sorted(
                    set(ex.weight_source_nodes) | set(edge.weight_source_nodes or [edge.src])
                )
            ex.score = max(ex.score, edge.score)  # best evidence wins
            ex.justification = sorted(set(ex.justification) | set(edge.justification))
            edge_id = existing_id
        else:
            edge.weight_sources = [seq]
            if not edge.weight_source_nodes:
                edge.weight_source_nodes = [edge.src]
            state.edges[edge.id] = edge
            state.edge_key[key] = edge.id
            edge_id = edge.id

        for dep in edge.justification:
            state.justified_by.setdefault(resolve(state, dep), set()).add(edge_id)

    for hd in sorted(p.get("hyperedges", []), key=lambda d: d["id"]):
        h = Hyperedge(**{**hd, "created_seq": seq})
        h.members = sorted(resolve(state, m) for m in h.members)
        if h.target:
            h.target = resolve(state, h.target)
        state.hyper[h.id] = h
        for dep in h.justification:
            state.justified_by.setdefault(resolve(state, dep), set()).add(h.id)

    _recompute_support(state, affected_nodes(p))


def _validated(state: GraphState, p: dict, seq: int) -> None:
    """The outcome path. `agreement` is structural; the values are encrypted.

    This is the flywheel signal — that a prediction matched is not personal
    data, so aggregate calibration survives an erasure request while the
    person's numbers do not.
    """
    aid = resolve(state, p["artifact_id"])
    if (art := state.nodes.get(aid)) is None:
        return
    art.labels_at = {**art.labels_at, "outcome": p["agreement"]}
    if p["agreement"] == "matched":
        m = _method_of(state, aid)  # Q12 — may be None
        for cid in sorted(p.get("validates", [])):
            if c := state.nodes.get(resolve(state, cid)):
                c.corroboration += 1  # a distinct RESULT
                if m and m not in c.corroborating_methods:
                    c.corroborating_methods = sorted(c.corroborating_methods + [m])
                _recompute_support(state, [c.id])


def _method_of(state: GraphState, artifact_id: str) -> str | None:
    """The Method an Artifact was produced with, if it declared one.

    Artifact(kind=run) --uses_method_in--> Artifact(kind=method).
    """
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if (
            e.src == artifact_id
            and e.relation is Relation.USES_METHOD_IN
            and e.rank is not Rank.DEPRECATED
        ):
            return e.dst
    return None


def _dead_end(state: GraphState, p: dict, seq: int) -> None:
    """What was tried, why it failed, and what would make it worth revisiting."""
    state.dead_ends[p["id"]] = {
        "question": p["question"],
        "nodes": sorted(p.get("nodes", [])),
        "seq": seq,
        "resurrect_if": sorted(p.get("resurrect_if", [])),
    }


def _correction(state: GraphState, p: dict, seq: int) -> None:
    """User fixed something. Applied, and logged as an extraction-quality signal.

    ⚠️ Re-validated rather than `setattr`-ed. A raw setattr bypasses pydantic
    entirely, so `origin="promoted"` lands as a STRING where every downstream
    `is Origin.PROMOTED` comparison then quietly fails — the enum looks right
    when printed and behaves wrong everywhere.

    Dict fields are MERGED, not replaced: a correction that sets one key of
    `labels_at` must not silently erase the domain and tier alongside it.
    """
    nid = resolve(state, p["target"])
    if (n := state.nodes.get(nid)) is None:
        return
    merged = n.model_dump()
    for k, v in sorted(p.get("fields", {}).items()):
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    state.nodes[nid] = Node(**merged)
    _recompute_support(state, [nid])


def _merged(state: GraphState, p: dict, seq: int) -> None:
    kept, absorbed = resolve(state, p["kept"]), resolve(state, p["absorbed"])
    if kept == absorbed:
        return
    state.merged_into[absorbed] = kept
    a = state.nodes.pop(absorbed, None)
    if a and kept in state.nodes:
        k = state.nodes[kept]
        k.aliases = sorted(set(k.aliases) | set(a.aliases) | ({a.label} if a.label else set()))
        k.corroboration += a.corroboration  # counts survive a merge
        k.corroborating_methods = sorted(
            set(k.corroborating_methods) | set(a.corroborating_methods)
        )  # Q12
        for s in k.aliases:
            state.alias[s] = kept
    _rebuild_edge_keys(state)  # endpoints changed
    _recompute_support(state, [kept])


def _retracted(state: GraphState, p: dict, seq: int) -> None:
    from .cascade import cascade_retract

    cascade_retract(state, resolve(state, p["target"]), seq)


def _shredded(state: GraphState, p: dict, seq: int) -> None:
    """Erasure. The SHAPE survives; the content does not.

    Nodes stay, with null labels, so the projector never corrupts and snapshots
    never break — and state_hash excludes these fields, so a shredded graph
    still passes its own determinism check.
    """
    for nid in sorted(state.nodes):
        n = state.nodes[nid]
        n.label, n.aliases, n.body_ref = None, [], None
    state.alias.clear()


def _accessed(state: GraphState, p: dict, seq: int) -> None:
    """Salience input. Recorded as SEQ, never as wall-clock — the projector
    must stay pure, so decay is computed at read time from `last_seq`."""
    for nid in sorted(p.get("nodes", [])):
        state.access.setdefault(resolve(state, nid), []).append(seq)


def _noop(state: GraphState, p: dict, seq: int) -> None:
    """Recorded, but carries no graph structure of its own."""


HANDLERS = {
    EventType.ACCEPTED: _accepted,
    EventType.VALIDATED: _validated,
    EventType.DEAD_END: _dead_end,
    EventType.CORRECTION: _correction,
    EventType.MERGED: _merged,
    EventType.RETRACTED: _retracted,
    EventType.SHREDDED: _shredded,
    EventType.OBSERVED: _noop,
    EventType.PROPOSED: _noop,
    EventType.REJECTED: _noop,
    EventType.ANNOTATED: _noop,
    EventType.ACCESSED: _accessed,
    EventType.SPLIT: _noop,
}


def project(events: Iterable[Event], state: GraphState | None = None) -> GraphState:
    state = state if state is not None else GraphState()
    for e in events:
        if e.seq <= state.last_seq:
            continue  # idempotent replay
        payload = upcast(e.structural, e.schema_version)
        handler = HANDLERS.get(e.type)
        if handler is None:
            raise UnknownEventType(f"no handler for {e.type!r} at seq {e.seq} — refusing to skip")
        handler(state, payload, e.seq)
        state.last_seq = e.seq
    return state


def state_hash(state: GraphState) -> str:
    """Canonical fingerprint.

    Excludes encrypted fields so a shredded graph still hashes to what it did
    before the key was destroyed — which is the test that proves erasure does
    not corrupt the structure.
    """
    h = hashlib.sha256()
    for nid in sorted(state.nodes):
        h.update(
            canonical(
                state.nodes[nid].model_dump(mode="json", exclude={"label", "aliases", "body_ref"})
            ).encode()
        )
    for eid in sorted(state.edges):
        h.update(canonical(state.edges[eid].model_dump(mode="json")).encode())
    for hid in sorted(state.hyper):
        h.update(canonical(state.hyper[hid].model_dump(mode="json")).encode())
    for did in sorted(state.dead_ends):
        h.update(canonical(state.dead_ends[did]).encode())
    for aid in sorted(state.access):
        h.update(canonical([aid, state.access[aid]]).encode())
    return h.hexdigest()
