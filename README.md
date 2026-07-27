# Nexus

Nexus is a modular agentic engineering platform. Vera orchestrates specialist domain agents, shared runtime packages, deterministic tools, and evaluation suites so complex engineering work can be planned, executed, and verified with clear architectural boundaries.

## Current status

This repository currently contains **foundation and governance only**. No product logic, agents, APIs, or user interfaces have been implemented yet.

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
- Python 3.11+ (for future Python packages and policy scripts)
- Node.js 20+ and [pnpm](https://pnpm.io/) (for future TypeScript packages)
- [GitHub CLI](https://cli.github.com/) (`gh`) for contribution workflows

## Setup

```bash
git clone https://github.com/NEXUS-Vera/nexus.git
cd nexus
make setup
```

## Common commands

| Command | Purpose |
| --- | --- |
| `make setup` | Install available tooling and prepare the workspace |
| `make format` | Format source files where tooling exists |
| `make lint` | Lint source files where tooling exists |
| `make typecheck` | Run type checkers where applicable |
| `make test` | Run unit and integration tests |
| `make contracts` | Validate contract schemas and examples |
| `make policy` | Enforce repository content policy |
| `make check` | Run the full local verification suite |
| `make build` | Build packages when build targets exist |
| `make clean` | Remove local build and cache artifacts |

## Documentation

- [AGENTS.md](./AGENTS.md) — canonical operating contract for coding agents
- [CONTRIBUTING.md](./CONTRIBUTING.md) — contribution workflow
- [docs/index.md](./docs/index.md) — documentation index

Product functionality is intentionally not implemented in this initialization.
