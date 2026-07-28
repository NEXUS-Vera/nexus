# Nexus Contracts

## Purpose

Canonical **shared contracts** (schemas, examples, and contract tests) for cross-agent and cross-module interoperability in Nexus.

## JSON Schema Contract Source of Truth

All public contract shapes are defined as **JSON Schema Draft 2020-12** files under `packages/contracts/schemas/`.

Rules:

- JSON Schema files are the canonical source of truth.
- Generated Python/TypeScript types must derive from the JSON Schemas (not independently authored).
- Shared contracts live only in `packages/contracts`. No other module should duplicate these schemas/types.
- Contract changes require contract tests and fixture updates.

## Semantic Schema Version vs Immutable Artifact Revision

Schemas and artifacts must distinguish:

- `schemaVersion`: semantic version of the contract *shape* (e.g. `"1.0.0"`).
- `artifactVersion`: immutable revision number of a specific artifact instance (e.g. `3`).

Compatibility policy:

- Patch: documentation/clarification only; accepted payloads unchanged.
- Minor: backward-compatible optional additions.
- Major: incompatible changes (including removing fields, changing required fields, changing enum meaning, or narrowing allowed values).

Additional rules:

- Schema changes do not mutate historical artifacts.
- Migrations create new representations rather than modifying historical records.
- Public contract changes must not be made silently.
- Enum expansion may break exhaustive consumers and requires compatibility testing.

## Status Dimensions Stay Separate

Artifact status is modeled with separate dimensions:

- lifecycle status
- evidence status
- approval status

Schemas must not combine these into a single generic status field.

## Validation + Semantic Validators

This package includes deterministic validation tooling that:

- validates JSON Schema correctness for all schema files
- validates all `examples/valid/**` fixtures successfully
- validates all `examples/invalid/**` fixtures fail for expected reasons
- runs semantic cross-record checks that JSON Schema cannot express cleanly

Semantic validators live under `packages/contracts/src/` and are executed by the contract validation script and tests.

## v1 Golden Contract Set (Fixture Stability)

For embedded initialization v1, the five valid project fixture families are treated as the **v1 golden contract set**:

- `indoor-environmental-rover`
- `wearable-tremor-monitor`
- `greenhouse-sensing-node`
- `vibration-monitoring-device`
- `robot-obstacle-detection-module`

These fixtures are **manually curated deterministic inputs** (not LLM outputs). Any change to schemas or semantic validators must keep this golden set passing unless an intentional contract revision is approved.

## Blocking Errors vs Non-Blocking Warnings

Semantic validators can emit both blocking errors and non-blocking warnings.

Repository policy for v1 golden fixtures:

- Golden valid fixtures must produce **no blocking semantic errors**.
- Non-blocking warnings are allowed **only** when explicitly allowlisted by validator code and/or the fixture path.
- Unexpected non-blocking warnings fail contract validation (so validator regressions do not silently accumulate).

## Conservative Provenance Validation

Provenance validation in v1 is intentionally conservative and deterministic:

- `user-explicit` requirements must reference the referenced `UserTurn` by `turnId`.
- Lexical/numeric evidence checks are used to detect obvious mismatches; the validator must not claim semantic truth beyond the referenced text.
- Later workflow generation should preserve source spans or structured extraction traces so provenance can be validated more strongly in future phases.

## Component Language Heuristics (Functional Architecture)

The functional-architecture semantic validator distinguishes:

- **Blocking**: concrete component/part identifiers (MCU/sensor/board model strings) appearing at `architectureMaturity = functional`.
- **Non-blocking warnings**: ambiguous technology-level language that may become acceptable at a later logical maturity.
- **No finding**: ordinary functional architecture language and generic abbreviations should not be treated as evidence of concrete component selection.

## Type Generation (Deterministic)

Generated types are intended to be derived from the JSON Schemas:

- `packages/contracts/generated/python/`
- `packages/contracts/generated/typescript/`

For this phase, type generation is **prepared** but not fully implemented if the selected generator cannot faithfully represent the discriminated unions and cross-record invariants without drift.

If generation is blocked:

- `make generate-contract-types` will document the limitation in output (and exit non-zero in this phase)
- `packages/contracts/generated/**` remains empty except for a tracked placeholder (`.gitkeep`)
- contract validation still works without generated types

## Future API & Events Notes (Not Implemented Here)

This slice does not create HTTP APIs or message-driven infrastructure.

Notes:

- future HTTP APIs will use OpenAPI 3.1 and reference these schemas
- future internal events will use CloudEvents-compatible envelopes
- AsyncAPI will be added only when message-driven interfaces exist
