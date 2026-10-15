"""In-memory circuit simulation provider for tests and evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .translator import assess_support, materialize_workspace
from .types import (
    AvailabilityStatus,
    ExecutionRequest,
    ExecutionResult,
    FindingSeverity,
    MaterializationRequest,
    ProviderAvailability,
    ProviderWorkspace,
    SupportAssessment,
    ValidationResult,
)


@dataclass
class FakeCircuitSimulationProvider:
    availability_result: ProviderAvailability = field(
        default_factory=lambda: ProviderAvailability(
            AvailabilityStatus.READY, "fake", "Fake provider is ready"
        )
    )
    validation_result: ValidationResult | None = None
    execution_result: ExecutionResult = field(
        default_factory=lambda: ExecutionResult(
            succeeded=True,
            exit_code=0,
            timed_out=False,
        )
    )
    calls: list[tuple[str, object]] = field(default_factory=list)

    def availability(self) -> ProviderAvailability:
        self.calls.append(("availability", None))
        return self.availability_result

    def assess_support(self, request: MaterializationRequest) -> SupportAssessment:
        self.calls.append(("assess_support", request))
        return assess_support(request)

    def materialize(self, request: MaterializationRequest) -> ProviderWorkspace:
        self.calls.append(("materialize", request))
        return materialize_workspace(request)

    def validate(self, workspace: ProviderWorkspace) -> ValidationResult:
        self.calls.append(("validate", workspace))
        if self.validation_result is not None:
            return self.validation_result
        valid = not any(finding.severity is FindingSeverity.ERROR for finding in workspace.findings)
        return ValidationResult(valid=valid, findings=workspace.findings)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls.append(("execute", request))
        return self.execution_result
