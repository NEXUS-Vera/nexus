"""Support, strength, and the two independence rules. Backend/02 §7.

The three axes that revision 2's first draft conflated, and must never be
re-conflated:

  existence     `support`         is there ANY live support / contradiction?
  independence  `corroboration`   how many distinct RESULTS back this?
  mass          `evidence_mass`   how many sources assert the link, damped
"""

from __future__ import annotations

from conftest import accept, edge, edge_id, node, validate
from mindgraph.events import EventType
from mindgraph.projector import independent_weight, project
from mindgraph.schema import Strength, Support


def test_one_result_is_tentative_not_established(led):
    """One lucky measurement must not mark something learned."""
    accept(led, [node("M", "Artifact"), node("C")], [edge("M", "supports", "C")])
    validate(led, "M", ["C"])
    c = project(led.read()).nodes["C"]
    assert c.support is Support.SUPPORTED
    assert c.strength is Strength.TENTATIVE  # NOT in the knowledge state


def test_two_distinct_results_establish(led):
    accept(
        led,
        [node("M1", "Artifact"), node("M2", "Artifact"), node("C")],
        [edge("M1", "supports", "C"), edge("M2", "supports", "C")],
    )
    validate(led, "M1", ["C"])
    validate(led, "M2", ["C"])
    assert project(led.read()).nodes["C"].strength is Strength.ESTABLISHED


def test_claim_kind_is_derived_not_stored(led):
    """A hypothesis becomes an observation the moment it is measured."""
    accept(led, [node("C")])
    assert project(led.read()).nodes["C"].kind == "hypothesis"

    accept(led, [node("M", "Artifact")], [edge("M", "supports", "C")])
    assert project(led.read()).nodes["C"].kind == "observation"

    accept(led, [node("C2"), node("C3")], [edge("C3", "supports", "C2")])
    assert project(led.read()).nodes["C2"].kind == "conclusion"


def test_hypothesis_can_never_be_established(led):
    accept(led, [node("C")])
    c = project(led.read()).nodes["C"]
    assert c.kind == "hypothesis"
    assert c.strength is Strength.TENTATIVE


def test_citing_sources_are_discounted(led):
    """ONE link, asserted by three papers, two of which cite the first.

    `weight` counts the distinct sources that asserted the same (src, rel, dst)
    link — so this is one edge with weight 3, not three edges.

    ⚠️ Direction matters, and the spec had it backwards. The CITER is the
    derivative one; the cited original is the independent evidence. Inverting
    it discounts the original and keeps the copies — precisely the failure the
    discount exists to prevent.
    """
    accept(
        led,
        [
            node("Z", "Concept"),
            node("C"),
            node("p1", "Source"),
            node("p2", "Source"),
            node("p3", "Source"),
        ],
        [edge("p2", "cites", "p1"), edge("p3", "cites", "p1")],
    )
    # the same claim, asserted three times, by three different papers
    for src in ("p1", "p2", "p3"):
        accept(led, [], [edge("Z", "supports", "C", eid="e_sup", weight_source_nodes=[src])])
    g = project(led.read())
    e = g.edges[edge_id(g, "Z", "supports", "C")]
    assert e.weight == 3
    assert sorted(e.weight_source_nodes) == ["p1", "p2", "p3"]
    assert independent_weight(g, e) == 1  # p2 and p3 are p1 repeated


def test_uncited_sources_stay_independent(led):
    """The control for the test above: three papers with no citation links
    between them are three independent assertions."""
    accept(
        led,
        [
            node("Z", "Concept"),
            node("C"),
            node("q1", "Source"),
            node("q2", "Source"),
            node("q3", "Source"),
        ],
    )
    for src in ("q1", "q2", "q3"):
        accept(led, [], [edge("Z", "supports", "C", eid="e_ind", weight_source_nodes=[src])])
    g = project(led.read())
    assert independent_weight(g, g.edges[edge_id(g, "Z", "supports", "C")]) == 3


