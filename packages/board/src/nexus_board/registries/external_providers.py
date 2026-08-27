"""External provider registry (fake only)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from nexus_board.errors import DuplicateRegistrationError, RegistryError

DEFAULT_EXTERNAL_PROVIDERS: list[dict[str, Any]] = [
    {
        "providerId": "fake",
        "displayName": "Fake Provider",
        "available": True,
        "capabilities": ["structured-validation", "fake-execution"],
    },
    {
        "providerId": "local",
        "displayName": "Local Filesystem",
        "available": True,
        "capabilities": ["file-workspace"],
    },
    {
        "providerId": "local-sandbox",
        "displayName": "Local Sandbox Runtime",
        "available": True,
        "capabilities": ["sandbox-execution"],
    },
]


class ExternalProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = {}

    def register(self, provider: dict[str, Any]) -> None:
        provider_id = provider.get("providerId")
        if not isinstance(provider_id, str) or not provider_id:
            raise RegistryError("Provider missing providerId.")
        if provider_id in self._providers:
            raise DuplicateRegistrationError(f"Provider already registered: {provider_id}")
        self._providers[provider_id] = deepcopy(provider)

    def get(self, provider_id: str) -> dict[str, Any]:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise RegistryError(f"Unknown provider: {provider_id}")
        return deepcopy(provider)

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._providers.values()]


def default_external_provider_registry() -> ExternalProviderRegistry:
    registry = ExternalProviderRegistry()
    for provider in DEFAULT_EXTERNAL_PROVIDERS:
        registry.register(provider)
    return registry
