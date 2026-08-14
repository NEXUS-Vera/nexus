"""Mind Graph — Phase 0.

The ledger, the projector, the retraction cascade, and the tests that prove the
whole thing is trustworthy. Nothing else.

Everything downstream — retrieval, frontier, agents, UI — is a pure function of
a correct GraphState. If replay isn't deterministic and retraction doesn't
cascade, none of it can be trusted, and every bug above will be misdiagnosed as
a bug in the layer you happen to be looking at.
"""
from .cascade import cascade_retract
from .events import Event, EventType
from .ledger import Ledger, canonical, event_hash
from .projector import GraphState, project, state_hash
from .schema import (SCHEMA_VERSION, Confidence, Edge, Hyperedge, Node,
                     NodeType, Origin, Rank, Relation, Scope, Strength, Support)

__all__ = [
    "Ledger", "canonical", "event_hash", "Event", "EventType",
    "GraphState", "project", "state_hash", "cascade_retract",
    "Node", "Edge", "Hyperedge", "NodeType", "Relation", "Confidence",
    "Rank", "Support", "Strength", "Scope", "Origin", "SCHEMA_VERSION",
]
