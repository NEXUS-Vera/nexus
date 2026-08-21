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
