"""Embedded project initialization workflow service."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from .fixture_router import SUPPORTED_FAMILIES
from .providers.base import InitializationProvider, InitializationRequestContext
from .providers.factory import build_initialization_provider
from .providers.fixture_provider import (
    FIXTURES_ROOT,
    FixtureInitializationProvider,
    FixtureRoutingError,
    FixtureValidationError,
)
from .providers.llm_provider import LlmInitializationError

AutonomyMode = Literal["collaborate", "delegate"]

logger = logging.getLogger("nexus.embedded.project_initialization")


class InitializationStore(Protocol):
    def save_initialization_package(self, package: dict[str, Any]) -> None: ...

    def save_workflow_run(self, workflow_run: dict[str, Any]) -> None: ...


class InitializationRoutingError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        matched_families: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.matched_families = matched_families


class InitializationValidationError(Exception):
    def __init__(
        self,
        *,
        codes: list[str],
        message: str,
        workflow_run: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.codes = codes
        self.message = message
        self.workflow_run = workflow_run


class InitializationProviderError(Exception):
    """LLM/provider path failures with stable error codes."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        workflow_run: dict[str, Any] | None = None,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.workflow_run = workflow_run
        self.details = details or []


@dataclass
class _LegacyStoreAdapter:
    """Adapts the historical InMemoryInitializationStore to the package store API."""

    inner: Any

    def save_initialization_package(self, package: dict[str, Any]) -> None:
        self.inner.save_project(package["project"])
        self.inner.save_turn(package["userTurn"])
        self.inner.save_workflow_run(package["workflowRun"])
        self.inner.save_artifacts(package["artifacts"])
        self.inner.save_package(package["project"]["projectId"], package)

    def save_workflow_run(self, workflow_run: dict[str, Any]) -> None:
        self.inner.save_workflow_run(workflow_run)


@dataclass
class InitializationService:
    store: Any
    provider: InitializationProvider = field(
        default_factory=lambda: build_initialization_provider("fixture")
    )
    fixtures_root: Path = FIXTURES_ROOT

    def __post_init__(self) -> None:
        if hasattr(self.store, "save_initialization_package"):
            self._store: InitializationStore = self.store
        else:
            self._store = _LegacyStoreAdapter(self.store)

    async def initialize_embedded_project(
        self,
        message: str,
        autonomy_mode: AutonomyMode = "collaborate",
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        logger.info(
            "initialization_requested",
            extra={"request_id": request_id, "autonomy_mode": autonomy_mode},
        )
        context = InitializationRequestContext(request_id=request_id)

        if isinstance(self.provider, FixtureInitializationProvider):
            self.provider.fixtures_root = self.fixtures_root

        try:
            result = await self.provider.initialize(message, autonomy_mode, context)
        except FixtureRoutingError as exc:
            raise InitializationRoutingError(
                code=exc.code,
                message=exc.message,
                matched_families=exc.matched_families,
            ) from exc
        except FixtureValidationError as exc:
            if exc.workflow_run:
                self._store.save_workflow_run(exc.workflow_run)
            raise InitializationValidationError(
                codes=exc.codes,
                message=exc.message,
                workflow_run=exc.workflow_run,
            ) from exc
        except LlmInitializationError as exc:
            if exc.workflow_run:
                self._store.save_workflow_run(exc.workflow_run)
            raise InitializationProviderError(
                code=exc.code,
                message=exc.message,
                workflow_run=exc.workflow_run,
                details=exc.details,
            ) from exc

        self._store.save_initialization_package(result)

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "initialization_completed",
            extra={
                "request_id": request_id,
                "workflow_run_id": result["workflowRun"]["workflowRunId"],
                "duration_ms": duration_ms,
            },
        )
        return result


def supported_family_examples() -> list[dict[str, str]]:
    examples = {
        "indoor-environmental-rover": (
            "I want to build a small indoor rover that drives around a room and maps "
            "temperature, humidity, and air quality."
        ),
        "wearable-tremor-monitor": (
            "I want to build a wrist-worn device that measures hand tremors "
            "and records the motion data for later analysis."
        ),
        "greenhouse-sensing-node": (
            "I want to build a greenhouse monitoring node that measures temperature, "
            "humidity, soil moisture, and light, and reports the readings remotely."
        ),
        "vibration-monitoring-device": (
            "I want to build a device that attaches to a machine and records vibration "
            "so I can detect changes in how the machine is operating."
        ),
        "robot-obstacle-detection-module": (
            "I want to build an obstacle-detection module for a small indoor robot "
            "so it can detect objects in front of it and react before it hits them."
        ),
        "esp32-imu-circuit-simulation": (
            "I want a golden Nexus circuit simulation project with an ESP32-class MCU "
            "and an IMU motion sensor for Wokwi surrogate simulation."
        ),
    }
    return [
        {"family": family, "examplePrompt": examples[family]}
        for family in SUPPORTED_FAMILIES
        if family in examples
    ]
