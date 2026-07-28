# Embedded Systems Agent

## Purpose

Domain agent for embedded-product engineering workflows.

## Current implementation

Fixture-backed embedded project initialization lives under:

```text
src/nexus_embedded_systems/workflows/project_initialization/
```

This phase routes supported prompts to golden contract fixtures, materializes a fresh project package with remapped IDs, and validates the package with the shared contracts validators. No LLM calls are used.

## Ownership boundary

- Belongs here: embedded workflows, validators, prompts, adapters to contracts/tools
- Must not: Vera orchestration, shared platform libraries, other agents' private code
