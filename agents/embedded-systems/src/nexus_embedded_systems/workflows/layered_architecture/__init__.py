"""Layered Architecture composition (Phase 13A)."""

from .compose_electrical import (
    compose_electrical_architecture_content,
    compose_electrical_architecture_envelope,
)
from .compose_physical import (
    compose_physical_architecture_content,
    compose_physical_architecture_envelope,
)
from .deletion_impact import (
    apply_functional_node_removal,
    inspect_functional_node_deletion_impact,
)
from .ensure import ensure_layered_architecture_artifacts
from .normalize_specs import normalize_candidate_specifications
from .semantic_ops import apply_electrical_semantic_op, apply_physical_semantic_op

__all__ = [
    "apply_electrical_semantic_op",
    "apply_functional_node_removal",
    "apply_physical_semantic_op",
    "compose_electrical_architecture_content",
    "compose_electrical_architecture_envelope",
    "compose_physical_architecture_content",
    "compose_physical_architecture_envelope",
    "ensure_layered_architecture_artifacts",
    "inspect_functional_node_deletion_impact",
    "normalize_candidate_specifications",
]
