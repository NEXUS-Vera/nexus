# Repository architecture overview

Nexus is a modular monorepo for an agentic engineering platform.

## Layers

| Layer | Role |
| --- | --- |
| `apps/` | Deployable applications (web, API, worker, desktop shell) |
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

## Current status

`apps/api`, `apps/web`, and the `apps/desktop` Electron shell are implemented; see [Current status in the root README](../../README.md#current-status) for what the shipped stack covers, and [ADR-0003](../decisions/ADR-0003-desktop-application.md) for the desktop shipping form factor and how it narrows the meaning of "deployable" for `apps/`.

Modules under `agents/`, `tools/`, `evals/`, and `infra/` are still boundary placeholders. Each module states its own status in its `README.md`.
