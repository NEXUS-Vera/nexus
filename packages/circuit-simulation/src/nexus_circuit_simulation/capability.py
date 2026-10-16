"""Provider-independent orchestration for the circuit-simulation capability."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import CircuitMaterializationError
from .protocol import CircuitSimulationProvider
from .types import (
    ExecutionRequest,
    ExecutionResult,
    MaterializationRequest,
    ProviderAvailability,
    ProviderWorkspace,
    SupportAssessment,
    SupportStatus,
    ValidationResult,
)


@dataclass(frozen=True)
class PreparedCircuitSimulation:
    assessment: SupportAssessment
    workspace: ProviderWorkspace


class CircuitSimulationCapability:
    """Orchestrate any conforming provider without vendor-specific branches."""

    def __init__(self, provider: CircuitSimulationProvider) -> None:
        self._provider = provider

    def availability(self) -> ProviderAvailability:
        return self._provider.availability()

    def assess_support(self, request: MaterializationRequest) -> SupportAssessment:
        return self._provider.assess_support(request)

    def prepare(self, request: MaterializationRequest) -> PreparedCircuitSimulation:
        assessment = self.assess_support(request)
        if assessment.status in {
            SupportStatus.UNSUPPORTED,
            SupportStatus.PARTIALLY_SUPPORTED,
        }:
            raise CircuitMaterializationError(
                code="ARCHITECTURE_UNSUPPORTED",
                message="Circuit architecture cannot be represented by this provider",
            )
        return PreparedCircuitSimulation(
            assessment=assessment,
            workspace=self._provider.materialize(request),
        )

    def validate(self, prepared: PreparedCircuitSimulation) -> ValidationResult:
        return self._provider.validate(prepared.workspace)

    def execute(
        self,
        prepared: PreparedCircuitSimulation,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        if request.workspace is not prepared.workspace:
            raise CircuitMaterializationError(
                code="PROVIDER_WORKSPACE_MISMATCH",
                message="Execution must use the prepared provider workspace",
            )
        return self._provider.execute(request)
