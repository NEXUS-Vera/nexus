"""Phase 1 — ingestion, validation, resolution, routing. Backend/03."""
from __future__ import annotations

import pytest

from mindgraph.artifact import Session
from mindgraph.crypto import KeyStore
from mindgraph.extract import (FakeLLM, extract_csv, extract_python,
                               ingest_text, route)
from mindgraph.ledger import Ledger, canonical
from mindgraph.proposals import decide, ingest, pending_review
from mindgraph.resolve import band_for, normalise, resolve_candidates, similarity
from mindgraph.validate import is_sentence_like, validate


@pytest.fixture
def s(tmp_path):
    sess = Session(user="u1", ledger=Ledger(tmp_path / "l.db"),
                   keys=KeyStore(tmp_path / "k.json"))
    sess.keys.create("u1")
    yield sess
    sess.close()


# ── the deterministic lane: 0 tokens, EXTRACTED 1.0 ─────────────────────────

def test_python_is_parsed_not_modelled():
    f = extract_python("def read_adc():\n    pass\n\ndef main():\n    read_adc()\n",
                       "driver.py")
    assert all(e["confidence"] == "EXTRACTED" and e["score"] == 1.0
               for e in f["edges"])
    assert {n["label"] for n in f["nodes"]} == {"driver.py", "read_adc", "main"}
    assert any(e["relation"] == "relates_to" for e in f["edges"])   # the call


def test_broken_python_degrades_instead_of_raising():
    f = extract_python("def (((", "bad.py")
    assert len(f["nodes"]) == 1 and f["edges"] == []


def test_csv_columns_become_measured_quantities():
    f = extract_csv("freq_hz,impedance_kohm\n50000,47.2\n", "sweep.csv")
    assert any(n["label"] == "impedance_kohm" for n in f["nodes"])
    assert all(e["relation"] == "measured_by" for e in f["edges"])


def test_routing():
    assert route("a.py") == "code" and route("a.csv") == "data"
    assert route("a.pdf") == "document" and route("a.md") == "text"


# ── the validator ───────────────────────────────────────────────────────────

def test_sentence_like_labels_are_demoted_to_notes():
    """The #1 failure mode of LLM-built graphs: prose becomes nodes."""
    v = validate({"nodes": [{"key": "k1", "type": "Claim",
                             "label": "The 5V rail is noisy because the "
                                      "regulator is undersized."}]})
    assert v.nodes[0]["type"] == "Note"
    assert len(v.nodes[0]["label"]) <= 60
    assert v.nodes[0]["body"].startswith("The 5V rail")


def test_is_sentence_like():
    assert is_sentence_like("This is a sentence.")
    assert not is_sentence_like("skin impedance")


def test_off_rubric_scores_are_rejected():
    v = validate({"nodes": [{"key": "a", "type": "Claim", "label": "x"},
                            {"key": "b", "type": "Claim", "label": "y"}],
                  "edges": [{"src_key": "a", "dst_key": "b",
                             "relation": "supports", "confidence": "INFERRED",
                             "score": 0.5}]})
    assert v.edges == [] and v.rejects[0].reason == "off-rubric score"


def test_extracted_without_a_relevant_passage_is_rejected():
    v = validate({"nodes": [{"key": "a", "type": "Claim", "label": "x"},
                            {"key": "b", "type": "Claim", "label": "y"}],
                  "edges": [{"src_key": "a", "dst_key": "b",
                             "relation": "supports", "confidence": "EXTRACTED",
                             "score": 1.0, "citation_state": "present_weak"}]})
    assert "directly-supporting" in v.rejects[0].reason


def test_weak_citation_is_demoted_not_dropped():
    v = validate({"nodes": [{"key": "a", "type": "Claim", "label": "x"},
                            {"key": "b", "type": "Claim", "label": "y"}],
                  "edges": [{"src_key": "a", "dst_key": "b",
                             "relation": "supports", "confidence": "INFERRED",
                             "score": 0.95, "citation_state": "present_weak",
                             "span": "p:1"}]})
    assert v.edges[0]["score"] == 0.75


