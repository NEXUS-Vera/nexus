# ADR-0002 — Mind Graph keeps its own persistence layer

**Status:** Accepted
**Context:** integrating the Mind Graph domain agent into the monorepo.

## Decision

Mind Graph's ledger (`ledger.py`), materialised graph (`graph.py`/`projector.py`), and snapshot cache (`snapshot.py`) remain a self-contained event-sourced store. It does **not** implement `packages/persistence`'s `ProjectPackageStore` protocol, and its node/edge schema (`schema.py`) is not derived from `packages/contracts/schemas`.

## Why

Checked both before deciding, not assumed:

- **`packages/persistence`'s `ProjectPackageStore`** is a narrow protocol — `save_initialization_package`, `save_modification_package`, `get_artifacts`, `list_dependencies`. It manages Vera's project-board packages and artifact revisions. Mind Graph's ledger is a general-purpose append-only event log with a hash chain, crypto-shredding erasure, and a materialised typed graph (six node types, confidence tiers, retraction cascades via ATMS). The two are structurally different — one is a versioned document store, the other is an event-sourced knowledge graph. Adapting Mind Graph onto `ProjectPackageStore` would mean either crippling the graph to fit a document-revision model, or building a second, shadow event log underneath a thin `ProjectPackageStore` shim — which is worse than two honestly-separate systems.
- **`packages/memory/src`** is empty scaffolding (`.gitkeep` only, no implementation). No existing memory system to conflict with. Mind Graph's ledger may be a useful reference when `packages/memory` gets built out — noted as a future opportunity, not a current obligation.
- **`packages/contracts/schemas/common`** has real conceptual overlap: `evidence-reference`, `artifact-status`, `open-question-reference` echo Mind Graph's `Source`/`Artifact`/`Question` node types. This is worth aligning eventually for cross-agent interop, but Mind Graph's types carry confidence tiers, support state, and justification chains that the generic schemas don't — collapsing now would lose information the design depends on. Tracked as future work, not blocking.

## Naming collision, not a code conflict

`packages/contracts/schemas/turns` (`turn-route.v1`, `user-turn.v1`) and Mind Graph's `turn` API route both use the word "turn" for different things — Vera's cross-agent turn routing vs. Mind Graph's internal ask/extraction protocol. No shared code path, no shared schema. Flagged here so nobody reading both in the same sitting assumes they're the same concept. Renaming wasn't done because it's a vocabulary collision inside two different packages, not an actual namespace conflict.

## Consequences

- Mind Graph is integrated as its own domain agent with its own storage, per the modular-monorepo model `ADR-0001` already establishes.
- Cross-agent interop with `packages/contracts` common schemas is a stated future direction, not a current requirement.
- If `packages/memory` is built out later, Mind Graph's ledger/projector split is worth reviewing as a reference implementation.
