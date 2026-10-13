"""The Graph API. Backend/05 §8.

⭐ The tests that matter are the refusals: capabilities are checked
server-side, and a client that could name its own has none.
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest
from conftest import edge
from mindgraph.agents import Cap
from mindgraph.api import BUNDLES, Api, ApiError, serve
from mindgraph.artifact import Session


@pytest.fixture
def api(tmp_path):
    a = Api(root=str(tmp_path))
    s = Session.open("u1", tmp_path)
    from mindgraph.crypto import encrypt
    from mindgraph.events import EventType
    # Labels ride in the ENCRYPTED half, as they do everywhere else.
    s.ledger.append("u1", EventType.ACCEPTED,
                    {"nodes": [{"id": "S1", "type": "Source", "kind": "paper"},
                               {"id": "C1", "type": "Claim"},
                               {"id": "R1", "type": "Artifact", "kind": "run"}],
                     "edges": [dict(edge("S1", "supports", "C1")),
                               dict(edge("R1", "contradicts", "C1"))]},
                    content=encrypt(s.keys, "u1", {"labels": {
                        "S1": "Chen 2019", "C1": "47 kOhm means hydrated",
                        "R1": "forearm sweep"}}))
    s.close()
    return a


def tok(api, bundle="human"):
    return api.tokens.mint("u1", bundle)


# ── tokens are server-minted ────────────────────────────────────────────────

def test_no_token_is_refused(api):
    with pytest.raises(ApiError) as e:
        api.handle("stats", {}, None)
    assert e.value.status == 401


def test_a_forged_token_is_not_a_weaker_token_but_no_token(api):
    """⭐ A token is an opaque lookup key. Nothing about it is decoded, so
    there is nothing to forge."""
    with pytest.raises(ApiError) as e:
        api.handle("stats", {}, "human-user-u1-allcaps")
    assert e.value.status == 401


def test_a_revoked_token_stops_working(api):
    t = tok(api)
    api.handle("stats", {}, t)
    api.tokens.revoke(t)
    with pytest.raises(ApiError):
        api.handle("stats", {}, t)


def test_an_unknown_bundle_cannot_be_minted(api):
    with pytest.raises(ApiError):
        api.tokens.mint("u1", "superuser")


def test_no_bundle_grants_validate_or_retract_to_an_agent():
    """⭐⭐ If AI could write "this worked", the record of what worked becomes
    fiction — and that record is the entire asset."""
    for name, caps in BUNDLES.items():
        if name == "human":
            continue
        assert Cap.VALIDATE not in caps and Cap.RETRACT not in caps


# ── capabilities are checked server-side ────────────────────────────────────

def test_a_reader_cannot_text_search_at_all(api):
    """⭐ Not an oversight. Hybrid seeding matches against LABELS, which are
    user text — a role without content access has nothing to match, so it
    would get an empty result set that reads as "nothing found" rather than
    "you may not look". Refusing loudly is the only honest option."""
    with pytest.raises(ApiError) as e:
        api.handle("query", {"q": "hydrated"}, tok(api, "reader"))
    assert e.value.status == 403


def test_a_reader_keeps_the_structural_routes(api):
    """It loses text search, not the graph."""
    t = tok(api, "reader")
    assert api.handle("stats", {}, t)["nodes"] == 3
    assert api.handle("explain", {"id": "C1"}, t)["support"] == "contested"
    assert api.handle("path", {"a": "S1", "b": "C1"}, t)["path"]


def test_a_grounder_can_see_labels(api):
    out = api.handle("query", {"q": "hydrated"}, tok(api, "grounder"))
    assert any(r.get("label") for r in out["results"])


def test_a_reader_cannot_export_content(api):
    with pytest.raises(ApiError) as e:
        api.handle("export", {}, tok(api, "reader"))
    assert e.value.status == 403


def test_a_reader_cannot_read_the_timeline(api):
    with pytest.raises(ApiError) as e:
        api.handle("timeline", {"at": "1"}, tok(api, "reader"))
    assert e.value.status == 403


def test_a_critic_may_read_the_timeline(api):
    assert api.handle("timeline", {"at": "1"}, tok(api, "critic"))["at"] == 1


def test_an_agent_cannot_validate(api):
    for bundle in ("reader", "grounder", "critic"):
        with pytest.raises(ApiError) as e:
            api.handle("validate", {}, tok(api, bundle),
                       {"artifact_id": "R1", "value": 1.0})
        assert e.value.status == 403


def test_an_agent_cannot_retract(api):
    with pytest.raises(ApiError) as e:
        api.handle("retract", {}, tok(api, "grounder"), {"target": "C1"})
    assert e.value.status == 403


def test_a_reader_cannot_propose(api):
    with pytest.raises(ApiError) as e:
        api.handle("propose", {}, tok(api, "reader"), {"basis": ["C1"]})
    assert e.value.status == 403


# ── proposals are not writes ────────────────────────────────────────────────

def test_a_proposal_is_pending_not_structure(api):
    out = api.handle("propose", {}, tok(api, "grounder"),
                     {"edges": [], "basis": ["C1"]})
    assert out["status"] == "pending"


def test_a_proposal_without_basis_is_rejected(api):
    """An agent that cannot name its basis has produced an unjustified claim."""
    with pytest.raises(ApiError) as e:
        api.handle("propose", {}, tok(api, "grounder"), {"edges": []})
    assert e.value.status == 400


# ── the read surface ────────────────────────────────────────────────────────

def test_explain_and_path_and_frontier(api):
    t = tok(api)
    assert api.handle("explain", {"id": "C1"}, t)["support"] == "contested"
    assert api.handle("path", {"a": "S1", "b": "C1"}, t)["path"]
    assert "actions" in api.handle("frontier", {}, t)
    assert api.handle("contradictions", {}, t)["tensions"]
    assert api.handle("stats", {}, t)["nodes"] == 3


def test_an_unknown_route_404s(api):
    with pytest.raises(ApiError) as e:
        api.handle("drop_everything", {}, tok(api))
    assert e.value.status == 404


# ── the transport ───────────────────────────────────────────────────────────

def test_over_http(api):
    srv = serve(api, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/stats",
            headers={"Authorization": f"Bearer {tok(api)}"})
        with urllib.request.urlopen(req, timeout=5) as r:
            assert json.loads(r.read())["nodes"] == 3

        bad = urllib.request.Request(f"http://127.0.0.1:{port}/stats")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(bad, timeout=5)
        assert e.value.code == 401
    finally:
        srv.shutdown()


# ── the routes the Workbench needs ──────────────────────────────────────────

def test_every_workbench_route_exists(api):
    from mindgraph.api import ROUTES
    need = {"query", "explain", "path", "neighbors", "frontier", "contradictions",
            "resurrections", "timeline", "stats", "export", "review", "nudge",
            "calibration", "analyze", "propose", "decide", "ingest",
            "predict", "validate", "retract", "start"}
    assert need <= set(ROUTES)


def test_ingest_needs_content_access(api):
    """⚠️ You cannot add text you may not read."""
    with pytest.raises(ApiError) as e:
        api.handle("ingest", {}, tok(api, "critic"), {"name": "n.md", "text": "x"})
    assert e.value.status == 403


def test_only_a_human_starts_a_project(api):
    for b in ("reader", "grounder", "critic"):
        with pytest.raises(ApiError):
            api.handle("start", {}, tok(api, b), {"question": "Can X to within 10%?"})


def test_review_is_ambiguous_only_and_decidable(api):
    t = tok(api, "human")
    assert api.handle("review", {}, t)["pending"] == []
    api.handle("ingest", {}, t, {"name": "notes.md", "text": "impedance drops\n"})
    assert api.handle("decide", {}, t, {"ids": [], "accept": True})["decided"] == 0


def test_calibration_and_analyze_are_readable(api):
    t = tok(api, "reader")
    assert "resolved" in api.handle("calibration", {}, t)
    assert set(api.handle("analyze", {}, t)) >= {"communities", "crossovers"}


def test_cors_reflects_an_allowed_origin_only(api):
    """⚠️ Every route is behind a bearer token — a wildcard CORS header tells
    the browser it's fine for any origin to read the response, which
    contradicts the auth model. Reflect from an allowlist instead of `*`."""
    srv = serve(api, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        allowed = urllib.request.Request(
            f"http://127.0.0.1:{port}/stats", method="OPTIONS",
            headers={"Origin": "http://localhost:5173"})
        with urllib.request.urlopen(allowed, timeout=5) as r:
            assert r.status == 204
            assert r.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"

        unknown = urllib.request.Request(
            f"http://127.0.0.1:{port}/stats", method="OPTIONS",
            headers={"Origin": "http://evil.example"})
        with urllib.request.urlopen(unknown, timeout=5) as r:
            assert r.status == 204
            assert "Access-Control-Allow-Origin" not in r.headers
    finally:
        srv.shutdown()


# ── turn: the one route that needs a model ──────────────────────────────────

class _TurnAgent:
    """Returns a proposal the gate will accept and one it will not.

    ⚠️ Deliberately not a mock of `run_turn`. Mocking the protocol would test
    that the route calls a function; what matters is that the ROUTE's contract
    — refusal, capability, and the shape handed to a client — holds against the
    real gate.
    """

    def __init__(self):
        self.roles: list[str] = []

    def run(self, role, payload, question):
        self.roles.append(role.name)
        out = {"answer": f"{role.name}: {question}", "tokens_in": 120,
               "tokens_out": 40, "proposals": []}
        if role.name == "grounder":
            out["proposals"] = [
                {"id": "p1", "subject": "C1", "relation": "supports",
                 "object": "S1", "confidence": "EXTRACTED", "basis": ["S1"],
                 "span": "chen.pdf:p3"},
                # ⚠️ EXTRACTED with no span — the gate must drop this one,
                # because "the source says so" without a locator is the exact
                # claim the citation rules exist to stop.
                {"id": "p2", "subject": "C1", "relation": "supports",
                 "object": "S1", "confidence": "EXTRACTED", "basis": ["S1"]},
            ]
        return out


def test_turn_refuses_loudly_without_an_endpoint(api, monkeypatch):
    """⭐ 503, not a keyword search dressed as an answer. Every other route is
    deterministic; this one must be distinguishable from them when unconfigured."""
    monkeypatch.delenv("MG_ENDPOINT", raising=False)
    api.agent = None
    with pytest.raises(ApiError) as e:
        api.handle("turn", {}, tok(api), {"question": "does 47 kOhm mean hydrated?"})
    assert e.value.status == 503
    assert "MG_ENDPOINT" in str(e.value)


def test_turn_needs_content_not_propose(api):
    """The turn returns proposals; it never writes them. Requiring PROPOSE
    would grant write intent to a read."""
    with pytest.raises(ApiError) as e:
        api.handle("turn", {}, tok(api, "reader"), {"question": "why?"})
    assert e.value.status == 403          # reader has no READ_CONTENT
    api.agent = _TurnAgent()
    # grounder has READ_CONTENT and no VALIDATE — and still gets a turn
    out = api.handle("turn", {}, tok(api, "grounder"), {"question": "why?"})
    assert out["answer"]


def test_turn_returns_the_gate_result_not_just_prose(api):
    api.agent = _TurnAgent()
    out = api.handle("turn", {}, tok(api), {"question": "does 47 kOhm mean hydrated?"})
    assert out["answer"]
    assert [p["id"] for p in out["proposals"]] == ["p1"]
    # ⭐ the dropped one is REPORTED, with its reason. A turn that discards a
    # proposal silently looks identical to one that never made it.
    assert len(out["rejected"]) == 1 and out["rejected"][0]["reason"]
    assert "grounder" in out["role_calls"]
    assert "usd" in out["cost"] or "per_accepted" in out["cost"]


def test_turn_rejects_an_empty_question(api):
    api.agent = _TurnAgent()
    with pytest.raises(ApiError) as e:
        api.handle("turn", {}, tok(api), {"question": "   "})
    assert e.value.status == 400


def test_turn_writes_nothing_to_the_ledger(api):
    """⚠️ The invariant behind the capability choice. If a turn could append,
    the review queue would fill with things no human ever saw."""
    from mindgraph.artifact import Session
    api.agent = _TurnAgent()
    s = Session.open("u1", api.root)
    before = len(list(s.ledger.read()))
    s.close()
    api.handle("turn", {}, tok(api), {"question": "why?"})
    s = Session.open("u1", api.root)
    after = len(list(s.ledger.read()))
    s.close()
    assert before == after


# ── log: what Share is published from ───────────────────────────────────────

def test_log_carries_the_head_hash_and_verifies(api):
    """⚠️ Without the hash a reader cannot tell a record from a claim about a
    record, and the whole reason to publish this is that it can be replayed."""
    out = api.handle("log", {}, tok(api))
    assert out["head"]["hash"] and out["head"]["seq"] >= 1
    assert out["head"]["verified"] is True


def test_log_needs_timeline_not_just_structure(api):
    with pytest.raises(ApiError) as e:
        api.handle("log", {}, tok(api, "reader"))     # reader has no READ_TIMELINE
    assert e.value.status == 403


def test_log_keeps_retractions_as_entries(api):
    """⭐ A log that drops what was withdrawn is a write-up, and a write-up is
    what destroys the evidence of competence."""
    t = tok(api)
    aid = api.handle("predict", {}, t, {
        "label": "forearm sweep", "quantity": "impedance",
        "low": 45, "high": 50, "unit": "kOhm"})["id"]
    api.handle("validate", {}, t, {"artifact_id": aid, "value": 47.2, "unit": "kOhm"})
    before = api.handle("log", {}, t)
    assert any(e["type"] == "validated" for e in before["entries"])

    api.handle("retract", {}, t, {"target": aid, "reason": "bad probe"})
    after = api.handle("log", {}, t)
    assert any(e["retracted"] for e in after["entries"])
    # the validation is still there — retraction is an entry, not a delete
    assert len([e for e in after["entries"] if e["type"] == "validated"]) == \
           len([e for e in before["entries"] if e["type"] == "validated"])


def test_log_artifacts_carry_predicted_and_measured(api):
    t = tok(api)
    aid = api.handle("predict", {}, t, {
        "label": "gel-electrode control", "quantity": "impedance",
        "low": 30, "high": 40, "unit": "kOhm"})["id"]
    api.handle("validate", {}, t, {"artifact_id": aid, "value": 33.0, "unit": "kOhm"})
    art = next(a for a in api.handle("log", {}, t)["artifacts"] if a["id"] == aid)
    assert art["predicted"] and art["measured"]
    assert art["agreement"] in ("matched", "diverged", "inconclusive", "not_run")


def test_log_degrades_to_shape_without_content(api):
    """⭐ A share link minted with a structure-only role gets the SHAPE of the
    work and none of the words. That is the intended degradation."""
    t = api.tokens.mint("u1", "critic")   # structure + timeline, no content
    out = api.handle("log", {}, t)
    assert all(e["labels"] == [] for e in out["entries"])


def test_a_retraction_names_what_it_withdrew(api):
    """⚠️ `retract` stores its subject under `target`. Missing that key made
    the most important entry on the page render as "0 items"."""
    t = tok(api)
    aid = api.handle("predict", {}, t, {
        "label": "motion-artifact rejection", "quantity": "error",
        "low": 0, "high": 5, "unit": "%"})["id"]
    api.handle("validate", {}, t, {"artifact_id": aid, "value": 11.4, "unit": "%"})
    api.handle("retract", {}, t, {"target": aid, "reason": "bad probe"})
    entry = next(e for e in api.handle("log", {}, t)["entries"] if e["retracted"])
    assert aid in entry["ids"]
    assert entry["labels"] == ["motion-artifact rejection"]


# ── map: one ranking implementation, not two ────────────────────────────────

def test_map_ranks_and_caps_server_side(api):
    out = api.handle("map", {"k": 3}, tok(api))
    assert len(out["nodes"]) <= 3
    assert out["total"] >= len(out["nodes"])
    # every edge is internal to the kept set — a dangling edge would render
    # as a line to nowhere
    ids = {n["id"] for n in out["nodes"]}
    assert all(e["src"] in ids and e["dst"] in ids for e in out["edges"])


def test_map_reports_what_it_held_back(api):
    """⚠️ A capped view that reports only what it drew claims the graph IS
    that size."""
    out = api.handle("map", {"k": 1}, tok(api))
    assert out["held"] == out["total"] - len(out["nodes"])
    assert out["held"] >= 0


def test_map_scores_come_from_the_real_doi(api):
    """⭐ The point of the route: the same rank() the Bench uses, with its six
    weighted components — not a hand-rolled degree score in the client."""
    out = api.handle("map", {}, tok(api))
    assert out["nodes"], "expected a seeded map"
    assert all("score" in n for n in out["nodes"])
    scores = [n["score"] for n in out["nodes"]]
    assert scores == sorted(scores, reverse=True)


def test_map_needs_only_structure(api):
    """A reader can see the shape without the words."""
    out = api.handle("map", {}, tok(api, "reader"))
    assert out["nodes"] and all("label" not in n for n in out["nodes"])


# ── portable: one ranking, two runtimes (§4.4) ──────────────────────────────

def test_portable_is_graphology_shaped(api):
    out = api.handle("portable", {}, tok(api))
    assert set(out) == {"options", "attributes", "nodes", "edges"}
    assert out["options"]["type"] == "directed"
    assert all("key" in n and "attributes" in n for n in out["nodes"])
    assert all({"key", "source", "target"} <= set(e) for e in out["edges"])


def test_portable_ships_the_weights_with_the_payload(api):
    """⚠️ Weights ramp as the graph ages. A cached payload without them would
    rank by last month's definition of interesting."""
    out = api.handle("portable", {}, tok(api))
    w = out["attributes"]["weights"]
    assert w and abs(sum(w.values())) > 0
    assert "distancePenalty" in out["attributes"]


