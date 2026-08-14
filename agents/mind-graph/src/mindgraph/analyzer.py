"""The analyzer. Backend/01 §7.

CPU-bound and single-core-ish. **Never runs synchronously.** Everything here
writes a SIDECAR — derived, disposable, recomputable — never the ledger.

    clustering + stable community identity   on change budget
    centrality (betweenness APPROXIMATE)     on change budget
    crossover scoring                        nightly
    co-citation · unlinked mentions          nightly / on write
    Adamic-Adar link prediction              nightly
    contradiction + staleness sweeps         nightly

⭐ Community identity must be STABLE across runs. Fingerprint members, remap to
the previous run, and never let a re-cluster renumber the student's mental map.
A region that silently becomes a different region is worse than no regions.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx

from .graph import to_networkx
from .projector import GraphState
from .resolve import normalise
from .schema import OPPOSING, Confidence, NodeType, Rank, Support

BETWEENNESS_PIVOTS = 200   # exact is ~118s at 10k nodes; this is 3s (Q11)
STALE_AFTER_SEQ = 50       # a dependency changed this long after the claim


# ── clustering, with identity that survives a re-run ────────────────────────

def _fingerprint(members: set[str]) -> frozenset[str]:
    return frozenset(sorted(members))


def communities(state: GraphState,
                previous: dict[str, set[str]] | None = None) -> dict[str, set[str]]:
    """Louvain today; ⚠️ Leiden when `leidenalg` is available.

    Louvain can emit internally DISCONNECTED communities, and a labelled region
    drawn around one is a lie rendered as a shape. We therefore split any
    disconnected community into its connected parts before returning, which
    recovers the guarantee Leiden gives for free.
    """
    g = to_networkx(state).to_undirected()
    if g.number_of_nodes() == 0:
        return {}
    raw = nx.community.louvain_communities(g, seed=7)

    parts: list[set[str]] = []
    for c in raw:
        sub = g.subgraph(c)
        parts.extend(set(p) for p in nx.connected_components(sub))

    # Stable identity: a new community inherits the id of whichever previous
    # community it overlaps most, so the student's map keeps its regions.
    out: dict[str, set[str]] = {}
    taken: set[str] = set()
    for i, members in enumerate(sorted(parts, key=lambda s: (-len(s), sorted(s)))):
        cid = None
        if previous:
            best, score = None, 0.0
            for pid, pmembers in previous.items():
                if pid in taken or not pmembers:
                    continue
                j = len(members & pmembers) / len(members | pmembers)
                if j > score:
                    best, score = pid, j
            if best and score >= 0.3:
                cid, _ = best, taken.add(best)
        out[cid or f"c{i}:{abs(hash(_fingerprint(members))) % 100000}"] = members
    return out


def _eigenvector_per_component(und) -> dict[str, float]:
    """⚠️ Eigenvector centrality is ILL-DEFINED on a disconnected graph.

    The dominant eigenvector may sit entirely on one component, so which
    component "wins" flips between runs and the numbers are not reproducible.
    Our graphs are disconnected all the time — separate projects, isolated
    notes — so this is the normal case, not an edge case.

    Computing it per connected component makes it both deterministic and
    meaningful: centrality within your region, which is what it was ever
    supposed to mean.
    """
    ev: dict[str, float] = {}
    for comp in nx.connected_components(und):
        sub = und.subgraph(comp)
        if sub.number_of_nodes() < 3 or sub.number_of_edges() == 0:
            ev.update(dict.fromkeys(sub, 0.0))
            continue
        try:
            vals = nx.eigenvector_centrality_numpy(nx.Graph(sub), weight="weight")
        except Exception:
            vals = dict.fromkeys(sub, 0.0)
        peak = max((abs(v) for v in vals.values()), default=0.0) or 1.0
        ev.update({n: abs(v) / peak for n, v in vals.items()})
    return ev


def centrality(state: GraphState) -> dict[str, dict[str, float]]:
    g = to_networkx(state)
    if g.number_of_nodes() == 0:
        return {}
    dg = nx.DiGraph(g)
    pr = nx.pagerank(dg, weight="weight")
    und = dg.to_undirected()
    k = min(BETWEENNESS_PIVOTS, und.number_of_nodes())
    bt = nx.betweenness_centrality(und, k=k, seed=7) if k > 2 else \
        dict.fromkeys(und, 0.0)
    ev = _eigenvector_per_component(und)
    return {n: {"pagerank": round(pr.get(n, 0.0), 6),
                "betweenness": round(bt.get(n, 0.0), 6),
                "eigenvector": round(abs(ev.get(n, 0.0)), 6)} for n in sorted(dg)}


# ── the crossover scorer — the differentiating signal ───────────────────────

def _discipline(state: GraphState, nid: str) -> str:
    return state.nodes[nid].labels_at.get("domain", "unknown")


def _project(state: GraphState, nid: str) -> str | None:
    return state.nodes[nid].project_id


def crossover_score(state: GraphState, u: str, v: str, edge,
                    degree: dict[str, int] | None = None) -> tuple[int, list[str]]:
    """⭐ Graphify's axes were file-type and directory. Ours are EPISTEMIC and
    DISCIPLINARY — which is the difference between a code-structure toy and a
    research companion."""
    score, why = 0, []
    score += {Confidence.AMBIGUOUS: 3, Confidence.INFERRED: 2,
              Confidence.EXTRACTED: 1}[edge.confidence]
    if edge.confidence is not Confidence.EXTRACTED:
        why.append("not explicitly stated in any source")

    du, dv = _discipline(state, u), _discipline(state, v)
    if du != dv and "unknown" not in (du, dv):
        score += 3; why.append(f"crosses {du} <-> {dv}")

    pu, pv = _project(state, u), _project(state, v)
    if pu != pv and pu and pv:
        score += 2; why.append("connects two of your projects")

    au, av = state.nodes[u].created_seq, state.nodes[v].created_seq
    if abs(au - av) > 30:
        score += 1; why.append("links work weeks apart")

    kinds = {state.nodes[u].type, state.nodes[v].type}
    if kinds == {NodeType.SOURCE, NodeType.ARTIFACT}:
        score += 3
        why.append("connects a published claim to your own measurement")

    # ⚠️ Degree is passed in by crossovers(). Rebuilding the graph per edge
    # here made analyze() O(E) full graph constructions — 3.9s on 697 nodes.
    if degree is None:
        gg = to_networkx(state).to_undirected()
        degree = {n: gg.degree(n) for n in gg}
    deg = {n: degree[n] for n in (u, v) if n in degree}
    if len(deg) == 2 and min(deg.values()) <= 2 and max(deg.values()) >= 5:
        score += 1; why.append("peripheral node unexpectedly reaches a hub")

    # Suppression: a label-matched INFERRED edge is resolver pollution, not
    # insight. Without this, the top of every crossover list is near-duplicates.
    if edge.confidence is Confidence.INFERRED and \
            edge.provenance.get("actor") == "resolver":
        score = min(score, 2)
    return score, why


def crossovers(state: GraphState, limit: int = 5) -> list[dict]:
    """⭐ Deduplicated BY COMMUNITY PAIR — without it, one high-betweenness hub
    dominates every result.

    Every surfaced crossover carries its `why`. Never show a connection without
    the reason it is surprising; that is what turns a graph into a mentor.
    """
    comms = communities(state)
    of = {n: cid for cid, members in comms.items() for n in members}
    und = to_networkx(state).to_undirected()
    degree = {n: und.degree(n) for n in und}
    scored = []
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if e.rank is Rank.DEPRECATED or e.src not in state.nodes \
                or e.dst not in state.nodes:
            continue
        s, why = crossover_score(state, e.src, e.dst, e, degree)
        if s >= 4 and why:
            scored.append({"edge": eid, "src": e.src, "dst": e.dst,
                           "score": s, "why": why,
                           "pair": tuple(sorted((of.get(e.src, "?"),
                                                 of.get(e.dst, "?"))))})
    seen, out = set(), []
    for c in sorted(scored, key=lambda d: (-d["score"], d["edge"])):
        if c["pair"] in seen:
            continue
        seen.add(c["pair"])
        out.append({k: v for k, v in c.items() if k != "pair"})
        if len(out) >= limit:
            break
    return out


# ── cheap proposal sources — no model call ─────────────────────────────────

def unlinked_mentions(state: GraphState, labels: dict[str, str],
                      bodies: dict[str, str]) -> list[dict]:
    """⭐ The cheapest proposal source in the system: one string scan against
    the alias table, no model."""
    concepts = {nid: normalise(labels[nid]) for nid, n in state.nodes.items()
                if n.type is NodeType.CONCEPT and nid in labels
                and len(labels[nid]) > 3}
    linked = {(e.src, e.dst) for e in state.edges.values()
              if e.rank is not Rank.DEPRECATED}
    out = []
    for holder, text in sorted(bodies.items()):
        if holder not in state.nodes:
            continue
        hay = normalise(text)
        for cid, name in sorted(concepts.items()):
            if cid == holder or (holder, cid) in linked:
                continue
            if re.search(rf"\b{re.escape(name)}\b", hay):
                out.append({"src": holder, "dst": cid, "relation": "relates_to",
                            "confidence": "INFERRED", "score": 0.75,
                            "why": f"mentions '{labels[cid]}' with no link"})
    return out


def cocitation(state: GraphState, containers: dict[str, list[str]],
               same_sentence: dict[str, list[list[str]]] | None = None
               ) -> list[dict]:
    """Concepts the student THINKS ABOUT TOGETHER — complementary to
    Adamic-Adar, which is purely structural."""
    same_sentence = same_sentence or {}
    pair: dict[tuple[str, str], float] = defaultdict(float)
    for holder, members in sorted(containers.items()):
        ms = sorted(set(members))
        sent = {tuple(sorted(g)) for g in same_sentence.get(holder, [])}
        for i, a in enumerate(ms):
            for b in ms[i + 1:]:
                w = 1.0
                if any(a in s and b in s for s in sent):
                    w = 3.0
                elif len(ms) <= 8:
                    w = 2.0
                pair[(a, b)] += w
    return [{"a": a, "b": b, "weight": round(w, 2)}
            for (a, b), w in sorted(pair.items(), key=lambda t: (-t[1], t[0]))]


def adamic_adar(state: GraphState, limit: int = 20) -> list[dict]:
    """Link prediction for phantom edges — and the evaluation BASELINE.

    If our retrieval cannot beat a 2003 algorithm, the graph is not earning
    its cost (Backend/06).
    """
    g = nx.Graph(to_networkx(state).to_undirected())   # simple graph: AA is
    if g.number_of_nodes() < 3:                        # not defined on multigraphs
        return []
    nonedges = [(u, v) for u, v in nx.non_edges(g)]
    scored = [{"a": u, "b": v, "score": round(s, 4)}
              for u, v, s in nx.adamic_adar_index(g, nonedges) if s > 0]
    return sorted(scored, key=lambda d: (-d["score"], d["a"], d["b"]))[:limit]


# ── nightly sweeps ─────────────────────────────────────────────────────────

def contradiction_sweep(state: GraphState) -> list[dict]:
    """⭐ The primary catch for auto-accepted inferences (Q1).

    A fabricated edge usually collides with something real eventually, and this
    is where that collision surfaces.
    """
    out = []
    for nid in sorted(state.nodes):
        n = state.nodes[nid]
        if n.support is Support.CONTESTED:
            live = [e for e in state.edges.values()
                    if e.dst == nid and e.rank is not Rank.DEPRECATED]
            out.append({
                "node": nid, "kind": "CONFLICT",
                "contest_ratio": n.contest_ratio,
                "against": sorted(e.src for e in live if e.relation in OPPOSING),
                "for": sorted(e.src for e in live if e.relation not in OPPOSING),
            })
    for eid in sorted(state.edges):
        e = state.edges[eid]
        if e.confidence is Confidence.AMBIGUOUS and e.rank is not Rank.DEPRECATED:
            out.append({"edge": eid, "kind": "AMBIGUOUS_UNRESOLVED",
                        "src": e.src, "dst": e.dst})
    return out


def staleness_sweep(state: GraphState) -> list[dict]:
    """A dependency changed AFTER a claim was made. The claim may be fine —
    but nobody has looked since, and that is worth saying."""
    out = []
    for nid in sorted(state.nodes):
        n = state.nodes[nid]
        if n.rank is Rank.DEPRECATED:
            continue
        deps = [state.nodes[e.src] for e in state.edges.values()
                if e.dst == nid and e.rank is not Rank.DEPRECATED
                and e.src in state.nodes]
        newer = [d for d in deps if d.created_seq > n.created_seq + STALE_AFTER_SEQ]
        if newer:
            out.append({"node": nid, "kind": "STALE",
                        "changed_since": sorted(d.id for d in newer)})
    return out


# ── the sidecar ────────────────────────────────────────────────────────────

@dataclass
class Sidecar:
    """Derived, disposable, recomputable. Deleting it costs CPU, never data."""
    communities: dict[str, list[str]] = field(default_factory=dict)
    centrality: dict[str, dict[str, float]] = field(default_factory=dict)
    crossovers: list[dict] = field(default_factory=list)
    predictions: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    stale: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"communities": self.communities, "centrality": self.centrality,
                "crossovers": self.crossovers, "predictions": self.predictions,
                "contradictions": self.contradictions, "stale": self.stale}


def analyze(state: GraphState,
            previous: dict[str, set[str]] | None = None) -> Sidecar:
    comms = communities(state, previous)
    return Sidecar(
        communities={cid: sorted(m) for cid, m in sorted(comms.items())},
        centrality=centrality(state),
        crossovers=crossovers(state),
        predictions=adamic_adar(state),
        contradictions=contradiction_sweep(state),
        stale=staleness_sweep(state),
    )
