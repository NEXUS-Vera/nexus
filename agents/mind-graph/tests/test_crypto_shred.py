"""Erasure vs immutability. Backend/02 §0, §7.

The property being proved: destroying a key removes the content and leaves the
STRUCTURE intact, so the projector never corrupts and aggregate outcome data
outlives an erasure request.
"""
from __future__ import annotations

import pytest
from conftest import accept, edge, node, validate
from mindgraph.crypto import KeyStore, decrypt, encrypt
from mindgraph.errors import KeyDestroyed
from mindgraph.events import EventType
from mindgraph.ledger import canonical
from mindgraph.projector import project, state_hash


def test_roundtrip():
    ks = KeyStore()
    ks.create("u1")
    blob = encrypt(ks, "u1", {"measured": "47.2 kOhm"})
    assert decrypt(ks, "u1", blob)["measured"] == "47.2 kOhm"


def test_destroying_the_key_makes_content_unreadable():
    ks = KeyStore()
    ks.create("u1")
    blob = encrypt(ks, "u1", {"measured": "47.2 kOhm"})
    ks.destroy("u1")
    with pytest.raises(KeyDestroyed):
        decrypt(ks, "u1", blob)


def test_structure_survives_shredding(led):
    """⭐ The shape stays; the labels go. state_hash excludes encrypted fields,
    so a shredded graph still passes its own determinism check."""
    accept(led, [node("M", "Artifact", label="forearm sweep"),
                 node("C", label="47 kOhm means hydrated")],
           [edge("M", "supports", "C")])
    validate(led, "M", ["C"])
    before = project(led.read())

    led.append("system", EventType.SHREDDED, {"user": "u1"})
    after = project(led.read())

    assert set(after.nodes) == set(before.nodes)
    assert all(n.label is None for n in after.nodes.values())
    assert state_hash(after) == state_hash(before)


def test_agreement_outlives_erasure(led):
    """The flywheel signal is structural, so calibration data survives while
    the person's numbers do not."""
    accept(led, [node("M", "Artifact", label="forearm sweep"), node("C")],
           [edge("M", "supports", "C")])
    validate(led, "M", ["C"])
    led.append("system", EventType.SHREDDED, {"user": "u1"})
    g = project(led.read())
    assert g.nodes["M"].labels_at["outcome"] == "matched"
    assert g.nodes["C"].corroboration == 1
    assert g.nodes["M"].label is None


def test_no_user_text_in_structural(led):
    """CI gate. Put a label or a measured value in `structural` "just for
    convenience" and erasure quietly stops working."""
    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    validate(led, "M", ["C"])
    for e in led.read():
        for tok in canonical(e.structural).split('"'):
            assert len(tok) <= 40, f"suspiciously long token in structural: {tok!r}"