def test_wrong_source_becomes_ambiguous():
    v = validate({"nodes": [{"key": "a", "type": "Claim", "label": "x"},
                            {"key": "b", "type": "Claim", "label": "y"}],
                  "edges": [{"src_key": "a", "dst_key": "b",
                             "relation": "supports", "confidence": "INFERRED",
                             "score": 0.95, "citation_state": "wrong_source",
                             "span": "p:1"}]})
    assert v.edges[0]["confidence"] == "AMBIGUOUS" and v.edges[0]["score"] == 0.3


def test_dangling_and_self_loops_are_rejected():
    v = validate({"nodes": [{"key": "a", "type": "Claim", "label": "x"}],
                  "edges": [{"src_key": "a", "dst_key": "ghost",
                             "relation": "supports", "confidence": "INFERRED",
                             "score": 0.85, "span": "p:1"},
                            {"src_key": "a", "dst_key": "a",
                             "relation": "supports", "confidence": "INFERRED",
                             "score": 0.85, "span": "p:1"}]})
    assert {r.reason for r in v.rejects} == {"dangling endpoint", "self-loop"}


def test_missing_span_costs_a_rung():
    v = validate({"nodes": [{"key": "a", "type": "Claim", "label": "x"},
                            {"key": "b", "type": "Claim", "label": "y"}],
                  "edges": [{"src_key": "a", "dst_key": "b",
                             "relation": "supports", "confidence": "INFERRED",
                             "score": 0.85, "citation_state": "missing"}]})
    assert v.edges[0]["score"] == 0.55        # 0.85 -> 0.65 (missing) -> 0.55


# ── entity resolution ───────────────────────────────────────────────────────

def test_surface_forms_normalise_together():
    assert normalise("I²C") == normalise("i2c") == "i2c"
    assert similarity("I²C", "i2c") == 1.0


def test_aliases_force_a_match():
    assert similarity("TWI", "Inter-Integrated Circuit",
                      a_aliases=["I2C"], b_aliases=["I2C"]) == 1.0


def test_bands():
    assert band_for(0.99) == "merge"
    assert band_for(0.8) == "same_as"
    assert band_for(0.4) == "distinct"


def test_soft_band_creates_same_as_not_a_merge(s):
    """⭐ 0.70-0.95 keeps BOTH nodes. A wrong same_as edge is one deletion; a
    wrong merge is node surgery."""
    llm = FakeLLM(canned={"a.md": {
        "nodes": [{"key": "n1", "type": "Concept", "label": "bioimpedance"},
                  {"key": "n2", "type": "Concept", "label": "bio impedance"}],
        "edges": []}})
    rep = ingest(s, ingest_text("a.md", "x", llm))
    g = s.state()
    assert len(rep.same_as) == 1
    assert sum(1 for e in g.edges.values() if e.relation.value == "same_as") == 1
    assert len(g.nodes) == 2                        # both survive


# ── routing to the human ────────────────────────────────────────────────────

def test_ambiguous_always_goes_to_review(s):
    llm = FakeLLM(canned={"a.md": {
        "nodes": [{"key": "a", "type": "Claim", "label": "hydration link"},
                  {"key": "b", "type": "Claim", "label": "impedance drop"}],
        "edges": [{"src_key": "a", "dst_key": "b", "relation": "supports",
                   "confidence": "AMBIGUOUS", "score": 0.3,
                   "citation_state": "missing", "span": "a.md:1"}]}})
    rep = ingest(s, ingest_text("a.md", "x", llm))
    assert len(rep.review) == 1
    assert len(pending_review(s)) == 1


def test_contradictions_always_go_to_review(s):
    llm = FakeLLM(canned={"a.md": {
        "nodes": [{"key": "a", "type": "Claim", "label": "hydration link"},
                  {"key": "b", "type": "Claim", "label": "impedance drop"}],
        "edges": [{"src_key": "a", "dst_key": "b", "relation": "contradicts",
                   "confidence": "INFERRED", "score": 0.85,
                   "citation_state": "present_relevant", "span": "a.md:1"}]}})
    assert len(ingest(s, ingest_text("a.md", "x", llm)).review) == 1


def test_inferred_auto_accepts(s):
    """Everything the extractor is confident about lands in the graph,
    reversibly. The queue is a thinking prompt, not an integrity gate."""
    rep = ingest(s, ingest_text("notes.md", "impedance drops when hydrated\n",
                                FakeLLM()))
    assert rep.accepted_edges >= 1 and rep.review == []


