"""Retraction cascades. Backend/02 §7.

⭐ The distinction these tests exist to protect: conclusions lose SUPPORT, not
TRUTH. A conclusion whose evidence vanished may still be true — it is simply no
longer earned. Collapsing that would silently deprecate conclusions that still
hold, and a student would rightly stop trusting the system.
"""

from __future__ import annotations

from conftest import accept, edge, node
from mindgraph.cascade import cascade_retract
from mindgraph.projector import project
from mindgraph.schema import Rank, Support


def test_retracting_evidence_unsupports_the_conclusion(led):
    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    g = project(led.read())
    cascade_retract(g, "M", seq=10)
    assert g.nodes["M"].rank is Rank.DEPRECATED
    assert g.nodes["C"].support is Support.UNSUPPORTED
    assert g.nodes["C"].rank is not Rank.DEPRECATED  # still not false


def test_claim_with_surviving_support_stays_supported(led):
    """Retracting one of two supports must not unsupport the claim."""
    accept(
        led,
        [node("M1", "Artifact"), node("M2", "Artifact"), node("C")],
        [edge("M1", "supports", "C"), edge("M2", "supports", "C")],
    )
    g = project(led.read())
    cascade_retract(g, "M1", seq=10)
    assert g.nodes["C"].support is Support.SUPPORTED


def test_cascade_is_transitive(led):
    """M -> C1 -> C2 -> C3. Retracting M must reach all three."""
    accept(
        led,
        [node("M", "Artifact"), node("C1"), node("C2"), node("C3")],
        [
            edge("M", "supports", "C1", eid="e1"),
            edge("C1", "supports", "C2", eid="e2", justification=["e1"]),
            edge("C2", "supports", "C3", eid="e3", justification=["e2"]),
        ],
    )
    g = project(led.read())
    out = cascade_retract(g, "M", seq=10)
    assert {"C1", "C2", "C3"} <= set(out["recomputed"])
    assert g.nodes["C3"].support is Support.UNSUPPORTED


def test_cascade_terminates_on_cyclic_justification(led):
    """A supports B supports A. Naive recursion hangs here; BFS with a seen
    set does not. Students write these."""
    accept(
        led,
        [node("A"), node("B")],
        [
            edge("A", "supports", "B", eid="eab", justification=["eba"]),
            edge("B", "supports", "A", eid="eba", justification=["eab"]),
        ],
    )
    g = project(led.read())
    cascade_retract(g, "A", seq=10)  # must not hang


def test_retraction_is_recorded_as_an_event(led):
    """The cascade runs through the projector, so it replays like anything else."""
    from mindgraph.events import EventType

    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    led.append("user", EventType.RETRACTED, {"target": "M"})
    g = project(led.read())
    assert g.nodes["M"].rank is Rank.DEPRECATED
    assert g.nodes["C"].support is Support.UNSUPPORTED


def test_retraction_replays_deterministically(led):
    from mindgraph.events import EventType
    from mindgraph.projector import state_hash

    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    led.append("user", EventType.RETRACTED, {"target": "M"})
    assert state_hash(project(led.read())) == state_hash(project(led.read()))
