"""Retrieval. Backend/01 §6, Backend/07 §5.

The most-corroborated finding in the whole research set — four independent
sources, no dissent:

    ⭐ Embeddings for the entry point. Graph traversal for the expansion.
       Never embeddings for the whole job.

    ① SEED      hybrid: embedding kNN + lexical over label+aliases -> 10 seeds
    ② EXPAND    Personalized PageRank from seeds, alpha = 0.15
    ③ RANK      DOI(x) = API(x) - D(x, focus·lens)
    ④ CAP       top-K. UI 50, 25 at cold start. Agent: token budget.

⭐ Why PPR rather than a vector index over the whole graph: PROVENANCE. Every
result is reachable by a printable path, and w3/w5 encode facts about *this
student* that no embedding can carry.

Measured at 27 ms for 10k nodes and 76 ms for 25k (Backend/09 Q11) — about
100x off the critical path next to a model call.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

import networkx as nx

from .graph import to_networkx
from .projector import GraphState
from .resolve import trigrams
from .schema import OPPOSING, SUPPORTING, Confidence, Rank, Relation, Strength

ALPHA = 0.15          # PPR restart
N_SEEDS = 10          # 5 embedding-kNN + 5 lexical, unioned
K_UI = 50             # the comprehension limit
K_COLD = 25
MAX_HOPS = 3
RAMP_EVENTS = 200     # weights mature over the first ~200 accepted events

# Backend/07 §5.1 — on day one salience and outcome are EMPTY, so weighting
# them weights noise. Learnability dominates early because it is the only
# signal that exists at t=0.
W_DAY1 = {"centrality": 0.30, "salience": 0.00, "outcome": 0.00,
          "confidence": 0.20, "learnability": 0.50, "staleness": -0.10}
W_MATURE = {"centrality": 0.20, "salience": 0.20, "outcome": 0.20,
            "confidence": 0.15, "learnability": 0.25, "staleness": -0.10}

LENSES = {
    "debug": {Relation.CONTRADICTS: 1.6, Relation.REFUTES: 1.6,
              Relation.MEASURED_BY: 1.4, Relation.REQUIRES: 1.2},
    "writeup": {Relation.CITES: 1.6, Relation.EVIDENCE_FOR: 1.5,
                Relation.SUPPORTS: 1.3},
    "learn": {Relation.REQUIRES: 1.8, Relation.RELATES_TO: 1.2},
    None: {},
}


class Embedder(Protocol):
    """Tier 1a. Absent until an endpoint exists — retrieval degrades to the
    lexical half of the hybrid seed rather than failing."""

    def embed(self, text: str) -> list[float]: ...


def maturity(state: GraphState) -> float:
    return min(1.0, state.last_seq / RAMP_EVENTS)


def weights(state: GraphState) -> dict[str, float]:
    m = maturity(state)
    return {k: W_DAY1[k] + (W_MATURE[k] - W_DAY1[k]) * m for k in W_DAY1}


# ── ① seed ──────────────────────────────────────────────────────────────────

def lexical_seeds(state: GraphState, query: str, labels: dict[str, str],
                  k: int = 5) -> list[tuple[str, float]]:
    """Trigram overlap with an IDF-ish rarity bonus. No model required."""
    qg = trigrams(query)
    df: dict[str, int] = {}
    grams = {nid: trigrams(text) for nid, text in labels.items()}
    for gs in grams.values():
        for g in gs:
            df[g] = df.get(g, 0) + 1
    n = max(1, len(labels))
    scored = []
    for nid, gs in grams.items():
        shared = qg & gs
        if not shared:
            continue
        s = sum(math.log(1 + n / df[g]) for g in shared) / math.sqrt(len(gs))
        scored.append((nid, round(s, 4)))
    return sorted(scored, key=lambda t: (-t[1], t[0]))[:k]


def seed(state: GraphState, query: str, labels: dict[str, str],
         embedder: Embedder | None = None,
         vectors: dict[str, list[float]] | None = None) -> list[str]:
    out = [nid for nid, _ in lexical_seeds(state, query, labels, k=N_SEEDS // 2)]
    if embedder and vectors:
        q = embedder.embed(query)
        def cos(v):
            d = math.sqrt(sum(a * a for a in q)) * math.sqrt(sum(b * b for b in v))
            return sum(a * b for a, b in zip(q, v, strict=False)) / d if d else 0.0
        knn = sorted(((nid, cos(v)) for nid, v in vectors.items()),
                     key=lambda t: (-t[1], t[0]))[:N_SEEDS // 2]
        out += [nid for nid, _ in knn]
    seen, uniq = set(), []
    for nid in out:                       # union, deduped, order stable
        if nid not in seen and nid in state.nodes:
            seen.add(nid)
            uniq.append(nid)
    return uniq


# ── ② expand ────────────────────────────────────────────────────────────────

def expand(state: GraphState, seeds: list[str], lens: str | None = None):
    g = to_networkx(state)
    if not g or not seeds:
        return g, {}
    boosts = LENSES.get(lens, {})
    for _, _, d in g.edges(data=True):
        d["ppr_weight"] = d.get("weight", 1) * boosts.get(
            Relation(d["relation"]), 1.0) if d.get("relation") else 1.0
    live = [s for s in seeds if s in g]
    if not live:
        return g, {}
    pers = {s: 1.0 / len(live) for s in live}
    ppr = nx.pagerank(nx.DiGraph(g), alpha=1 - ALPHA, personalization=pers,
                      weight="ppr_weight")
    return g, ppr


# ── ③ rank ──────────────────────────────────────────────────────────────────

def _outcome(state: GraphState, nid: str) -> float:
    """Did things built on this work? Uses the Artifact agreement field —
    the signal no competitor has."""
    outs = [state.nodes[e.src].labels_at.get("outcome")
            for e in state.edges.values()
            if e.dst == nid and e.src in state.nodes
            and e.rank is not Rank.DEPRECATED]
    scored = [o for o in outs if o in ("matched", "diverged")]
    if not scored:
        return 0.0
    return scored.count("matched") / len(scored)


def _confidence(state: GraphState, nid: str) -> float:
    live = [e for e in state.edges.values()
            if e.dst == nid and e.rank is not Rank.DEPRECATED]
    if not live:
        return 0.0
    best = {Confidence.EXTRACTED: 1.0, Confidence.INFERRED: 0.6,
            Confidence.AMBIGUOUS: 0.2}
    return max(best[e.confidence] for e in live)


def _learnable(state: GraphState, nid: str, known: set[str]) -> float:
    """Knowledge Space Theory: is every prerequisite already demonstrated?

    That is the formal definition of "ready to learn next", and at t=0 it is
    the only signal in the system that is not empty.
    """
    n = state.nodes[nid]
    if n.type.value != "Concept" or nid in known:
        return 0.0
    prereqs = [e.src for e in state.edges.values()
               if e.dst == nid and e.relation is Relation.REQUIRES
               and e.rank is not Rank.DEPRECATED]
    if not prereqs:
        return 0.5                              # a root: learnable, unremarkable
    return 1.0 if all(p in known for p in prereqs) else 0.0


SALIENCE_HALF_LIFE = 200        # in SEQ, not days — the projector has no clock


def _salience(state: GraphState, nid: str) -> float:
    """Access recency and count, decayed. ⭐ Measured in ledger position rather
    than wall-clock, because a clock in the projector breaks replay."""
    hits = state.access.get(nid)
    if not hits:
        return 0.0
    total = sum(0.5 ** ((state.last_seq - s) / SALIENCE_HALF_LIFE) for s in hits)
    return round(min(1.0, total / 3), 4)


def _stale(state: GraphState, nid: str) -> float:
    n = state.nodes[nid]
    return 1.0 if (n.valid_to or n.superseded_by or n.quarantined) else 0.0


def known_set(state: GraphState) -> set[str]:
    """Demonstrated, not read. A concept enters only via ESTABLISHED strength —
    one lucky measurement must not mark something learned."""
    return {nid for nid, n in state.nodes.items()
            if n.strength is Strength.ESTABLISHED}


@dataclass
class Result:
    id: str
    score: float
    doi: dict = field(default_factory=dict)
    hops: int | None = None
    path: list[str] = field(default_factory=list)


def rank(state: GraphState, ppr: dict, g, seeds: list[str],
         lens: str | None = None) -> list[Result]:
    w = weights(state)
    known = known_set(state)
    top = max(ppr.values()) if ppr else 1.0
    dist: dict[str, int] = {}
    if seeds:
        und = g.to_undirected(as_view=True)
        for s in seeds:
            if s in und:
                for nid, d in nx.single_source_shortest_path_length(
                        und, s, cutoff=MAX_HOPS).items():
                    dist[nid] = min(dist.get(nid, 99), d)

    out = []
    for nid in sorted(ppr):
        if nid not in state.nodes:
            continue
        parts = {
            "centrality": ppr[nid] / top if top else 0.0,
            "salience": _salience(state, nid),
            "outcome": _outcome(state, nid),
            "confidence": _confidence(state, nid),
            "learnability": _learnable(state, nid, known),
            "staleness": _stale(state, nid),
        }
        api = sum(w[k] * v for k, v in parts.items())
        d = dist.get(nid, MAX_HOPS + 1)
        out.append(Result(id=nid, score=round(api - 0.05 * d, 5),
                          doi=parts, hops=d))
    return sorted(out, key=lambda r: (-r.score, r.id))


# ── ④ cap ───────────────────────────────────────────────────────────────────

def cap(results: list[Result], state: GraphState,
        k: int | None = None) -> list[Result]:
    """⭐ The limit is HUMAN, not technical — by a factor of 500. Comprehension
    fails around 50 nodes; performance does not fail until 25,000. So there is
    no version of this where "show more" is the answer."""
    if k is None:
        k = K_COLD if state.last_seq < RAMP_EVENTS // 4 else K_UI
    return results[:k]


def query(state: GraphState, text: str, labels: dict[str, str], *,
          lens: str | None = None, k: int | None = None,
          embedder: Embedder | None = None,
          vectors: dict[str, list[float]] | None = None) -> list[Result]:
    from .costlog import default as costlog
    # Retrieval is a pure function of state, so it has no session to own its
    # log; the process default is correct here and carries no user identity.
    with costlog().measure("query", lens=lens or "none", nodes=len(state.nodes)):
        return _query(state, text, labels, lens=lens, k=k, embedder=embedder,
                      vectors=vectors)


def _query(state: GraphState, text: str, labels: dict[str, str], *,
           lens: str | None = None, k: int | None = None,
           embedder: Embedder | None = None,
           vectors: dict[str, list[float]] | None = None) -> list[Result]:
    seeds = seed(state, text, labels, embedder, vectors)
    g, ppr = expand(state, seeds, lens)
    if not ppr:
        return []
    results = cap(rank(state, ppr, g, seeds, lens), state, k)
    und = g.to_undirected(as_view=True)
    for r in results:                       # every result carries its path
        for s in seeds:
            if s in und and r.id in und:
                try:
                    r.path = nx.shortest_path(und, s, r.id)
                    break
                except nx.NetworkXNoPath:
                    continue
    return results


# ── the Graph API surface (Backend/05 §8) ───────────────────────────────────

def explain(state: GraphState, node_id: str) -> dict:
    """supports / contradicts / provenance. The answer to "why do I believe
    this?" — a backwards walk along what justified it."""
    if node_id not in state.nodes:
        return {}
    n = state.nodes[node_id]
    live = [e for e in state.edges.values()
            if e.dst == node_id and e.rank is not Rank.DEPRECATED]
    dead = [e for e in state.edges.values()
            if e.dst == node_id and e.rank is Rank.DEPRECATED]
    return {
        "id": node_id, "type": n.type.value, "kind": n.kind,
        "support": n.support.value, "strength": n.strength.value,
        "corroboration": n.corroboration, "single_method": n.single_method,
        "evidence_mass": n.evidence_mass, "contest_ratio": n.contest_ratio,
        "supported_by": sorted(e.src for e in live if e.relation in SUPPORTING),
        "contradicted_by": sorted(e.src for e in live if e.relation in OPPOSING),
        "retracted_support": sorted(e.src for e in dead
                                    if e.relation in SUPPORTING),
        "provenance": [e.provenance for e in sorted(live, key=lambda e: e.id)],
    }


def path(state: GraphState, a: str, b: str) -> list[str]:
    g = to_networkx(state).to_undirected()
    try:
        return nx.shortest_path(g, a, b)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def timeline(state_at, ledger, at_seq: int):
    """The graph as it stood at a past point. Free, because the ledger is the
    truth and `seq` is the only ordering."""
    from .projector import project
    return project(e for e in ledger.read() if e.seq <= at_seq)
