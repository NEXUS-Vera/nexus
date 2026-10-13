"""Adapters, vectors, snapshot persistence, costlog, and the CLI paths.

The tests here prove the PLUMBING — that every module has a reachable user
path and that the system degrades honestly when no endpoint is configured.
"""

from __future__ import annotations

import json

import pytest
from conftest import accept, node
from mindgraph.adapters import ROLE_PROMPT, TIER_MODELS, HTTPAgent, from_env
from mindgraph.agents import DEFAULT_ROLES
from mindgraph.artifact import Session
from mindgraph.cli import main
from mindgraph.costlog import CostLog
from mindgraph.projector import state_hash
from mindgraph.vectors import VectorStore

# ── adapters ────────────────────────────────────────────────────────────────


def test_no_endpoint_returns_nothing_rather_than_a_fake(monkeypatch):
    """⚠️ A missing key must not silently produce a stub that looks like a
    model call — the caller has to know it has no agent."""
    monkeypatch.delenv("MG_ENDPOINT", raising=False)
    assert from_env() == (None, None, None)


def test_from_env_builds_all_three():
    agent, emb, llm = from_env("https://x/v1", "k")
    assert agent and emb and llm


def test_every_role_has_a_prompt_and_a_model():
    for name, role in DEFAULT_ROLES.items():
        assert name in ROLE_PROMPT
        assert role.tier in TIER_MODELS


def test_the_planner_prompt_forbids_proposing():
    assert "Never emit `proposals`" in ROLE_PROMPT["planner"]


def test_the_synthesiser_prompt_states_it_has_seen_no_document():
    assert "not seen any document" in ROLE_PROMPT["synthesiser"]
    assert "never EXTRACTED" in ROLE_PROMPT["synthesiser"]


def test_the_critic_prompt_is_downgrade_only():
    assert "never raise one" in ROLE_PROMPT["critic"]


def test_a_failed_call_is_not_an_empty_answer():
    """⚠️ A network failure must not look like a model that found nothing."""
    a = HTTPAgent("http://127.0.0.1:1/v1", "k", max_retries=0, timeout=1)
    out = a.run(DEFAULT_ROLES["grounder"], {"nodes": []}, "q")
    assert out["error"] and out["proposals"] == []


def test_a_non_proposing_role_cannot_smuggle_proposals(monkeypatch):
    a = HTTPAgent("http://x/v1")
    monkeypatch.setattr(a, "_post", lambda *_: ({"answer": "x", "proposals": [{"id": "p"}]}, 1, 1))
    assert a.run(DEFAULT_ROLES["planner"], {}, "q")["proposals"] == []


# ── vectors ─────────────────────────────────────────────────────────────────


class FakeEmbedder:
    model = "fake"

    def embed(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.5]


def test_backfill_is_incremental():
    """A sidecar: a partial backfill degrades retrieval QUALITY, never
    correctness — the lexical seed always runs."""
    vs = VectorStore()
    labels = {"a": "impedance", "b": "capacitance"}
    assert vs.backfill(labels, FakeEmbedder()) == 2
    assert vs.backfill(labels, FakeEmbedder()) == 0  # nothing missing
    labels["c"] = "inductance"
    assert vs.backfill(labels, FakeEmbedder()) == 1
    assert set(vs.all()) == {"a", "b", "c"}


def test_unlabelled_nodes_are_skipped():
    vs = VectorStore()
    assert vs.backfill({"a": "", "b": "x"}, FakeEmbedder()) == 1


def test_embeddings_reach_retrieval(tmp_path):
    from mindgraph.retrieve import seed

    s = Session.open("u1", tmp_path)
    accept(s.ledger, [node("a"), node("b")])
    labels = {"a": "skin impedance", "b": "electrode drift"}
    vs = s.vectors()
    vs.backfill(labels, FakeEmbedder())
    got = seed(s.state(), "impedance", labels, FakeEmbedder(), vs.all())
    assert got
    s.close()


# ── snapshot persistence ────────────────────────────────────────────────────


def test_the_snapshot_is_a_cache_not_a_source(tmp_path):
    """⭐ Topped up from the ledger, never trusted. A stale snapshot is
    corrected; a corrupt one is just a cold cache."""
    s = Session.open("u1", tmp_path)
    accept(s.ledger, [node("C1")])
    first = state_hash(s.state())
    s.checkpoint()

    accept(s.ledger, [node("C2")])  # ledger moves past the cache
    assert state_hash(s.state()) != first
    assert "C2" in s.state().nodes
    s.close()


def test_a_corrupt_snapshot_degrades_to_a_full_replay(tmp_path):
    s = Session.open("u1", tmp_path)
    accept(s.ledger, [node("C1")])
    expected = state_hash(s.state())
    s.checkpoint()
    (tmp_path / "u1" / "graph.snapshot").write_text("{ not json")
    assert state_hash(s.state()) == expected
    s.close()


def test_closing_checkpoints(tmp_path):
    s = Session.open("u1", tmp_path)
    accept(s.ledger, [node("C1")])
    s.state()
    s.close()
    assert (tmp_path / "u1" / "graph.snapshot").exists()


# ── costlog ─────────────────────────────────────────────────────────────────


