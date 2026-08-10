"""Stable circuit simulation errors."""

from __future__ import annotations


class CircuitSimulationError(Exception):
    """Normalized failure that is safe to expose to callers."""

    def __init__(self, *, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class CircuitConfigurationError(CircuitSimulationError):
    """Invalid or unavailable provider configuration."""


class CircuitMaterializationError(CircuitSimulationError):
    """Provider workspace could not be materialized safely."""


class CircuitExecutionError(CircuitSimulationError):
    """Provider process could not be executed safely."""
