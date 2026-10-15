"""Provider-neutral circuit simulation boundary."""

from __future__ import annotations

from typing import Protocol

from .types import (
    ExecutionRequest,
    ExecutionResult,
    MaterializationRequest,
    ProviderAvailability,
    ProviderWorkspace,
    SupportAssessment,
    ValidationResult,
)


class CircuitSimulationProvider(Protocol):
    def availability(self) -> ProviderAvailability:
        """Report provider health without exposing credentials."""
        ...

    def assess_support(self, request: MaterializationRequest) -> SupportAssessment:
        """Assess exact selected components without fuzzy matching."""
        ...

    def materialize(self, request: MaterializationRequest) -> ProviderWorkspace:
        """Create a deterministic, in-memory provider workspace."""
        ...

    def validate(self, workspace: ProviderWorkspace) -> ValidationResult:
        """Validate a materialized workspace."""
        ...

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a validated workspace under bounded runtime policy."""
        ...
