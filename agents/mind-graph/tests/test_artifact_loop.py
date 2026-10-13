"""The Artifact loop. Backend/10 Phase 2.

Gate: a real prediction → measurement leaves the graph at
`corroboration = 1, strength = TENTATIVE`.
"""
from __future__ import annotations

import pytest
from mindgraph.artifact import ArtifactError, Session, calibration, measure, predict, show
from mindgraph.cli import _claim
from mindgraph.crypto import KeyStore
from mindgraph.errors import KeyDestroyed
from mindgraph.events import EventType
from mindgraph.ledger import Ledger, canonical
from mindgraph.projector import project, state_hash
from mindgraph.schema import Strength, Support


@pytest.fixture
def s(tmp_path):
    sess = Session(user="u1", ledger=Ledger(tmp_path / "l.db"),
                   keys=KeyStore(tmp_path / "keys.json"))
    sess.keys.create("u1")
    yield sess
    sess.close()


def _cycle(s, low=45.0, high=50.0, value=47.2, claim="C1"):
    _claim(s, "47 kOhm means hydrated", cid=claim)
    aid = predict(s, label="forearm sweep", quantity="impedance", low=low,
                  high=high, unit="kOhm", supports=[claim])
    return aid, measure(s, aid, value=value)


# ── the gate ────────────────────────────────────────────────────────────────

def test_one_cycle_gives_corroboration_one_and_tentative(s):
    aid, r = _cycle(s)
    assert r["agreement"] == "matched"
    c = s.state().nodes["C1"]
    assert c.corroboration == 1
    assert c.support is Support.SUPPORTED
    assert c.strength is Strength.TENTATIVE      # one result is not knowledge


def test_two_cycles_establish(s):
    _cycle(s)
    aid2 = predict(s, label="second sweep", quantity="impedance", low=45,
                   high=50, unit="kOhm", supports=["C1"])
    measure(s, aid2, value=46.0)
    assert s.state().nodes["C1"].strength is Strength.ESTABLISHED


# ── the prediction is locked ────────────────────────────────────────────────

def test_prediction_cannot_be_edited(s):
    aid = predict(s, label="x", quantity="impedance", low=45, high=50,
                  unit="kOhm")
    with pytest.raises(ArtifactError, match="immutable"):
        predict(s, label="x", quantity="impedance", low=40, high=60,
                unit="kOhm", artifact_id=aid)


def test_cannot_measure_without_predicting(s):
    _claim(s, "c", cid="C1")
    s.ledger.append("u1", EventType.ACCEPTED,
                    {"nodes": [{"id": "A9", "type": "Artifact", "kind": "run"}]})
    with pytest.raises(ArtifactError, match="predict before you measure"):
        measure(s, "A9", value=1.0)


def test_cannot_measure_twice(s):
    aid, _ = _cycle(s)
    with pytest.raises(ArtifactError, match="already has a measurement"):
        measure(s, aid, value=99.0)


def test_inverted_range_is_rejected(s):
    with pytest.raises(ArtifactError, match="above high"):
        predict(s, label="x", quantity="q", low=50, high=45, unit="kOhm")


def test_unit_mismatch_is_rejected(s):
    aid = predict(s, label="x", quantity="impedance", low=45, high=50,
                  unit="kOhm")
    with pytest.raises(ArtifactError, match="unit mismatch"):
        measure(s, aid, value=47.0, unit="Ohm")


# ── the verdict is derived, never supplied ──────────────────────────────────

def test_outside_the_range_diverges(s):
    _, r = _cycle(s, value=61.0)
    assert r["agreement"] == "diverged"
    assert s.state().nodes["C1"].corroboration == 0     # only matches corroborate


def test_boundary_counts_as_matched(s):
    _, r = _cycle(s, low=45, high=50, value=50.0)
    assert r["agreement"] == "matched"


def test_no_value_is_inconclusive(s):
    aid = predict(s, label="x", quantity="q", low=1, high=2, unit="u")
    assert measure(s, aid, value=None)["agreement"] == "inconclusive"


# ── privacy: values encrypted, verdict structural ───────────────────────────

def test_values_never_appear_in_structural(s):
    _cycle(s)
    for e in s.ledger.read():
        blob = canonical(e.structural)
        assert "47.2" not in blob
        assert "forearm sweep" not in blob


def test_agreement_survives_erasure(s):
    """⭐ Calibration data outlives an erasure request; the numbers do not."""
    aid, _ = _cycle(s)
    state_hash(s.state())
    s.keys.destroy("u1")
    s.ledger.append("system", EventType.SHREDDED, {"user": "u1"})
    g = project(s.ledger.read())
    assert g.nodes[aid].labels_at["outcome"] == "matched"
    assert g.nodes["C1"].corroboration == 1
    assert g.nodes[aid].label is None
    with pytest.raises(KeyDestroyed):
        show(s, aid)


def test_calibration_is_computed_from_structure_only(s):
    _cycle(s)
    aid2 = predict(s, label="b", quantity="impedance", low=45, high=50,
                   unit="kOhm", supports=["C1"])
    measure(s, aid2, value=80.0)
    cal = calibration(s)
    assert cal == {"resolved": 2, "matched": 1, "diverged": 1,
                   "hit_rate": 0.5, "inconclusive": 0}


# ── it replays like everything else ─────────────────────────────────────────

def test_the_loop_replays_deterministically(s):
    _cycle(s)
    assert state_hash(project(s.ledger.read())) == \
           state_hash(project(s.ledger.read()))
    assert s.ledger.verify_chain()


def test_method_is_recorded_and_flags_single_method(s):
    s.ledger.append("u1", EventType.ACCEPTED,
                    {"nodes": [{"id": "MTH", "type": "Artifact",
                                "kind": "method", "label": "4-wire Kelvin"}]})
    _claim(s, "c", cid="C1")
    for lo, hi, v in ((45, 50, 47.0), (45, 50, 46.5)):
        aid = predict(s, label="run", quantity="impedance", low=lo, high=hi,
                      unit="kOhm", supports=["C1"], method="MTH")
        measure(s, aid, value=v)
    c = s.state().nodes["C1"]
    assert c.strength is Strength.ESTABLISHED
    assert c.single_method is True          # flagged, not blocked
