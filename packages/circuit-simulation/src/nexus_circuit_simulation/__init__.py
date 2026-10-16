"""Shared circuit simulation package."""

from .capability import CircuitSimulationCapability, PreparedCircuitSimulation
from .errors import (
    CircuitConfigurationError,
    CircuitExecutionError,
    CircuitMaterializationError,
    CircuitSimulationError,
)
from .fake import FakeCircuitSimulationProvider
from .mappings import EXACT_MAPPING_REGISTRY, FIXED_PIN_PROFILE, find_mapping
from .protocol import CircuitSimulationProvider
from .runner import ProcessRunner, SafeSubprocessRunner
from .translator import assess_support, materialize_workspace
from .types import (
    ArtifactEntityReference,
    AvailabilityStatus,
    ComponentMapping,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionResult,
    Finding,
    FindingSeverity,
    MappingType,
    MaterializationRequest,
    PinMapping,
    ProviderAvailability,
    ProviderWorkspace,
    RunnerRequest,
    RunnerResult,
    SupportAssessment,
    SupportStatus,
    ValidationResult,
)
from .wokwi import WokwiProvider

__all__ = [
    "ArtifactEntityReference",
    "AvailabilityStatus",
    "CircuitConfigurationError",
    "CircuitExecutionError",
    "CircuitMaterializationError",
    "CircuitSimulationError",
    "CircuitSimulationCapability",
    "CircuitSimulationProvider",
    "ComponentMapping",
    "EXACT_MAPPING_REGISTRY",
    "ExecutionOutput",
    "ExecutionRequest",
    "ExecutionResult",
    "FIXED_PIN_PROFILE",
    "FakeCircuitSimulationProvider",
    "Finding",
    "FindingSeverity",
    "MappingType",
    "MaterializationRequest",
    "PinMapping",
    "PreparedCircuitSimulation",
    "ProcessRunner",
    "ProviderAvailability",
    "ProviderWorkspace",
    "RunnerRequest",
    "RunnerResult",
    "SafeSubprocessRunner",
    "SupportAssessment",
    "SupportStatus",
    "ValidationResult",
    "WokwiProvider",
    "assess_support",
    "find_mapping",
    "materialize_workspace",
]
