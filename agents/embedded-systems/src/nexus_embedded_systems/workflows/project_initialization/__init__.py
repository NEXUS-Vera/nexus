"""Embedded project initialization workflow package."""

from .fixture_router import FixtureRouteDecision, FixtureRouteOutcome, route_fixture_family
from .repository import InMemoryInitializationStore
from .service import (
    InitializationProviderError,
    InitializationRoutingError,
    InitializationService,
    InitializationValidationError,
    supported_family_examples,
)

__all__ = [
    "FixtureRouteDecision",
    "FixtureRouteOutcome",
    "InMemoryInitializationStore",
    "InitializationProviderError",
    "InitializationRoutingError",
    "InitializationService",
    "InitializationValidationError",
    "route_fixture_family",
    "supported_family_examples",
]
