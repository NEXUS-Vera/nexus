# Model Gateway

## Purpose

Model-provider abstraction and routing.

## Ownership boundary

Shared model access layer for agents and workers.

## What belongs here

- Provider interfaces
- Routing and request shaping helpers

## What must not be placed here

- Hard-coded provider secrets
- Domain prompts
- App UI

## Current status

`ModelGateway` (`protocol.py`) is the shared async boundary domain workflows
call instead of a provider SDK directly: `generate_structured(...)` takes a
task name, system instructions, an input payload, a JSON output schema, and a
`ModelPolicy`, and returns a `StructuredGenerationResult` (or raises
`ModelGatewayError` on transport, configuration, or parse failures).

Two implementations exist:

- `OpenAICompatibleGateway` — calls an OpenAI-compatible chat-completions
  endpoint over `urllib` (no extra HTTP dependency) and parses/validates the
  JSON response against the caller's schema.
- `FakeModelGateway` — a scripted, in-memory gateway for deterministic tests
  and the eval harness. Register per-task-name callables with `set_script`
  (or a default with `set_default_script`); scripts can return a payload dict
  or raise `ModelGatewayError` to simulate transport/validation failures. Every
  call is recorded in `.calls` for assertions.

Consumers select a provider via `NEXUS_MODEL_PROVIDER`, `NEXUS_MODEL_NAME`,
`NEXUS_MODEL_API_KEY`, `NEXUS_MODEL_TIMEOUT_SECONDS`, and
`NEXUS_MODEL_MAX_REPAIR_ATTEMPTS` (see the embedded-systems agent's
`providers/factory.py` for the concrete wiring).
