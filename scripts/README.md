# Repository Scripts

## Purpose

Root scripts for setup, policy checks, contracts, and make targets.

## Ownership boundary

Monorepo developer and CI helper scripts.

## What belongs here

- Policy enforcement
- Format/lint/test orchestration
- Contract validation

## What must not be placed here

- Product features
- Agent implementations

## Current status

Implemented. These scripts back the `make` targets; `make check` runs the policy,
format, lint, typecheck, contracts, test, evaluation, and build scripts in order.
See [Common commands in the root README](../README.md#common-commands) for the
targets themselves.

## Python typecheck baseline

When Pyright is installed, `make typecheck` compares its errors with
`scripts/pyright-baseline.json` (Pyright 1.1.414). The sorted JSON object maps
`relative-file::rule` to error counts; messages and line numbers are ignored.
Existing counts and removals pass; increased counts or new keys fail and print
the current diagnostics for those keys. The TypeScript check still runs.

After reviewing intentional baseline changes, regenerate from the repository root
in the canonical environment (dependency availability can change diagnostics):

```bash
python3 scripts/pyright-baseline.py --update
```

Review the JSON diff before committing; updating accepts all current errors.
