# Repository architecture overview

Nexus is a modular monorepo for an agentic engineering platform.

## Layers

| Layer | Role |
| --- | --- |
| `apps/` | Deployable applications (web, API, worker) |
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

Foundation modules plus the Phase 11 Artifact Workspace / Project-State Kernel
in `packages/board` and `packages/persistence` (Project Board control plane).
HTTP exposure is in `apps/api`; UI surfaces remain separate.
