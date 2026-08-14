"""The closed ontology. Backend/02 §2.

Nothing enters the graph that is not one of these types, related by one of these
relations, at one of these confidence scores. The validators here are the last
place a bad value can be stopped cheaply.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = 2


class NodeType(StrEnum):
    CONCEPT = "Concept"; QUESTION = "Question"; CLAIM = "Claim"
    ARTIFACT = "Artifact"; SOURCE = "Source"; NOTE = "Note"


class Relation(StrEnum):
    CONTAINS = "contains"; PART_OF = "part_of"
    SUPPORTS = "supports"; CONTRADICTS = "contradicts"
    REFUTES = "refutes"; CONFIRMS = "confirms"; EXTENDS = "extends"
    EVIDENCE_FOR = "evidence_for"; MEASURED_BY = "measured_by"
    CITES = "cites"; USES_METHOD_IN = "uses_method_in"
    REQUIRES = "requires"; RELATES_TO = "relates_to"; SAME_AS = "same_as"
    ANSWERS = "answers"; RAISES = "raises"
    SUPERSEDES = "supersedes"; DERIVED_FROM = "derived_from"


SUPPORTING = {Relation.SUPPORTS, Relation.EVIDENCE_FOR,
              Relation.CONFIRMS, Relation.MEASURED_BY}
OPPOSING = {Relation.CONTRADICTS, Relation.REFUTES}


class Confidence(StrEnum):
    EXTRACTED = "EXTRACTED"; INFERRED = "INFERRED"; AMBIGUOUS = "AMBIGUOUS"


class Rank(StrEnum):
    PREFERRED = "preferred"; NORMAL = "normal"; DEPRECATED = "deprecated"


class Support(StrEnum):
    """Distinct from Rank. A claim can be true but unsupported."""
    SUPPORTED = "supported"; UNSUPPORTED = "unsupported"
    CONTESTED = "contested"
    UNKNOWN = "unknown"


class Strength(StrEnum):
    TENTATIVE = "tentative"; ESTABLISHED = "established"; CONTESTED = "contested"


class CitationState(StrEnum):
    PRESENT_RELEVANT = "present_relevant"; PRESENT_WEAK = "present_weak"
    MISSING = "missing"; WRONG_SOURCE = "wrong_source"
    ANCHOR_UNAVAILABLE = "anchor_unavailable"


class Scope(StrEnum):
    GLOBAL = "global"; PROJECT = "project"


class Origin(StrEnum):
    CURATED = "curated"      # from the skeleton, or carries a CASE external_id
    EXTRACTED = "extracted"  # invented by the LLM from this student's material
    PROMOTED = "promoted"    # extracted, then seen in a 2nd project at >=0.95


MIN_CORROBORATION = 2   # one result cannot mint a belief

MERGE_HARD = 0.95       # one node
MERGE_SOFT = 0.70       # `same_as` edge, both nodes survive
PROMOTE_MIN = 0.95      # extracted -> global requires this AND a 2nd project

# The ONLY legal confidence scores. Continuous ranges collapse to bimodal in
# practice (>50% at 0.5, >40% at 0.85+ measured in production), so five defined
# rungs discriminate where a 0-1 range does not.
LEGAL_SCORES = frozenset({1.0, 0.95, 0.85, 0.75, 0.65, 0.55, 0.3, 0.2, 0.1})

# Evidence from outside your own reasoning. Used to derive Claim.kind.
EXTERNAL_TYPES = {NodeType.ARTIFACT, NodeType.SOURCE}


class Node(BaseModel):
    id: str
    type: NodeType
    kind: str | None = None      # Artifact/Source: INTRINSIC. Claim: DERIVED (Q5)
    label: str | None = None                            # ENCRYPTED at rest
    aliases: list[str] = Field(default_factory=list)    # ENCRYPTED at rest
    body_ref: str | None = None
    project_id: str | None = None
    labels_at: dict[str, str] = Field(default_factory=dict)
    external_ids: dict[str, str] = Field(default_factory=dict)
    scope: Scope = Scope.PROJECT      # Concept only; set by provenance (Q4)
    origin: Origin = Origin.EXTRACTED
    created_seq: int
    valid_from: str | None = None
    valid_to: str | None = None
    rank: Rank = Rank.NORMAL
    support: Support = Support.UNKNOWN
    corroboration: int = 0
    corroborating_methods: list[str] = Field(default_factory=list)   # Q12
    single_method: bool = False                                      # Q12, derived
    strength: Strength = Strength.TENTATIVE
    # Derived in _recompute_support, kept for RANKING only — never for classification.
    evidence_mass: float = 0.0
    contest_ratio: float = 0.0
    superseded_by: str | None = None
    quarantined: bool = False

    @model_validator(mode="after")
    def _check(self):
        # Backend/09 Q4: Concept scope follows PROVENANCE, not a setting.
        if self.type is NodeType.CONCEPT:
            if self.origin is Origin.CURATED and self.scope is not Scope.GLOBAL:
                raise ValueError("curated concepts are global by construction")
            if self.scope is Scope.GLOBAL and self.project_id is not None:
                raise ValueError("global scope requires project_id = None")
            if self.scope is Scope.PROJECT and self.project_id is None:
                raise ValueError("project scope requires a project_id")
        elif self.scope is Scope.GLOBAL:
            raise ValueError("only Concept may be globally scoped")
        return self


class Edge(BaseModel):
    id: str
    src: str
    dst: str
    relation: Relation
    confidence: Confidence
    score: float
    weight: int = 1
    weight_sources: list[int] = Field(default_factory=list)       # event seqs
    # The NODES that asserted this link. Distinct from weight_sources, which are
    # event seqs — independence is a property of who said it, not of when.
    weight_source_nodes: list[str] = Field(default_factory=list)
    justification: list[str] = Field(default_factory=list)        # ATMS
    provenance: dict = Field(default_factory=dict)
    created_seq: int
    valid_from: str | None = None
    valid_to: str | None = None
    rank: Rank = Rank.NORMAL
    superseded_by: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.score not in LEGAL_SCORES:
            raise ValueError(f"score {self.score} not in the discrete rubric")
        if self.confidence is Confidence.EXTRACTED:
            if self.score != 1.0:
                raise ValueError("EXTRACTED edges are always 1.0")
            # Certainty requires a directly-supporting passage.
            if self.provenance.get("citation_state") not in (
                    None, CitationState.PRESENT_RELEVANT,
                    CitationState.PRESENT_RELEVANT.value):
                raise ValueError(
                    "EXTRACTED requires citation_state=present_relevant")
        if self.confidence is Confidence.AMBIGUOUS and self.score > 0.3:
            raise ValueError("AMBIGUOUS edges score 0.1-0.3")
        if self.weight < 1:
            raise ValueError("weight is a count, minimum 1")
        return self


class Hyperedge(BaseModel):
    """'These five measurements JOINTLY support this' is one relationship.

    Not five edges: pull one member and the joint justification fails, which is
    the whole point and is why this cannot be retrofitted later.
    """
    id: str
    relation: str
    members: list[str]
    target: str | None = None
    confidence: Confidence
    score: float
    weight: int = 1
    justification: list[str] = Field(default_factory=list)
    created_seq: int
    rank: Rank = Rank.NORMAL

    @model_validator(mode="after")
    def _check(self):
        if self.relation not in ("jointly_support", "jointly_contradict",
                                 "participate_in"):
            raise ValueError(f"unknown hyperedge relation {self.relation}")
        if self.score not in LEGAL_SCORES:
            raise ValueError(f"score {self.score} not in the discrete rubric")
        if len(set(self.members)) < 3:
            raise ValueError("hyperedge needs 3+ distinct members")
        return self
