"""The companion — the supervisor moves a chatbot cannot make.

⭐ Every function here is graph or arithmetic over the student's OWN outcomes.
That is the point: a competitor with a better model still does not have the
record these read from.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mindgraph.artifact import Session, measure, predict, show
from mindgraph.companion import bias, impact, recall_failures, transfer


@pytest.fixture
def sess():
    with tempfile.TemporaryDirectory() as t:
        s = Session.open("c", Path(t))
        yield s
        s.close()


# ── impact ──────────────────────────────────────────────────────────────────

def test_impact_previews_what_loses_its_footing(sess):
    """⭐ Before retracting, not after. A student who sees that withdrawing one
    sweep un-supports four claims will think; one who finds out afterwards
    learns to distrust the tool."""
    from conftest import edge
    from mindgraph.crypto import encrypt
    from mindgraph.events import EventType
    sess.ledger.append("c", EventType.ACCEPTED, {
        "nodes": [{"id": "R1", "type": "Artifact", "kind": "run"},
                  {"id": "C1", "type": "Claim"},
                  {"id": "C2", "type": "Claim"}],
        "edges": [dict(edge("R1", "supports", "C1")),
                  dict(edge("C1", "supports", "C2"))]},
        content=encrypt(sess.keys, "c", {"labels": {"R1": "sweep", "C1": "a", "C2": "b"}}))
    im = impact(sess.state(), "R1")
    assert "C1" in im.direct
    # ⚠️ the cascade is the part a student cannot compute in their head
    assert "C2" in im.unsupported_after
    assert im.load_bearing


def test_impact_of_an_unknown_node_is_empty_not_an_error(sess):
    assert impact(sess.state(), "nope").direct == []


# ── recall ──────────────────────────────────────────────────────────────────

def _dead_end(sess, did, question, resurrect=()):
    from mindgraph.events import EventType
    sess.ledger.append("c", EventType.DEAD_END,
                       {"id": did, "question": question, "nodes": [],
                        "resurrect_if": list(resurrect)})


def test_recall_finds_the_shape_of_a_past_failure(sess):
    """⭐ The immune-memory move: not "you tried X", but "this looks like the
    class of problem that bit you before"."""
    _dead_end(sess, "D1", "pull-up resistor caused bus errors under motor load",
              ["shielding_added"])
    hits = recall_failures(sess.state(), "bus errors when the motor spins up", {})
    assert hits and hits[0].id == "D1"
    assert "bus errors" in hits[0].reason


def test_recall_is_silent_on_an_unrelated_question(sess):
    """⚠️ A recall that fires on everything is a recall nobody reads."""
    _dead_end(sess, "D1", "pull-up resistor caused bus errors")
    assert recall_failures(sess.state(), "protein binding assay kinetics", {}) == []


# ── bias — the seventh vector ───────────────────────────────────────────────

def _art(q, lo, hi, val):
    return {"predicted": {"low": lo, "high": hi, "unit": "u", "quantity": q},
            "measured": {"value": val, "unit": "u"}, "kind": "run"}


def test_bias_names_the_direction_not_just_the_miss():
    """⭐ A student is rarely wrong at random — they are wrong in a DIRECTION,
    and usually a different one per quantity."""
    arts = [_art("timing", 100, 200, 400), _art("timing", 100, 200, 350),
            _art("timing", 100, 200, 500)]
    b = bias(arts)
    assert len(b) == 1 and b[0].quantity == "timing"
    assert b[0].direction == "optimistic"
    assert "widening upward" in b[0].advice


def test_bias_refuses_to_call_a_coincidence_a_pattern():
    """⚠️ Two misses in one direction is a coin landing heads twice. Calling
    that "systematically optimistic" teaches the student to ignore us."""
    assert bias([_art("timing", 1, 2, 9), _art("timing", 1, 2, 8)]) == []


def test_bias_reports_calibrated_when_it_is(sess):
    arts = [_art("impedance", 45, 50, 47), _art("impedance", 45, 50, 46),
            _art("impedance", 30, 40, 33)]
    assert bias(arts)[0].direction == "calibrated"


def test_bias_normalises_by_interval_width():
    """⚠️ A 2-unit miss on a 5-unit interval is not the same error as a 2-unit
    miss on a 500-unit one, and averaging them raw would say nothing."""
    wide = bias([_art("w", 0, 1000, 1100)] * 3)
    narrow = bias([_art("n", 0, 1, 101)] * 3)
    assert abs(narrow[0].median_error) > abs(wide[0].median_error)


def test_bias_pays_out_where_it_can_change_something(sess):
    """The whole loop, end to end: predict → measure → the system knows how you
    are habitually wrong."""
    for lo, hi, v in ((100, 200, 380), (100, 200, 420), (150, 250, 500)):
        aid = predict(sess, label="isr", quantity="timing", low=lo, high=hi, unit="us")
        measure(sess, aid, value=v)
    arts = [show(sess, nid) for nid, n in sess.state().nodes.items()
            if str(n.type).split(".")[-1] == "Artifact"]
    b = bias([a for a in arts if a.get("predicted")])
    assert b and b[0].direction == "optimistic"