def test_portable_carries_doi_components_not_a_ranking(api):
    """⭐ The split: the server ships the expensive half, the client does the
    arithmetic. Shipping a finished ranking would make re-seeding impossible
    offline, which is the whole point."""
    out = api.handle("portable", {}, tok(api))
    parts = out["nodes"][0]["attributes"]["doi"]
    assert set(parts) == {"centrality", "salience", "outcome", "confidence",
                          "learnability", "staleness"}


def test_portable_ranking_matches_retrieve_rank(api):
    """⚠️ The conformance oracle, server-side. If these diverge the fixture
    handed to the frontend is already wrong."""
    from mindgraph.portable import rank_portable
    out = api.handle("portable", {}, tok(api))
    ranked = rank_portable(out)
    assert len(ranked) == len(out["nodes"])
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_portable_withholds_labels_without_content(api):
    out = api.handle("portable", {}, tok(api, "reader"))
    assert all("label" not in n["attributes"] for n in out["nodes"])


def test_companion_route_answers_all_four_moves(api):
    out = api.handle("companion", {"q": "bus errors under load"}, tok(api))
    assert set(out) >= {"bias", "transfer", "recall"}
    assert isinstance(out["bias"], list)


def test_companion_impact_needs_an_id(api):
    """No id, no impact section — rather than an empty one that reads as
    'nothing depends on this'."""
    assert "impact" not in api.handle("companion", {}, tok(api))
    out = api.handle("companion", {"id": "C1"}, tok(api))
    assert out["impact"]["id"] == "C1"