def test_operations_are_recorded_without_being_asked(tmp_path):
    """⭐ Instrumentation is opt-OUT. Nobody in this field has published real
    cost data, and the reason is always that the table went in too late."""
    s = Session.open("u1", tmp_path)  # the session owns its own sink
    accept(s.ledger, [node("C1")])
    s.state()
    assert "project" in {r[0] for r in s.costs.rows()}
    s.close()


def test_the_cost_log_records_timings():
    cl = CostLog()
    with cl.measure("thing", tag="x"):
        pass
    op, wall, cpu, tags = cl.rows()[0]
    assert op == "thing" and wall >= 0 and json.loads(tags)["tag"] == "x"


# ── the CLI paths ───────────────────────────────────────────────────────────


def _run(tmp_path, *args) -> int:
    return main(["--root", str(tmp_path), *args])


def test_every_new_command_is_reachable(tmp_path, capsys):
    assert _run(tmp_path, "start", "Can X track Y to within 10 percent?") == 0
    for cmd in (["nudge"], ["promote"], ["cost"], ["status"], ["export"]):
        assert _run(tmp_path, *cmd) == 0
    assert capsys.readouterr().out


def test_export_writes_a_file_you_own(tmp_path):
    _run(tmp_path, "start", "Can X track Y to within 10 percent?")
    out = tmp_path / "graph.json"
    assert _run(tmp_path, "export", "-o", str(out)) == 0
    assert json.loads(out.read_text())["schema_version"] == 1


def test_ask_without_an_endpoint_fails_loudly(tmp_path, capsys, monkeypatch):
    """⚠️ It must not fall back to a stub and look like it worked."""
    monkeypatch.delenv("MG_ENDPOINT", raising=False)
    assert _run(tmp_path, "ask", "what is X?") == 1
    assert "no endpoint" in capsys.readouterr().err


def test_embed_without_an_endpoint_fails_loudly(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MG_ENDPOINT", raising=False)
    assert _run(tmp_path, "embed") == 1


def test_one_users_rows_never_land_in_anothers_file(tmp_path):
    """⚠️ A process-global sink pinned to one user's directory means operating
    on user B after opening user A writes B's rows into A's file — a tenancy
    leak in the very table meant to prove we can measure ourselves."""
    a = Session.open("u1", tmp_path)
    accept(a.ledger, [node("C1")])
    a.state()
    b = Session.open("u2", tmp_path)
    accept(b.ledger, [node("C2")])
    b.state()
    assert len(b.costs.rows()) == 1  # not polluted by u1
    a.close()
    b.close()


def test_the_cost_table_survives_the_process(tmp_path):
    """⚠️ An in-memory log looks like it works and records nothing that
    outlives the run — which for a CLI means every row is discarded the
    instant it is written."""
    s = Session.open("u1", tmp_path)
    accept(s.ledger, [node("C1")])
    s.state()
    s.close()
    assert (tmp_path / "u1" / "costs.db").exists()

    from mindgraph.costlog import CostLog

    assert any(r[0] == "project" for r in CostLog(tmp_path / "u1" / "costs.db").rows())


# ── schema evolution ────────────────────────────────────────────────────────


def test_a_v1_event_upcasts_on_read():
    """⭐ The first real upcaster, and the proof the mechanism works.

    v1 edges recorded only `weight_sources` (event seqs), but independence is
    a property of WHO asserted a link. A v1 edge has exactly one asserter — its
    own `src` — and that is the only honest reconstruction.
    """
    from mindgraph.upcast import upcast

    v1 = {"edges": [{"id": "e1", "src": "S1", "dst": "C1"}]}
    assert upcast(v1, 1)["edges"][0]["weight_source_nodes"] == ["S1"]


def test_an_upcaster_never_improves_the_past():
    """⚠️ An upcaster that makes old data look better-evidenced is worse than
    none at all — every downstream number silently shifts."""
    from mindgraph.upcast import upcast

    out = upcast({"edges": [{"id": "e1", "src": "S1", "dst": "C1"}]}, 1)
    assert len(out["edges"][0]["weight_source_nodes"]) == 1


def test_a_v2_payload_is_untouched():
    from mindgraph.upcast import upcast

    p = {"edges": [{"id": "e1", "src": "S1", "weight_source_nodes": ["X"]}]}
    assert upcast(p, 2) == p


def test_a_future_schema_is_refused():
    """Reading a payload written by newer code must fail loudly."""
    from mindgraph.upcast import upcast

    with pytest.raises(ValueError, match="newer than this code"):
        upcast({}, 99)


def test_the_frozen_v1_ledger_still_projects_to_its_recorded_hash():
    """The golden fixture: any divergence without a matching upcaster is a P0."""
    import json as _json
    from pathlib import Path as _P

    from mindgraph.ledger import Ledger as _L
    from mindgraph.projector import project as _proj

    root = _P(__file__).resolve().parent / "golden"
    manifest = _json.loads((root / "manifest.json").read_text())
    for name, expected in sorted(manifest.items()):
        led = _L(root / name)
        try:
            assert state_hash(_proj(led.read())) == expected, name
        finally:
            led.close()
