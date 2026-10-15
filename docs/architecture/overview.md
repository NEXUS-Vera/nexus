# Repository architecture overview

Nexus is a modular monorepo for an agentic engineering platform.

## Layers

| Layer | Role |
| --- | --- |
| `apps/` | Top-level applications (web, API, worker, desktop shell) |
| `agents/` | Domain agents including Vera and specialists |
| `packages/` | Shared platform libraries and contracts |
| `tools/` | Deterministic engineering tools |
| `knowledge/` | Manifests, schemas, and small fixtures |
| `evals/` | Agent-behavior evaluations |
| `infra/` | Infrastructure and deployment configuration |
| `docs/` | Durable documentation and ADRs |

## Dependency direction

```text
apps → agents → packages / tools
apps → packages
packages ↛ apps
packages ↛ agents
agents ↛ other agents' private code
```

Vera communicates with domain agents through `packages/contracts`, not by importing private agent internals.

## Phase 13A architecture scale envelope

Initial POC operating targets (not permanent product limits): System ≤50 nodes / ≤100 edges; Electrical ≤150 nodes / ≤300 connections; Physical ≤100 nodes / ≤200 relationships; combined Project Graph roughly ≤1000 entities+edges. Exercised by `test_layered_architecture_scale.py`.

## Phase 13C Electrical visualization

The Electrical Architecture workspace uses XYFlow with domain-specific node/edge
renderers and Design / Simulation subviews. Canonical Electrical Architecture
remains Nexus-owned; Simulation mode is a derived provider preview (normalized
DTO, not raw `diagram.json`). Provider setup and the opt-in smoke test are
described in `packages/circuit-simulation/README.md`.

## Circuit-simulation provider boundary

Circuit simulation is exposed through the replaceable, provider-neutral
`packages/circuit-simulation` boundary. Wokwi is one adapter and does not own
Nexus's canonical electrical architecture, component plan, or simulation
results. Provider workspaces are derived views and can be regenerated or
translated for another provider.

Real Wokwi execution is an opt-in local integration. It depends on a
user-installed `wokwi-cli`, a user-built firmware ELF, and a Wokwi credential;
Nexus does not install the CLI or build firmware automatically. Credentials
must remain in the local environment and must not be persisted in artifacts,
logs, fixtures, or repository files. Wokwi service availability, account
entitlements, quotas, and commercial terms remain external constraints, so
default tests and core workflows must not depend on live Wokwi access.

## Current status

`apps/api`, `apps/web`, and the `apps/desktop` Electron shell are implemented; see [Current status in the root README](../../README.md#current-status) for what the shipped stack covers, and [ADR-0003](../decisions/ADR-0003-desktop-application.md) for the desktop shipping form factor and how it narrows the meaning of "deployable" for `apps/`.

Modules under `agents/`, `tools/`, `evals/`, and `infra/` are still boundary placeholders. Each module states its own status in its `README.md`.

Foundation modules plus the Phase 11 Artifact Workspace / Project-State Kernel
in `packages/board` and `packages/persistence` (Project Board control plane).
HTTP exposure is in `apps/api`; UI surfaces remain separate.
