"""Runtime capability registry."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from nexus_board.errors import DuplicateRegistrationError, RegistryError

DEFAULT_RUNTIME_CAPABILITIES: list[dict[str, Any]] = [
    {
        "schemaVersion": "1.0.0",
        "capabilityId": "structured-validation",
        "displayName": "Structured Validation",
        "providerId": "fake",
        "available": True,
        "description": "Deterministic fake structured validation",
    },
    {
        "schemaVersion": "1.0.0",
        "capabilityId": "fake-execution",
        "displayName": "Fake Execution",
        "providerId": "fake",
        "available": True,
        "description": "Deterministic fake execution runtime",
    },
    {
        "schemaVersion": "1.0.0",
        "capabilityId": "file-workspace",
        "displayName": "Filesystem Workspace",
        "providerId": "local",
        "available": True,
        "description": "Persistent lease-guarded filesystem workspace storage",
    },
    {
        "schemaVersion": "1.0.0",
        "capabilityId": "sandbox-execution",
        "displayName": "Sandboxed Execution",
        "providerId": "local-sandbox",
        "available": True,
        "description": (
            "Nexus-owned generic sandboxed command execution against filesystem snapshots"
        ),
    },
]


class RuntimeCapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Any]] = {}

    def register(self, capability: dict[str, Any]) -> None:
        capability_id = capability.get("capabilityId")
        if not isinstance(capability_id, str) or not capability_id:
            raise RegistryError("Capability missing capabilityId.")
        if capability_id in self._capabilities:
            raise DuplicateRegistrationError(f"Capability already registered: {capability_id}")
        self._capabilities[capability_id] = deepcopy(capability)

    def get(self, capability_id: str) -> dict[str, Any]:
        capability = self._capabilities.get(capability_id)
        if capability is None:
            raise RegistryError(f"Unknown capability: {capability_id}")
        return deepcopy(capability)

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._capabilities.values()]

    def is_available(self, capability_id: str) -> bool:
        capability = self._capabilities.get(capability_id)
        return bool(capability and capability.get("available") is True)


def default_runtime_capability_registry() -> RuntimeCapabilityRegistry:
    registry = RuntimeCapabilityRegistry()
    for capability in DEFAULT_RUNTIME_CAPABILITIES:
        registry.register(capability)
    return registry
