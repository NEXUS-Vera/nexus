# Embedded Systems Agent

## Purpose

Domain agent for embedded-product engineering workflows.

## Current implementation

Embedded project initialization lives under:

```text
src/nexus_embedded_systems/workflows/project_initialization/
```

The workflow interprets an early-stage embedded-product idea and produces a
project brief, requirements, and a functional architecture. It never performs
firmware/PCB generation, debugging, detailed component selection, or BOM
generation — see `docs/product/embedded-project-initialization-v1.md` for the
frozen workflow boundary. Nothing is persisted and no retrieval/RAG is used:
each run is a stateless request/response over the supplied prompt.

### Provider modes

`NEXUS_INITIALIZATION_PROVIDER` selects how a project package is produced
(see `providers/factory.py`):

- `fixture` (default) — routes supported prompts to golden contract fixtures,
  materializes a fresh project package with remapped IDs, and validates it
  with the shared contracts validators. No LLM calls are made. This is the
  only mode required by `make check` and CI.
- `llm` — runs the deterministic boundary check (`boundary.py`), then staged
  LLM generation (interpretation → brief → requirements → functional
  architecture) via `nexus_model_gateway`, normalizes/validates each draft,
  and repairs invalid drafts up to `NEXUS_MODEL_MAX_REPAIR_ATTEMPTS` times
  before failing with `LLM_INITIALIZATION_VALIDATION_FAILED`.
  `NEXUS_MODEL_PROVIDER`, `NEXUS_MODEL_NAME`, `NEXUS_MODEL_API_KEY`,
  `NEXUS_MODEL_TIMEOUT_SECONDS`, and `NEXUS_MODEL_BASE_URL` configure the
  gateway (`openai` or `anthropic`).
- `shadow` — runs both `fixture` and `llm`, always returns the `fixture`
  result to the caller, and records the LLM outcome (success or failure)
  through `nexus_observability` without ever propagating an LLM error.

### Typed execution-plan review (W2)

`workflows/project_modification/execution_plan.py` handles provider-independent,
bounded typed review and ESP32/MPU6050 workspace preparation using shared board
revision and file services. It does not extend the fixture prose interpreter to
live conversation. See the W2 section of the initialization boundary document for
supported selections, failure/retry semantics and the open live acceptance gate.

### Staged generation and repair

`LlmInitializationProvider` generates artifacts in stages, minting all IDs
itself (`proj_`, `art_`, `req_`, etc. — never trusting model-provided IDs) and
recording each step on the workflow ledger. `select_next_action`
(`next_action_selector.py`) deterministically prioritizes the single
highest-priority follow-up (blocking issues > multi-artifact open questions >
missing dimensions > component-selection scoping) rather than asking the
model to choose.

### Evaluation

The embedded-project-initialization eval harness (`evals/`) runs golden and
adversarial prompts against this workflow; see `evals/README.md` for the
command.

## Ownership boundary

- Belongs here: embedded workflows, validators, prompts, adapters to contracts/tools
- Must not: Vera orchestration, shared platform libraries, other agents' private code

### Bounded execution repair (W5 / P2)

`workflows/repair.py` coordinates failure inspection, guarded correction review,
and affected compile/simulation/analysis reruns. Its resumable progress uses the
existing project event ledger; jobs, proposals, immutable snapshots and outputs
retain their existing stores. See the W5 API section in
[`apps/api/README.md`](../../apps/api/README.md) for actions, bounds and explicit
unavailability/diagnostic limitations. Scripted gateways demonstrate regression
control flow only. This workflow does not add W6 provenance or W8 UI integration.