def test_reviewed_items_can_be_accepted_in_bulk(s):
    llm = FakeLLM(canned={"a.md": {
        "nodes": [{"key": "a", "type": "Claim", "label": "hydration link"},
                  {"key": "b", "type": "Claim", "label": "impedance drop"}],
        "edges": [{"src_key": "a", "dst_key": "b", "relation": "contradicts",
                   "confidence": "INFERRED", "score": 0.85,
                   "citation_state": "present_relevant", "span": "a.md:1"}]}})
    ingest(s, ingest_text("a.md", "x", llm))
    ids = [e["id"] for e in pending_review(s)]
    assert decide(s, ids, accept=True) == 1
    assert pending_review(s) == []
    assert any(e.relation.value == "contradicts" for e in s.state().edges.values())


def test_rejecting_clears_the_queue_without_writing_the_edge(s):
    llm = FakeLLM(canned={"a.md": {
        "nodes": [{"key": "a", "type": "Claim", "label": "hydration link"},
                  {"key": "b", "type": "Claim", "label": "impedance drop"}],
        "edges": [{"src_key": "a", "dst_key": "b", "relation": "contradicts",
                   "confidence": "INFERRED", "score": 0.85,
                   "citation_state": "present_relevant", "span": "a.md:1"}]}})
    ingest(s, ingest_text("a.md", "x", llm))
    decide(s, [e["id"] for e in pending_review(s)], accept=False)
    assert pending_review(s) == []
    assert not any(e.relation.value == "contradicts"
                   for e in s.state().edges.values())


# ── hygiene ─────────────────────────────────────────────────────────────────

def test_the_same_file_twice_is_a_noop(s):
    f = ingest_text("notes.md", "impedance drops when hydrated\n", FakeLLM())
    ingest(s, f)
    before = len(s.state().nodes)
    rep2 = ingest(s, ingest_text("notes.md", "impedance drops when hydrated\n",
                                 FakeLLM()))
    assert rep2.duplicate and len(s.state().nodes) == before


def test_quarantine_keeps_the_bad_fragment(s):
    llm = FakeLLM(canned={"a.md": {
        "nodes": [{"key": "a", "type": "Sandwich", "label": "x"}],
        "edges": []}})
    rep = ingest(s, ingest_text("a.md", "x", llm))
    assert rep.quarantined[0]["reason"] == "unknown type"


def test_ingested_labels_never_reach_the_plaintext_half(s):
    ingest(s, ingest_text("notes.md", "impedance drops when hydrated\n",
                          FakeLLM()))
    for e in s.ledger.read():
        assert "impedance drops when hydrated" not in canonical(e.structural)


def test_ingestion_replays_deterministically(s):
    from mindgraph.projector import project, state_hash
    ingest(s, ingest_text("notes.md", "a\nb\nc\n", FakeLLM()))
    ingest(s, ingest_text("driver.py", "def f():\n    pass\n", FakeLLM()))
    assert state_hash(project(s.ledger.read())) == \
           state_hash(project(s.ledger.read()))
    assert s.ledger.verify_chain()


# ── ⚠️ calibration target, not a passing grade ──────────────────────────────

@pytest.mark.parametrize("a,b,score", [
    ("skin impedance", "skin impedence", 0.684),      # single-char typo
    ("PID control", "PID controller", 0.611),         # morphological variant
    ("skin impedance", "skin impedance measurement", 0.517),   # containment
    ("I2C bus", "I2C", 0.400),                        # short-label containment
])
def test_known_under_merges(a, b, score):
    """These are the SAME thing to a human, and trigram Jaccard scores them
    below the 0.70 soft band — so today they stay as separate nodes, which is
    the fragmentation the resolver exists to prevent.

    ⚠️ Backend/03 §5 says the threshold "is a starting guess and must be
    calibrated in week one". This test is that calibration's concrete target:
    it pins today's behaviour so a scoring change is visible rather than
    silent. Exact-match and alias paths already handle I²C/i2c/TWI, which is
    the highest-frequency case; these are the residue.
    """
    assert similarity(a, b) == pytest.approx(score, abs=0.01)
    assert band_for(similarity(a, b)) == "distinct"


def test_unrelated_labels_stay_far_apart():
    """The control: whatever we raise the threshold to, this must not merge."""
    assert similarity("skin impedance", "thermal noise") < 0.1
