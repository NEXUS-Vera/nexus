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

## Artifact Revision Identity (Phase 9+)

Persisted projects keep every artifact revision. Revisions are immutable records, not mutable rows:

- Each physical revision gets a **new** `artifactId`. An existing revision is never rewritten in place.
- `artifactVersion` is monotonically increasing per `(projectId, artifactType)`. It is a per-artifact-type revision counter, not a global sequence and not a schema version.
- A replacing revision points backwards with `supersedesArtifactId` and `supersedesArtifactVersion`. The superseded revision keeps its own identity and moves to lifecycle status `superseded`.
- `project.currentArtifactReferences` points at the current heads only — one reference per artifact type. Reading a project follows these references; it never scans history.
- Uniqueness constraint: `projectId` + `artifactType` + `artifactVersion` identifies exactly one revision.

`schemas/responses/project-history.v1.schema.json` exposes the revision chain (including `supersedes*` links) so history can be audited without loading full artifact content.

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

Generated types are derived from the JSON Schemas:

- `packages/contracts/generated/python/`
- `packages/contracts/generated/typescript/`

Commands:

```bash
make generate-contract-types
```

`make contracts` regenerates in check mode and fails if committed generated output is stale.

Tooling:

- Python: `datamodel-code-generator` → `typing.TypedDict`
- TypeScript: `json-schema-to-typescript`

Generated files include a do-not-edit notice. Re-running generation with unchanged schemas must produce no Git diff.

Backend and frontend import these generated types rather than hand-authoring duplicate contract interfaces.

### TypeScript generation notes

Canonical schemas keep `additionalProperties: false` and conditional keywords (`contains`, `if`/`then`/`else`). For TypeScript codegen only, the generator:

1. collapses compatible object `allOf` branches so discriminated artifact unions do not gain permissive `[k: string]: any` index signatures;
2. strips `contains` / `if` / `then` / `else` (still enforced by runtime JSON Schema validation).

Do not manually edit generated TypeScript. If a future generator regression reintroduces index signatures on `Artifact`, fix bundling/codegen — not the schemas.

## Project Initialization Result Wrapper

`schemas/responses/project-initialization-result.v1.schema.json` is the canonical package wrapper for a successful embedded initialization response. It `$ref`s existing contracts and requires exactly the five v1 artifact types (`project-brief`, `requirement-set`, `functional-architecture`, `next-action`, `component-plan`).

## Project Read and Modification Contracts

Persistence and modification responses reuse the same package shape:

- `schemas/responses/project-current-state.v1.schema.json` is the canonical read response for a persisted project. It keeps the initialization-result shape and adds optional `dependencies` and `previousTurnIds`.
- `schemas/responses/project-history.v1.schema.json` is the lightweight audit view (turns, workflow runs, artifact revisions, responses).
- `schemas/modification/project-change-intent.v1.schema.json` records how a modification request was interpreted, including ambiguities and whether user confirmation is required.
- `schemas/modification/project-impact-analysis.v1.schema.json` classifies propagation across artifact types and requires an explicit reason per affected artifact type.
- `schemas/dependencies/artifact-dependency.v1.schema.json` records directed dependencies between artifact types, optionally pinned to specific revisions.
- `schemas/responses/project-turn-result.v1.schema.json` is the canonical modification-turn response combining current state, intent, impact analysis, and what was changed or regenerated.

## Future API & Events Notes

- HTTP APIs use OpenAPI-compatible request models at the edge and return canonical contract payloads.
- CloudEvents / AsyncAPI remain deferred until message-driven interfaces exist.

## Risk mitigation verification

Risk Register v1 optionally records `mitigationVerificationStatus` (`proposed`,
`evidence-present`, or `verified`) and `mitigationVerifiedByTests` on each risk.
These additive fields describe deterministic verification separately from risk status.
