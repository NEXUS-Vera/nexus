# Observability

## Purpose

Logging, tracing, metrics, and agent telemetry helpers.

## Ownership boundary

Shared observability utilities for apps, agents, and tools.

## What belongs here

- Structured logging helpers
- Trace/metric instrumentation utilities

## What must not be placed here

- Production credentials
- Domain business logic

## Current status

`ObservationRecorder` (`recorder.py`) is the shared interface for recording
`GenerationObservation` events emitted by model-gateway callers (stage,
provider, model, duration, token counts, retry/repair counts, validation
result, error code, prompt id/version). Observations never carry raw prompts
or API keys.

Two implementations exist:

- `StructuredLogRecorder` — logs each observation as a structured message via
  the standard `logging` module; requires no external platform.
- `InMemoryObservationRecorder` — accumulates observations in `.events` for
  unit tests and the eval harness.
