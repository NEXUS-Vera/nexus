# Nexus

Nexus is a modular agentic engineering platform. Vera orchestrates specialist domain agents, shared runtime packages, deterministic tools, and evaluation suites so complex engineering work can be planned, executed, and verified with clear architectural boundaries.

## Current status

This repository contains the v1 embedded-project initialization and multi-turn modification stack: shared contracts, an API with project persistence/retrieval, fixture-mode workflows (no model key required by default), and a Vera prototype UI with project workspace routing. Initialization providers are `fixture` (default), `llm`, and `shadow`, selected via `NEXUS_INITIALIZATION_PROVIDER`. Project storage is `memory` (default for tests) or `postgres` via `NEXUS_STORAGE_BACKEND` (see `.env.example`, `packages/persistence/README.md`).

## Architecture overview

Nexus is a single modular monorepo:

- **`apps/`** — deployable applications (web, API, worker)
- **`agents/`** — domain agents (Vera orchestrator, embedded-systems specialist, …)
- **`packages/`** — shared platform capabilities (runtime, contracts, memory, retrieval, …)
- **`tools/`** — deterministic, independently testable engineering tools
- **`knowledge/`** — manifests, schemas, and small fixtures (not large binaries)
- **`evals/`** — agent-behavior evaluations, separate from unit tests
- **`infra/`** — Terraform, Docker, and infrastructure scripts
- **`docs/`** — durable long-form documentation and ADRs

Applications may depend on agents and packages. Agents may depend on packages and tools. Shared packages must not depend on apps or specific domain agents. See [AGENTS.md](./AGENTS.md) for the full boundary rules.

## Top-level map

```text
nexus/
├── apps/           # Deployable applications
├── agents/         # Domain agent packages
├── packages/       # Shared platform libraries
├── tools/          # Deterministic engineering tools
├── knowledge/      # Manifests, schemas, fixtures
├── evals/          # Agent evaluations
├── infra/          # Infrastructure configuration
├── docs/           # Durable documentation
├── scripts/        # Repository scripts
└── .github/        # CI, templates, ownership
```

## Prerequisites

- Git
- Make
- Python 3.11+ (API, contracts, agents)
- Node.js 20+ and [pnpm](https://pnpm.io/) (web)
- [GitHub CLI](https://cli.github.com/) (`gh`) for contribution workflows

## Setup

```bash
git clone https://github.com/NEXUS-Vera/nexus.git
cd nexus
make setup
```

## Local development

```bash
make generate-contract-types
make dev-api    # http://127.0.0.1:8000
make dev-web    # http://localhost:5173
# or both:
make dev
```

## Common commands

| Command | Purpose |
| --- | --- |
| `make setup` | Install available tooling and prepare the workspace |
| `make generate-contract-types` | Generate Python/TS types from JSON Schemas |
| `make format` | Format source files where tooling exists |
| `make lint` | Lint source files where tooling exists |
| `make typecheck` | Run type checkers where applicable |
| `make test` | Run unit and integration tests |
| `make contracts` | Validate contract schemas, examples, and generated types |
| `make policy` | Enforce repository content policy |
| `make check` | Run the full local verification suite |
| `make eval-embedded-initialization` | Run the embedded-project-initialization eval suite (fake provider by default) |
| `make dev` / `make dev-api` / `make dev-web` | Local API and web servers |
| `make dev-db` / `make db-migrate` | Start local Postgres and apply migrations |
| `make test-e2e` | Playwright E2E (fixture + memory; no model key) |
| `make clean` | Remove local build and cache artifacts |

## Documentation

- [AGENTS.md](./AGENTS.md) — canonical operating contract for coding agents
- [CONTRIBUTING.md](./CONTRIBUTING.md) — contribution workflow
- [docs/index.md](./docs/index.md) — documentation index
- [apps/api/README.md](./apps/api/README.md) — API application
- [apps/web/README.md](./apps/web/README.md) — web application
- [packages/contracts/README.md](./packages/contracts/README.md) — contract package
- [packages/persistence/README.md](./packages/persistence/README.md) — project package store (memory / Postgres)