def test_conflicting_evidence_is_contested(led):
    accept(
        led,
        [node("M", "Artifact"), node("S", "Source"), node("C")],
        [edge("M", "supports", "C"), edge("S", "contradicts", "C")],
    )
    n = project(led.read()).nodes["C"]
    assert n.support is Support.CONTESTED
    assert n.strength is Strength.CONTESTED  # feeds the Disagreement Engine


def test_heavy_citation_does_not_suppress_a_contradiction(led):
    """20 papers agree; the student's bench disagrees once. Still CONTESTED."""
    nodes = [node(f"S{i}", "Source") for i in range(20)] + [node("C"), node("M", "Artifact")]
    accept(led, nodes, [edge(f"S{i}", "supports", "C") for i in range(20)])
    accept(led, [], [edge("M", "contradicts", "C")])
    n = project(led.read()).nodes["C"]
    assert n.support is Support.CONTESTED  # existence, not magnitude
    assert n.contest_ratio < 0.3  # graded for ranking only


def test_same_method_twice_is_flagged_not_blocked(led):
    """Two runs, one method: still ESTABLISHED, but visibly single-method."""
    accept(
        led,
        [
            node("M1", "Artifact", kind="method"),
            node("R1", "Artifact", kind="run"),
            node("R2", "Artifact", kind="run"),
            node("C"),
        ],
        [
            edge("R1", "uses_method_in", "M1"),
            edge("R2", "uses_method_in", "M1"),
            edge("R1", "supports", "C"),
            edge("R2", "supports", "C"),
        ],
    )
    validate(led, "R1", ["C"])
    validate(led, "R2", ["C"])
    c = project(led.read()).nodes["C"]
    assert c.corroboration == 2
    assert c.strength is Strength.ESTABLISHED  # not blocked
    assert c.single_method is True  # but flagged


def test_two_methods_clears_the_flag(led):
    accept(
        led,
        [
            node("M1", "Artifact", kind="method"),
            node("M2", "Artifact", kind="method"),
            node("R1", "Artifact"),
            node("R2", "Artifact"),
            node("C"),
        ],
        [
            edge("R1", "uses_method_in", "M1"),
            edge("R2", "uses_method_in", "M2"),
            edge("R1", "supports", "C"),
            edge("R2", "supports", "C"),
        ],
    )
    validate(led, "R1", ["C"])
    validate(led, "R2", ["C"])
    assert project(led.read()).nodes["C"].single_method is False


def test_methods_survive_a_merge(led):
    """A merge must not manufacture single-method-ness, nor hide it."""
    accept(
        led,
        [
            node("M1", "Artifact", kind="method"),
            node("M2", "Artifact", kind="method"),
            node("R1", "Artifact"),
            node("R2", "Artifact"),
            node("A"),
            node("B"),
        ],
        [
            edge("R1", "uses_method_in", "M1"),
            edge("R2", "uses_method_in", "M2"),
            edge("R1", "supports", "A"),
            edge("R2", "supports", "B"),
        ],
    )
    validate(led, "R1", ["A"])
    validate(led, "R2", ["B"])
    led.append("user", EventType.MERGED, {"kept": "A", "absorbed": "B"})
    g = project(led.read())
    assert g.nodes["A"].corroborating_methods == ["M1", "M2"]
    assert g.nodes["A"].single_method is False


def test_weight_never_substitutes_for_corroboration(led):
    """One measurement, cited by ten sources, is still TENTATIVE."""
    accept(
        led,
        [node("M", "Artifact"), node("C")] + [node(f"S{i}", "Source") for i in range(10)],
        [edge("M", "supports", "C")],
    )
    validate(led, "M", ["C"])
    for i in range(10):
        accept(led, [], [edge(f"S{i}", "supports", "C")])
    n = project(led.read()).nodes["C"]
    assert n.corroboration == 1
    assert n.strength is Strength.TENTATIVE  # not admitted to knowledge state
