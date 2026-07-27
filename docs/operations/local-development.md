# Local development

## Prerequisites

- Git, Make
- Python 3.11+
- Node.js 20+ and pnpm (when TypeScript packages exist)
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

Product services are not implemented yet; there is no local application stack to start.
