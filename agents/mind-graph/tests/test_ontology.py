"""The closed ontology refuses bad values. Backend/02 §7."""

from __future__ import annotations

import pytest
from mindgraph.schema import (
    CitationState,
    Confidence,
    Edge,
    Hyperedge,
    Node,
    NodeType,
    Origin,
    Scope,
)
from pydantic import ValidationError


def _edge(**kw):
    base = dict(
        id="e1",
        src="a",
        dst="b",
        relation="supports",
        confidence=Confidence.INFERRED,
        score=0.85,
        created_seq=1,
    )
    return Edge(**{**base, **kw})


@pytest.mark.parametrize("bad", [0.5, 0.9, 0.42, 0.0, 0.99])
def test_scores_outside_the_rubric_are_rejected(bad):
    """A continuous scale looks precise and carries less information."""
    with pytest.raises(ValidationError):
        _edge(score=bad)


def test_extracted_requires_a_supporting_passage():
    """Closes the likeliest route to a confident, well-cited, wrong edge."""
    with pytest.raises(ValidationError):
        _edge(
            confidence=Confidence.EXTRACTED,
            score=1.0,
            provenance={"citation_state": CitationState.PRESENT_WEAK},
        )


def test_extracted_with_a_relevant_passage_is_fine():
    e = _edge(
        confidence=Confidence.EXTRACTED,
        score=1.0,
        provenance={"citation_state": CitationState.PRESENT_RELEVANT},
    )
    assert e.score == 1.0


def test_extracted_must_be_certain():
    with pytest.raises(ValidationError):
        _edge(confidence=Confidence.EXTRACTED, score=0.95)


def test_ambiguous_cannot_be_confident():
    with pytest.raises(ValidationError):
        _edge(confidence=Confidence.AMBIGUOUS, score=0.85)


def test_weight_is_a_count():
    with pytest.raises(ValidationError):
        _edge(weight=0)


def test_curated_concepts_must_be_global():
    with pytest.raises(ValidationError):
        Node(
            id="n",
            type=NodeType.CONCEPT,
            origin=Origin.CURATED,
            scope=Scope.PROJECT,
            project_id="p1",
            created_seq=1,
        )


def test_extracted_concepts_start_project_scoped():
    n = Node(
        id="n",
        type=NodeType.CONCEPT,
        origin=Origin.EXTRACTED,
        scope=Scope.PROJECT,
        project_id="p1",
        created_seq=1,
    )
    assert n.scope is Scope.PROJECT


def test_global_concepts_have_no_project():
    with pytest.raises(ValidationError):
        Node(
            id="n",
            type=NodeType.CONCEPT,
            origin=Origin.CURATED,
            scope=Scope.GLOBAL,
            project_id="p1",
            created_seq=1,
        )


def test_only_concepts_may_be_global():
    with pytest.raises(ValidationError):
        Node(id="n", type=NodeType.CLAIM, scope=Scope.GLOBAL, created_seq=1)


def test_hyperedge_needs_three_members():
    """Two members is an edge. The joint semantics only mean something at 3+."""
    with pytest.raises(ValidationError):
        Hyperedge(
            id="h1",
            relation="jointly_support",
            members=["a", "b"],
            target="c",
            confidence=Confidence.INFERRED,
            score=0.85,
            created_seq=1,
        )


def test_hyperedge_relation_is_closed():
    with pytest.raises(ValidationError):
        Hyperedge(
            id="h1",
            relation="vaguely_related",
            members=["a", "b", "c"],
            target="d",
            confidence=Confidence.INFERRED,
            score=0.85,
            created_seq=1,
        )
