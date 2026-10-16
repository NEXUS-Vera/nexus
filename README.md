# Nexus

Nexus is a modular agentic engineering platform. Vera orchestrates specialist domain agents, shared runtime packages, deterministic tools, and evaluation suites so complex engineering work can be planned, executed, and verified with clear architectural boundaries.

## Current status

This repository contains the v1 embedded-project initialization and multi-turn modification stack: shared contracts, an API with project persistence/retrieval, fixture-mode workflows (no model key required by default), and a Vera prototype UI with project workspace routing. Initialization providers are `fixture` (default), `llm`, and `shadow`, selected via `NEXUS_INITIALIZATION_PROVIDER`. Project storage is `memory` (default for tests), `sqlite` (what the packaged desktop shell runs), or `postgres` via `NEXUS_STORAGE_BACKEND` (see `.env.example`, `packages/persistence/README.md`). An Electron desktop shell runs the API as an authenticated loopback sidecar (see `apps/desktop/README.md`).

## Architecture overview

Nexus is a single modular monorepo:

- **`apps/`** — top-level applications (web, API, worker, desktop shell)
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
├── apps/           # Top-level applications
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
- Node.js 20+ and [pnpm](https://pnpm.io/) (web, desktop shell)
- [GitHub CLI](https://cli.github.com/) (`gh`) for contribution workflows

## Setup

```bash
git clone https://github.com/NEXUS-Vera/nexus.git
cd nexus
make setup
```

Setup creates or reuses `.venv` and installs the Python development dependencies
and pnpm workspace dependencies. Make targets use `.venv` automatically; no shell
activation or manual pip install is needed. Run `make test-unit` after setup.

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
| `make test-e2e` | Playwright E2E: the web suite against a live API (fixture + memory; no model key) and the Electron shell suite (needs `xvfb` on Linux) |
| `make clean` | Remove local build and cache artifacts |

## Documentation

- [AGENTS.md](./AGENTS.md) — canonical operating contract for coding agents
- [CONTRIBUTING.md](./CONTRIBUTING.md) — contribution workflow
- [docs/index.md](./docs/index.md) — documentation index
- [apps/api/README.md](./apps/api/README.md) — API application
- [apps/web/README.md](./apps/web/README.md) — web application
- [apps/desktop/README.md](./apps/desktop/README.md) - Electron desktop shell
- [packages/contracts/README.md](./packages/contracts/README.md) — contract package
- [packages/persistence/README.md](./packages/persistence/README.md) — project package store (memory / SQLite / Postgres)

## No-key ESP32 IMU golden demo

After `make setup` (Python 3.11+ and the repository Python dependencies), run:

```bash
make demo-golden
# Or use an existing environment:
make demo-golden PYTHON=/path/to/venv/bin/python
```

This developer demo builds on N24's `esp32-imu-vibration-monitor` flow. It
explicitly selects fixture initialization and removes model API keys from its
child environment. No model API or running API server is needed. It exercises
materialization, electrical/Wokwi translation, firmware scaffold/stub compilation,
real Python analysis, and accepted Test Plan evidence through the in-memory kernel.
R7 becomes VERIFIED at approximately **0.015676 g RMS < 0.10 g**. A second run
injects 0.20 g noise and proves R7 FAILED with linked execution evidence; a
crashing analysis run is also rejected for promotion.

Fixture/fake gates and live gates are printed separately. When `platformio` or
`pio` is on PATH, the demo attempts a real ESP32 build with the checked-in
`platformio.ini` and verifies nonempty ELF/BIN outputs. Initial builds require
PlatformIO's ESP32 platform/toolchain downloads (network access); build errors
and timeouts fail the command. Without the CLI it explicitly reports a GAP.
Wokwi execution always remains a GAP in this no-key demo; diagram translation
is not simulation or hardware validation. Fixture compilation is never live
compile evidence. Synthetic CSV analysis is not evidence from a physical IMU.

The demo accepts an R7 requirement revision to a 0.01 g limit and reports the
old evidence as STALE by comparing its captured requirement version with the
new head. This freshness check is currently in the demo harness: the product's
coverage projection does **not** yet invalidate that old evidence automatically.
The revision uses the in-memory persistence adapter, not the UI turn workflow.
No public contracts or prompts change. This is a scripted kernel integration
demo, not a browser/desktop or live-model end-to-end claim. Reports and build
logs are retained in a printed `/tmp/nexus-demo-golden.*` directory, outside Git.
