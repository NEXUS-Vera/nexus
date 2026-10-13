"""The Graph API surface. Backend/05 §8.

    READ    query · neighbors · path · explain · frontier · contradictions
            · timeline · stats
    WRITE   propose · accept · reject          (agents: PROPOSE only)
    HUMAN   validate · retract                 ⭐ never an agent

⭐ Every call carries a role token whose capabilities are checked SERVER-SIDE.
No client-supplied capability claims — a client that could name its own
capabilities has none, and the whole confidence-tier guarantee (§2.1) collapses
into a naming convention.

stdlib only. This is a real surface, not a framework choice; swapping in
FastAPI later changes the transport and nothing else.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .agents import Cap
from .artifact import Session, measure, predict, show
from .curation import export
from .errors import MindGraphError
from .frontier import frontier, tensions
from .retrieve import explain, path, query
from .tenancy import GraphCache

# Capability bundles a token may be minted with. VALIDATE and RETRACT are
# absent by construction — there is no bundle that grants them to a caller
# that is not the signed-in human.
BUNDLES = {
    "reader": frozenset({Cap.READ_STRUCTURE, Cap.READ_FRONTIER}),
    "grounder": frozenset({Cap.READ_STRUCTURE, Cap.READ_CONTENT,
                           Cap.READ_FRONTIER, Cap.PROPOSE}),
    "critic": frozenset({Cap.READ_STRUCTURE, Cap.READ_TIMELINE,
                         Cap.VERIFY_SPAN, Cap.PROPOSE}),
    "human": frozenset({Cap.READ_STRUCTURE, Cap.READ_CONTENT,
                        Cap.READ_FRONTIER, Cap.READ_TIMELINE, Cap.PROPOSE,
                        Cap.VALIDATE, Cap.RETRACT}),
}


class ApiError(MindGraphError):
    def __init__(self, status: int, msg: str) -> None:
        super().__init__(msg)
        self.status = status


@dataclass
class Token:
    user: str
    bundle: str
    caps: frozenset[Cap]


@dataclass
class TokenStore:
    """⭐ Server-minted, in-memory, never parsed from the request.

    A token is an opaque lookup key. Nothing about it is decoded — so a
    forged one is not a weaker token, it is no token.
    """
    _by_secret: dict[str, Token] = field(default_factory=dict)

    def mint(self, user: str, bundle: str) -> str:
        if bundle not in BUNDLES:
            raise ApiError(400, f"unknown bundle {bundle!r}")
        tok = secrets.token_urlsafe(24)
        self._by_secret[tok] = Token(user, bundle, BUNDLES[bundle])
        return tok

    def resolve(self, secret: str | None) -> Token:
        if not secret or (t := self._by_secret.get(secret)) is None:
            raise ApiError(401, "no valid role token")
        return t

    def revoke(self, secret: str) -> None:
        self._by_secret.pop(secret, None)


def require(token: Token, *caps: Cap) -> None:
    missing = {c for c in caps} - token.caps
    if missing:
        raise ApiError(403, f"{token.bundle} lacks {sorted(c.value for c in missing)}")


@dataclass
class Api:
    """The routes. Deliberately transport-free so they are testable directly."""
    root: str = "users"
    tokens: TokenStore = field(default_factory=TokenStore)
    cache: GraphCache | None = None
    # ⭐ Injected, never constructed at import. `turn` is the only route that
    # needs a model, and building one eagerly would make every other route —
    # all of which are deterministic — fail to import without a key.
    agent: object | None = None
    embedder: object | None = None
    budget_usd: float | None = None

    def _agent(self):
        """Resolve the agent lazily: injected first, environment second.

        ⚠️ Returns None rather than raising. The caller decides how to refuse,
        because a missing endpoint is a 503 (the operator has not configured
        one) and not a 500 (something broke).
        """
        if self.agent is not None:
            return self.agent
        from .adapters import from_env
        agent, embedder, _ = from_env()
        if agent is not None and self.embedder is None:
            self.embedder = embedder
        self.agent = agent
        return agent

    def _session(self, user: str) -> Session:
        return Session.open(user, self.root)

    def _labels(self, s: Session) -> dict:
        from .cli import _labels
        return _labels(s)

    def handle(self, route: str, params: dict, secret: str | None,
               body: dict | None = None) -> dict:
        tok = self.tokens.resolve(secret)
        fn = ROUTES.get(route)
        if fn is None:
            raise ApiError(404, f"no route {route!r}")
        s = self._session(tok.user)
        try:
            return fn(self, s, tok, params, body or {})
        finally:
            s.close()


# ── READ ────────────────────────────────────────────────────────────────────

def _query(api, s, tok, p, _b):
    """⭐ Text search requires READ_CONTENT, and that is not an oversight.

    Hybrid seeding matches the query against node LABELS, which are user text.
    A role without content access has nothing to match — so it would receive an
    empty result set that reads as "nothing found" rather than "you may not
    look". Refusing loudly is the only honest option; structural routes
    (`neighbors`, `path`, `explain`) remain open to it.
    """
    require(tok, Cap.READ_STRUCTURE, Cap.READ_CONTENT)
    labels = api._labels(s)
    res = query(s.state(), p.get("q", ""), labels,
                lens=p.get("lens"), k=int(p.get("k", 25)))
    return {"results": [{"id": r.id, "score": r.score, "hops": r.hops,
                         "path": r.path,
                         **({"label": labels.get(r.id)}
                            if Cap.READ_CONTENT in tok.caps else {})}
                        for r in res]}


def _explain(api, s, tok, p, _b):
    require(tok, Cap.READ_STRUCTURE)
    return explain(s.state(), p["id"])


def _path(api, s, tok, p, _b):
    require(tok, Cap.READ_STRUCTURE)
    return {"path": path(s.state(), p["a"], p["b"])}


def _frontier(api, s, tok, p, _b):
    require(tok, Cap.READ_FRONTIER)
    return {"actions": [{"id": a.id, "kind": a.kind, "why": a.why,
                         "priority": a.priority}
                        for a in frontier(s.state(), limit=int(p.get("k", 3)))]}


def _contradictions(api, s, tok, p, _b):
    require(tok, Cap.READ_FRONTIER)
    return {"tensions": [{"a": t.a, "b": t.b, "kind": t.kind,
                          "level": t.level, "framing": t.framing}
                         for t in tensions(s.state())]}


def _timeline(api, s, tok, p, _b):
    require(tok, Cap.READ_TIMELINE)
    from .retrieve import timeline
    g = timeline(None, s.ledger, int(p["at"]))
    return {"nodes": len(g.nodes), "edges": len(g.edges), "at": int(p["at"])}


def _stats(api, s, tok, _p, _b):
    require(tok, Cap.READ_STRUCTURE)
    from .graph import stats
    return stats(s.state())


def _map(api, s, tok, p, _b):
    """The Map's subgraph — ranked and capped SERVER-SIDE.

    ⚠️ This route exists to delete a duplicate. The Map first shipped with its
    own Degree-of-Interest implementation in TypeScript, because the browser
    had no way to run the real one. Two implementations of one ranking
    function, in two languages, drift — and when they do the Map ranks
    differently from the Bench for reasons nobody can trace.

    ⭐ The client's copy was also strictly worse: `retrieve.rank` weighs six
    components (centrality · salience · outcome · confidence · learnability ·
    staleness) with weights that RAMP AS THE GRAPH AGES. A hand-rolled
    degree-plus-type score cannot express that, so the Map was quietly ranking
    by a different definition of "interesting" than everything else.
    """
    require(tok, Cap.READ_STRUCTURE)
    from .retrieve import cap as cap_results
    from .retrieve import expand, rank
    st = s.state()
    focus = p.get("focus")
    seeds = [focus] if focus and focus in st.nodes else []
    if not seeds:
        # No focus: seed on the frontier, which is what the student would open
        # the Map from anyway. An unseeded Map is a hairball with extra steps.
        seeds = [a.id for a in frontier(st, limit=5) if a.id in st.nodes]
    if not seeds:
        seeds = sorted(st.nodes)[:5]

    g, ppr = expand(st, seeds, p.get("lens"))
    k = int(p.get("k", 50))
    results = cap_results(rank(st, ppr, g, seeds, p.get("lens")), st, k)
    keep = {r.id for r in results}
    labels = api._labels(s) if Cap.READ_CONTENT in tok.caps else {}

    nodes = []
    for r in results:
        n = st.nodes[r.id]
        nodes.append({
            "id": r.id, "type": str(n.type).split(".")[-1],
            "kind": n.kind, "support": str(n.support).split(".")[-1],
            "strength": str(n.strength).split(".")[-1],
            "corroboration": n.corroboration,
            "single_method": n.single_method,
            "score": r.score, "hops": r.hops,
            **({"label": labels.get(r.id)} if labels else {}),
        })
    edges = [{"src": e.src, "dst": e.dst,
              "relation": str(e.relation).split(".")[-1]}
             for e in st.edges.values() if e.src in keep and e.dst in keep]
    return {"nodes": nodes, "edges": edges,
            "total": len(st.nodes), "held": max(0, len(st.nodes) - len(keep)),
            "seeds": seeds, "cap": k}


def _portable(api, s, tok, p, _b):
    """The graph plus everything needed to re-rank it CLIENT-SIDE. `§4.4`.

    ⭐ This is what makes the frontier work with no signal. The expensive half
    of ranking (PageRank, corroboration, staleness) is computed here once and
    shipped; the client does a weighted sum. A student at a bench can change
    focus and re-sort with no server and no model.

    ⚠️ Cacheable on purpose — the weight vector rides in the payload, so a
    cached copy cannot silently rank by last month's weights.
    """
    require(tok, Cap.READ_STRUCTURE)
    from .portable import to_portable
    labels = api._labels(s) if Cap.READ_CONTENT in tok.caps else None
    focus = p.get("focus")
    st = s.state()
    seeds = [focus] if focus and focus in st.nodes else \
        [a.id for a in frontier(st, limit=5) if a.id in st.nodes]
    return to_portable(st, seeds=seeds, labels=labels, lens=p.get("lens"))


def _companion(api, s, tok, p, _b):
    """The four supervisor moves, in one call. `companion.py`.

    ⭐ One route rather than four because they are read together — the Bench
    asks "what should this student see about themselves right now", and four
    round trips to answer one question is how a companion becomes a dashboard.
    """
    require(tok, Cap.READ_STRUCTURE)
    from .companion import bias, impact, recall_failures, transfer
    st = s.state()
    labels = api._labels(s) if Cap.READ_CONTENT in tok.caps else {}
    out: dict = {}

    if (nid := p.get("id")):
        im = impact(st, nid)
        out["impact"] = {
            "id": im.id, "direct": im.direct, "cascade": im.cascade,
            "unsupported_after": im.unsupported_after,
            "load_bearing": im.load_bearing,
        }
    if (text := p.get("q")):
        out["recall"] = [{"id": r.id, "label": r.label, "reason": r.reason,
                          "overlap": r.overlap, "kind": r.kind}
                         for r in recall_failures(st, text, labels)]

    arts = []
    for aid, n in st.nodes.items():
        if str(n.type).split(".")[-1] != "Artifact":
            continue
        try:
            arts.append(show(s, aid))
        except Exception:
            continue
    out["bias"] = [{"quantity": b.quantity, "n": b.n, "matched": b.matched,
                    "direction": b.direction, "median_error": b.median_error,
                    "advice": b.advice} for b in bias(arts)]
    out["transfer"] = transfer(st, labels)
    return out


def _log(api, s, tok, p, _b):
    """The project document, and the thing Share is published from.

    ⭐ VALIDATION order, not discovery order, and retractions are entries
    rather than deletions. A log that drops what was withdrawn is a
    write-up, and a write-up is precisely the artifact that destroys the
    evidence of competence (`Frontend/01 §4.6`).

    ⚠️ The head hash ships with it. Without it a reader cannot tell a record
    from a claim about a record — the whole point of publishing this is that
    someone can replay the ledger and see the predictions were not written
    afterwards.
    """
    require(tok, Cap.READ_STRUCTURE, Cap.READ_TIMELINE)
    from .events import EventType
    st = s.state()
    labels = api._labels(s) if Cap.READ_CONTENT in tok.caps else {}

    # ⭐ VALIDATED is the outcome path; RETRACTED and DEAD_END are the two
    # kinds of failure the design insists stay visible. Predictions arrive as
    # ACCEPTED like any other structure, so they are not entries here — they
    # are the `artifacts` list below, where predicted-vs-measured belongs.
    KEEP = {EventType.VALIDATED, EventType.RETRACTED, EventType.DEAD_END}
    entries = []
    for e in s.ledger.read():
        if e.type not in KEEP:
            continue
        ids = [n.get("id") for n in e.structural.get("nodes", []) if n.get("id")]
        # ⚠️ `target` is where a retraction names its subject. Missing it made
        # the one entry type that most needs a label — the withdrawal — render
        # as "0 items", which is the opposite of failures staying visible.
        ids += [x for x in (e.structural.get("artifact_id"),
                            e.structural.get("id"),
                            e.structural.get("target")) if x]
        entries.append({
            "seq": e.seq, "ts": e.ts, "type": str(e.type).split(".")[-1],
            "ids": ids,
            # ⚠️ labels only when the caller may read content — a shared page
            # minted with a reader token gets the SHAPE of the work and none
            # of the words, which is the intended degradation, not a bug.
            "labels": [labels[i] for i in ids if i in labels],
            "retracted": e.type is EventType.RETRACTED,
        })

    arts = []
    for nid, n in st.nodes.items():
        if str(n.type).split(".")[-1] != "Artifact":
            continue
        try:
            a = show(s, nid)
        except Exception:
            continue
        # ⚠️ Structural Artifact nodes exist that are neither predicted nor
        # measured — cold-start placeholders and method stubs. Publishing them
        # renders a blank row on Share, which reads as a bug in the record
        # rather than as an artifact nobody has run yet.
        if a.get("predicted") is None and a.get("measured") is None:
            continue
        arts.append(a)
    arts.sort(key=lambda a: a.get("id", ""))

    seq, head = s.ledger.head()
    return {"entries": entries, "artifacts": arts,
            "head": {"seq": seq, "hash": head, "verified": s.ledger.verify_chain()}}


def _export(api, s, tok, _p, _b):
    require(tok, Cap.READ_STRUCTURE, Cap.READ_CONTENT)
    return json.loads(export(s.state(), api._labels(s)))


# ── WRITE ───────────────────────────────────────────────────────────────────

def _turn(api, s, tok, p, body):
    """The turn protocol over HTTP — `ask`, the product's main verb.

    ⭐ READ_CONTENT, not PROPOSE. The turn RETURNS proposals; it does not write
    them. Nothing reaches the ledger until the caller comes back through
    `decide`, so requiring PROPOSE here would grant write intent to a read.
    The content requirement is `_query`'s argument verbatim: retrieval seeds on
    labels, and a role that cannot read them gets an empty answer that lies
    about why.

    ⚠️ Refuses loudly with 503 when no endpoint is configured. Everything else
    in this API is deterministic and works with no key at all; silently
    returning a keyword-search result dressed as an answer would make the one
    route that needs a model indistinguishable from the ones that don't.
    """
    require(tok, Cap.READ_STRUCTURE, Cap.READ_CONTENT)
    question = (body.get("question") or p.get("q", [""])[0] or "").strip()
    if not question:
        raise ApiError(400, "no question")

    agent = api._agent()
    if agent is None:
        raise ApiError(503, "no model endpoint configured — set MG_ENDPOINT "
                            "and MG_API_KEY. Every other route is "
                            "deterministic and needs neither.")

    from .agents import run_turn
    g, labels = s.state(), api._labels(s)
    vecs = s.vectors().all() if api.embedder else None
    k = int(body.get("k", 12))
    hits = query(g, question, labels, k=k, embedder=api.embedder, vectors=vecs)
    budget = body.get("budget_usd", api.budget_usd)
    t = run_turn(g, question, [r.id for r in hits], agent, labels=labels,
                 budget_usd=float(budget) if budget is not None else None)

    from .evaluation import cost_per_accepted
    return {
        "question": question,
        "answer": t.answer,
        "seeds": [r.id for r in hits],
        "proposals": t.proposals,
        "critique": t.critique,
        # ⭐ Rejections are part of the reply, not a log line. A turn that
        # discarded four proposals and says nothing looks like a turn that
        # found four — and the gate's reasons are the most legible evidence
        # that capability binding is doing anything at all.
        "rejected": [{"reason": r.reason, "item": r.item} for r in t.rejected],
        "role_calls": t.role_calls,
        "escalated": t.escalated,
        "degraded": t.degraded,
        "cost": cost_per_accepted(t.cost_rows, t.accepted_count),
    }


def _propose(api, s, tok, _p, body):
    """⚠️ A proposal is not a write. It becomes structure only via the gate."""
    require(tok, Cap.PROPOSE)
    from .events import EventType
    if not body.get("basis"):
        raise ApiError(400, "no basis — an unjustified claim is rejected")
    seq = s.ledger.append(tok.user, EventType.PROPOSED,
                          {"edges": body.get("edges", []),
                           "basis": sorted(body["basis"])})
    return {"proposal_seq": seq, "status": "pending"}


# ── HUMAN-ONLY ──────────────────────────────────────────────────────────────

def _validate(api, s, tok, _p, body):
    """⭐⭐ If AI could write "this worked", the record of what worked becomes
    fiction — and that record is the entire asset."""
    require(tok, Cap.VALIDATE)
    return measure(s, body["artifact_id"], value=body.get("value"),
                   unit=body.get("unit"), raw_ref=body.get("raw_ref"))


def _predict(api, s, tok, _p, body):
    require(tok, Cap.VALIDATE)
    aid = predict(s, label=body["label"], quantity=body["quantity"],
                  low=float(body["low"]), high=float(body["high"]),
                  unit=body["unit"], supports=body.get("supports", []),
                  method=body.get("method"))
    return show(s, aid)


def _retract(api, s, tok, _p, body):
    require(tok, Cap.RETRACT)
    from .events import EventType
    seq = s.ledger.append(tok.user, EventType.RETRACTED,
                          {"target": body["target"]})
    return {"seq": seq}


def _neighbors(api, s, tok, p, _b):
    require(tok, Cap.READ_STRUCTURE)
    from .graph import neighbors
    return {"nodes": sorted(neighbors(s.state(), p["id"], int(p.get("hops", 1))))}


def _review(api, s, tok, _p, _b):
    """⭐ AMBIGUOUS only. Everything the extractor was confident about is
    already in the graph, flagged and reversible."""
    require(tok, Cap.READ_STRUCTURE)
    from .proposals import pending_review
    return {"pending": pending_review(s)}


def _decide(api, s, tok, _p, body):
    require(tok, Cap.PROPOSE)
    from .proposals import decide
    n = decide(s, body.get("ids", []), accept=bool(body.get("accept")))
    return {"decided": n}


def _ingest(api, s, tok, _p, body):
    """⚠️ Content, so it needs READ_CONTENT — you cannot add text you may not
    read."""
    require(tok, Cap.PROPOSE, Cap.READ_CONTENT)
    from .extract import FakeLLM, ingest_text
    from .proposals import ingest
    rep = ingest(s, ingest_text(body["name"], body.get("text", ""), FakeLLM()))
    return rep.as_dict()


def _nudge(api, s, tok, _p, _b):
    require(tok, Cap.READ_STRUCTURE)
    from .curation import structuring_nudge
    n = structuring_nudge(s.state())
    return {"triggered": n.triggered, "ratio": n.ratio,
            "outstanding": len(n.outstanding), "reason": n.reason}


def _calibration(api, s, tok, _p, _b):
    """Structural only — survives erasure by construction."""
    require(tok, Cap.READ_STRUCTURE)
    from .artifact import calibration
    return calibration(s)


def _analyze(api, s, tok, _p, _b):
    """Crossovers, communities, contradictions, staleness. Off the request
    path in production; synchronous here because the demo is small."""
    require(tok, Cap.READ_STRUCTURE)
    from .analyzer import analyze
    return analyze(s.state()).as_dict()


def _resurrections(api, s, tok, _p, _b):
    require(tok, Cap.READ_FRONTIER)
    from .frontier import resurrected
    return {"resurrected": resurrected(s.state())}


def _start(api, s, tok, _p, body):
    """Cold start. ⭐ The graph is never empty."""
    require(tok, Cap.VALIDATE)          # it is the human's project to create
    from .coldstart import seed_project
    return seed_project(s, body["question"],
                        transcript=body.get("transcript", "")).as_dict()


ROUTES = {
    "query": _query, "explain": _explain, "path": _path,
    "neighbors": _neighbors,
    "frontier": _frontier, "contradictions": _contradictions,
    "resurrections": _resurrections,
    "timeline": _timeline, "stats": _stats, "export": _export, "log": _log,
    "map": _map, "portable": _portable, "companion": _companion,
    "review": _review, "nudge": _nudge, "calibration": _calibration,
    "analyze": _analyze,
    "turn": _turn,
    "propose": _propose, "decide": _decide, "ingest": _ingest,
    "predict": _predict, "validate": _validate, "retract": _retract,
    "start": _start,
}


# ── transport ───────────────────────────────────────────────────────────────

# ⚠️ Security audit finding, fixed: this used to be `Access-Control-Allow-
# Origin: *`. That's harmless for a truly public read-only API, but every
# route here is behind a bearer token, and a wildcard tells the BROWSER it is
# fine to let arbitrary origins read authenticated responses — the auth model
# and the CORS policy have to agree, and they didn't.
#
# Fixed by reflecting the request's Origin header ONLY when it is on an
# allowlist, which is the standard pattern for a credentialed API. Default
# list covers the dev ports this repo actually uses (the static demo server,
# Vite dev, Vite preview). Override with MG_CORS_ORIGINS (comma-separated) for
# anything else — never with `*`.
DEFAULT_CORS_ORIGINS = frozenset({
    "http://127.0.0.1:8899", "http://localhost:8899",   # demo static server
    "http://127.0.0.1:5173", "http://localhost:5173",   # vite dev
    "http://127.0.0.1:3000", "http://localhost:3000",   # vite preview
})


def _cors_origins() -> frozenset[str]:
    raw = os.environ.get("MG_CORS_ORIGINS")
    if not raw:
        return DEFAULT_CORS_ORIGINS
    return frozenset(o.strip() for o in raw.split(",") if o.strip())


def make_handler(api: Api):
    allowed_origins = _cors_origins()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            origin = self.headers.get("Origin")
            if origin and origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "authorization,content-type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _route(self, body: dict | None) -> None:
            u = urlparse(self.path)
            params = {k: v[0] for k, v in parse_qs(u.query).items()}
            secret = (self.headers.get("Authorization") or "").removeprefix(
                "Bearer ").strip() or None
            try:
                self._send(200, api.handle(u.path.strip("/"), params, secret,
                                           body))
            except ApiError as exc:
                self._send(exc.status, {"error": str(exc)})
            except (KeyError, ValueError) as exc:
                self._send(400, {"error": f"bad request: {exc}"})
            except MindGraphError as exc:
                self._send(409, {"error": str(exc)})

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
            self._route(None)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "body is not JSON"})
            self._route(body)

        def log_message(self, *a):    # quiet by default
            pass

    return Handler


def serve(api: Api, host: str = "127.0.0.1", port: int = 8787):
    srv = ThreadingHTTPServer((host, port), make_handler(api))
    return srv
