# ADR-0001: Use a modular monorepo

## Status

Accepted

## Context

Nexus comprises Vera (global orchestrator), domain agents, shared runtime packages, deterministic tools, evaluations, applications, and infrastructure. These components share contracts, evolve together, and must enforce clear architectural boundaries for humans and coding agents.

A multi-repo model would isolate agents but would also multiply versioning, contract drift, CI duplication, and contribution friction early in the project lifecycle.

## Decision

Nexus will use **one modular monorepo**.

Individual agents will **not** have separate repositories. Internal modules may later become independently deployable artifacts while remaining in this repository until extraction criteria are met.

## Consequences

- Shared contracts, tooling, CI policy, and contribution rules remain centralized.
- Coding agents and humans navigate one ownership map (`apps/`, `agents/`, `packages/`, `tools/`, `evals/`, `infra/`, `docs/`).
- Module boundaries must be enforced through documentation, CODEOWNERS, reviews, and policy checks rather than repository isolation.

## Benefits

- Single source of truth for schemas and interfaces in `packages/contracts`.
- Atomic cross-module changes and coordinated evaluations.
- Consistent naming, documentation, and CI foundations.
- Lower operational overhead during early product development.
- Clear path for coding agents to discover ownership without cross-repo search.

## Tradeoffs

- Repository size and CI scope grow as modules mature.
- Weak boundary discipline can allow accidental coupling.
- Access control is coarser than fully separate repositories.
- Release and deployment pipelines must eventually support selective module builds.

## Future extraction criteria

A module may be considered for extraction into a separately deployable unit (still preferably published from this monorepo) or, in exceptional cases, a separate repository when **all** of the following are true:

1. It has a stable public contract and independent release cadence.
2. Cross-module change frequency is low and well-versioned.
3. Operational ownership, scaling, or compliance requires stronger isolation.
4. Extraction cost is justified and recorded in a new ADR.
