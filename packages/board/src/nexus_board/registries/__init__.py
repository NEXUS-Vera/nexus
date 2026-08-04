"""Registries for artifact types, capabilities, and providers."""

from __future__ import annotations

from nexus_board.registries.artifact_types import (
    ArtifactTypeRegistry,
    default_artifact_type_registry,
)
from nexus_board.registries.external_providers import (
    ExternalProviderRegistry,
    default_external_provider_registry,
)
from nexus_board.registries.runtime_capabilities import (
    RuntimeCapabilityRegistry,
    default_runtime_capability_registry,
)

__all__ = [
    "ArtifactTypeRegistry",
    "ExternalProviderRegistry",
    "RuntimeCapabilityRegistry",
    "default_artifact_type_registry",
    "default_external_provider_registry",
    "default_runtime_capability_registry",
]
