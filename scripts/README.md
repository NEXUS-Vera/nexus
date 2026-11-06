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

## Golden acceptance entry point

With the API running in the acceptance environment:

```bash
python scripts/run_golden_acceptance.py --api-url http://127.0.0.1:8000 --require-real
```

The runner reads `NEXUS_API_SESSION_TOKEN` (development token by default), creates
fresh projects, accepts their derived plans and applies bounded firmware proposals
as the demo operator. It drives baseline verification, F2/F4/F5 repairs, M5
invalidation and re-verification through public HTTP endpoints. `--timeout` is a
per-step deadline in seconds (default 240); `--step N` runs prerequisites through
step N, with no resume state. Failures include step, project and HTTP context.
The initialization provider must produce a supported ESP32/MPU6050 pair; unsupported
or ambiguous fixture/live plans fail visibly rather than rewriting project intent.

`--require-real` rejects fixture compile/proposal metadata and requests real
execution; it does not prove physical hardware behavior. R2/R3 remain manual
inspection. Persistence checks cover repeated HTTP reads, immutable run inputs and
analysis input hashes; process restart is covered separately by the API restart
test. Follow [live acceptance](../docs/operations/first-loop-live-acceptance.md)
for environment prerequisites and failure triage. Offline ASGI/mock tests are
regression evidence only.
