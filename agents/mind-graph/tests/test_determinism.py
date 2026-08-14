"""Replay must be byte-identical. Backend/02 §7.

This is the single most important property in the system: it is what makes the
database swappable, every failure repairable, and time free. Everything else is
downstream of it.
"""
from __future__ import annotations

import pytest

from conftest import accept, edge, node, validate
from mindgraph.errors import UnknownEventType
from mindgraph.events import Event, EventType
from mindgraph.projector import GraphState, project, state_hash


@pytest.fixture
def populated(led):
    accept(led, [node("M", "Artifact", kind="run"), node("C")],
           [edge("M", "supports", "C", confidence="EXTRACTED", score=1.0)])
    accept(led, [node("S", "Source", kind="paper")],
           [edge("S", "supports", "C")])
    validate(led, "M", ["C"])
    led.append("user", EventType.DEAD_END,
               {"id": "d1", "question": "400 kHz I2C?",
                "nodes": ["M"], "resurrect_if": ["shielding_added"]})
    return led


def test_replay_is_byte_identical(populated):
    assert state_hash(project(populated.read())) == \
           state_hash(project(populated.read()))


def test_replay_independent_of_batching(populated):
    """Streaming one event at a time must equal one big fold."""
    whole = project(populated.read())
    piecewise = GraphState()
    for e in populated.read():
        piecewise = project([e], piecewise)
    assert state_hash(whole) == state_hash(piecewise)


def test_applying_an_event_twice_is_a_noop(populated):
    """last_seq guards replay — re-delivery must not double-count anything."""
    once = project(populated.read())
    twice = project(list(populated.read()) + list(populated.read()))
    assert state_hash(once) == state_hash(twice)


def test_hash_chain_detects_tampering(populated):
    assert populated.verify_chain()
    populated.db.execute(
        "UPDATE events SET structural='{\"nodes\":[]}' WHERE seq=1")
    assert not populated.verify_chain()


def test_hash_chain_detects_deletion(populated):
    assert populated.verify_chain()
    populated.db.execute("DELETE FROM events WHERE seq=2")
    assert not populated.verify_chain()


def test_unknown_event_type_raises_rather_than_skipping(populated):
    """Silently skipping makes replay differ across versions — the one thing
    that must never happen."""
    e = next(iter(populated.read()))
    bogus = Event(seq=999, ts=e.ts, actor="x", type=EventType.OBSERVED,
                  structural={}, prev_hash=e.prev_hash, hash=e.hash)
    object.__setattr__(bogus, "type", "not_a_real_type")
    with pytest.raises(UnknownEventType):
        project([bogus])


def test_projector_does_not_touch_the_clock(populated, monkeypatch):
    """Purity check: a projector that reads the wall clock is not replayable."""
    import time
    def boom(*a, **k):
        raise AssertionError("the projector called the clock")
    monkeypatch.setattr(time, "time", boom)
    monkeypatch.setattr(time, "time_ns", boom)
    project(populated.read())


def test_projector_does_not_use_randomness(populated, monkeypatch):
    import random
    import uuid
    def boom(*a, **k):
        raise AssertionError("the projector used randomness")
    monkeypatch.setattr(random, "random", boom)
    monkeypatch.setattr(uuid, "uuid4", boom)
    project(populated.read())
