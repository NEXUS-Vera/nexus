# Evaluations

## Purpose

Agent-behavior evaluation suites, kept separate from ordinary unit tests.

## Ownership boundary

Evaluation scenarios and fixtures for Vera, domain agents, and integration flows.

## What belongs here

- Evaluation definitions
- Shared eval fixtures
- Scenario metadata

## What must not be placed here

- Unit tests for deterministic code
- Product implementation
- Large generated result dumps

## Current status

`embedded_project_initialization/` evaluates the embedded-systems agent's
`LlmInitializationProvider` pipeline (deterministic boundary check, staged
generation, assembly, and contract validation) against golden and adversarial
prompts:

- `cases/golden.yaml` — one case per fixture family, asserting expected
  explicit claims and missing dimensions.
- `cases/adversarial.yaml` — software-only, component-selection-only,
  debugging, multi-product, ambiguous, numeric, contradictory,
  fixed-component, sparse, and prompt-injection prompts, asserting the
  workflow either stays in scope or is correctly rejected.
- `scorers/` — structural (schema + semantic validation) and golden-claim
  (explicit claims, missing dimensions, forbidden component/selection
  leakage) scoring, plus metric aggregation.
- `gates.py` — quality gates applied to the aggregated run (pass-rate floors,
  outcome mismatches, forbidden-leakage failures).

Run the suite:

```bash
make eval-embedded-initialization
# or, for a live model run (requires NEXUS_MODEL_API_KEY):
PROVIDER=llm make eval-embedded-initialization
```

The default `--provider fake` mode never calls a live model: it drives the
real provider pipeline with a `FakeModelGateway` scripted per case, so it
needs no credentials and is safe to run in CI. It also runs automatically as
part of `make eval` (and therefore `make check`) in fake mode only.
