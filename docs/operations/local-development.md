# Local development

## Prerequisites

- Git, Make
- Python 3.11+
- Node.js 20+ and pnpm (web application and desktop shell)
- GitHub CLI for contribution workflows

## Setup

```bash
make setup
```

## Verification

```bash
make check
```

`make check` runs repository policy, format check, lint, typecheck, contracts, tests, evaluations, and build. Unavailable language tooling is skipped cleanly when no sources exist; real failures still fail the suite.

## Running the application stack

See [Local development in the root README](../../README.md#local-development) for the targets that start the API and web servers, and [`apps/desktop/README.md`](../../apps/desktop/README.md) for running the Electron shell.
