"""Observability helpers for model and workflow telemetry."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class GenerationObservation:
    request_id: str | None
    workflow_run_id: str | None
    stage: str
    provider: str | None
    model: str | None
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    retry_count: int | None
    repair_count: int | None
    validation_result: str
    error_code: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    # Never store raw prompts/API keys here.
    metadata: dict[str, Any] = field(default_factory=dict)


class ObservationRecorder:
    def record_generation(self, observation: GenerationObservation) -> None:
        raise NotImplementedError


class StructuredLogRecorder(ObservationRecorder):
    """Local structured logging recorder (no external platform required)."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("nexus.observability.generation")

    def record_generation(self, observation: GenerationObservation) -> None:
        payload = asdict(observation)
        self._logger.info("generation_observation %s", payload)


class InMemoryObservationRecorder(ObservationRecorder):
    def __init__(self) -> None:
        self.events: list[GenerationObservation] = []

    def record_generation(self, observation: GenerationObservation) -> None:
        self.events.append(observation)
