# Repository architecture overview

Nexus is a modular monorepo for an agentic engineering platform.

## Layers

| Layer | Role |
| --- | --- |
| `apps/` | Deployable applications (web, API, worker) |
| `agents/` | Domain agents including Vera and specialists |
| `packages/` | Shared platform libraries and contracts |
| `tools/` | Deterministic engineering tools |
| `knowledge/` | Manifests, schemas, and small fixtures |
| `evals/` | Agent-behavior evaluations |
| `infra/` | Infrastructure and deployment configuration |
| `docs/` | Durable documentation and ADRs |

## Dependency direction

```text
apps → agents → packages / tools
apps → packages
packages ↛ apps
packages ↛ agents
agents ↛ other agents' private code
```

Vera communicates with domain agents through `packages/contracts`, not by importing private agent internals.

## Phase 13A architecture scale envelope

Initial POC operating targets (not permanent product limits): System ≤50 nodes / ≤100 edges; Electrical ≤150 nodes / ≤300 connections; Physical ≤100 nodes / ≤200 relationships; combined Project Graph roughly ≤1000 entities+edges. Exercised by `test_layered_architecture_scale.py`.

## Phase 13C Electrical visualization

The Electrical Architecture workspace uses XYFlow with domain-specific node/edge
renderers and Design / Simulation subviews. Canonical Electrical Architecture
remains Nexus-owned; Simulation mode is a derived provider preview (normalized
DTO, not raw `diagram.json`). See
[`golden-full-demo-execution.md`](./golden-full-demo-execution.md).

## Circuit-simulation provider boundary

Circuit simulation is exposed through the replaceable, provider-neutral
`packages/circuit-simulation` boundary. Wokwi is one adapter and does not own
Nexus's canonical electrical architecture, component plan, or simulation
results. Provider workspaces are derived views and can be regenerated or
translated for another provider.

Real Wokwi execution is an opt-in local integration. It depends on a
user-installed `wokwi-cli`, a user-built firmware ELF, and a Wokwi credential;
Nexus does not install the CLI or build firmware automatically. Credentials
must remain in the local environment and must not be persisted in artifacts,
logs, fixtures, or repository files. Wokwi service availability, account
entitlements, quotas, and commercial terms remain external constraints, so
default tests and core workflows must not depend on live Wokwi access.

## Phase 14A filesystem workspace spine

Filesystem-capable workspaces reuse the Phase 11 workspace identity, draft
lease, and `WorkspaceSnapshot` lifecycle. Mutable file metadata lives in
`workspace_files`; bytes are content-addressed in a replaceable `FileStore`
(`InMemoryFileStore` / `LocalFileStore`). Snapshots may capture either
structured JSON or an immutable filesystem manifest. Ordinary file edits do
not create artifact revisions.

## Phase 14B sandboxed execution runtime

Phase 14B adds Nexus-owned sandboxed compute on filesystem snapshots:

```text
filesystem WorkspaceSnapshot
  → ExecutionRun (product-facing)
  → ExecutionJob (infrastructure-only)
  → ExecutionRuntime (process runtime in 14B)
  → logs + declared ProducedOutputs
```

Job statuses map onto run statuses; `stale` remains an ExecutionRun concern.
Wokwi stays provider-direct (`ExecutionRun` → circuit adapter → Wokwi →
`SafeSubprocessRunner`) and is not migrated into `ExecutionJob`. The default
process runtime is intentionally weaker than a container sandbox: no inherited
API/provider secrets, process-group kill, ephemeral materialization, and
bounded logs/outputs — but no network/cgroup isolation yet.

## Phase 14C runtime hardening

Phase 14C hardens the shared runtime without changing the product hierarchy:

- `LocalContainerRuntime` behind the same `ExecutionRuntime` interface (`securityLevel=isolated`)
- Explicit selection via `NEXUS_EXECUTION_RUNTIME=process|container` (no silent downgrade)
- Image digest recorded on job/run identity; network default `none`
- Idempotent cleanup, crash/restart recovery (`RUNTIME_LOST`), bounded scheduler health
- Reference-aware retention/GC for orphan blobs, reclaimable filesystem snapshots, and terminal logs
- ProcessRuntime remains the weaker explicit fallback/test path (`securityLevel=limited`)

Docker is optional. Ordinary `make check` uses ProcessRuntime offline. Opt-in:

```text
RUN_DOCKER_INTEGRATION=1
NEXUS_EXECUTION_RUNTIME=container
```

Admin/dev GC preview defaults to dry-run: `POST /v1/admin/retention/gc?dry_run=true`.
Scheduler/runtime health: `GET /v1/runtime/health`.

### Local container demo (opt-in)

```bash
export NEXUS_EXECUTION_RUNTIME=container
export NEXUS_EXEC_CONTAINER_IMAGE=python:3.13-slim
docker pull "$NEXUS_EXEC_CONTAINER_IMAGE"
RUN_DOCKER_INTEGRATION=1 python -m pytest \
  packages/board/tests/test_runtime_hardening.py::test_container_runtime_isolation_smoke -q
```

## Phase 14D workspace runtime handoff

Phase 14D adds a thin application facade `WorkspaceRuntimeService`
(`kernel.workspace_runtime`) that composes filesystem, snapshots, sandboxed
execution, logs, cancellation, and declared outputs without exposing
`ProcessRuntime`, `LocalContainerRuntime`, scheduler, FileStore, or GC
internals to Phase 15.

Artifact workspaces bind to filesystem workspaces by
`(projectId, artifactType)`. Capabilities come from the artifact-type
registry (`file-workspace`, `sandbox-execution`). Artifact-scoped HTTP routes
live under `/v1/projects/{projectId}/artifacts/{artifactType}/workspace/...`.

Wokwi remains provider-direct and is not routed through this facade.

## Phase 15A Firmware filesystem editor

Phase 15A registers canonical `firmware` (`code-workspace` + `file-workspace` /
`sandbox-execution`) and ships a Monaco + file-tree UI that edits files only
through the Phase 14D artifact-scoped workspace APIs.

## Phase 15B Firmware scaffold

Phase 15B adds an explicit, deterministic PlatformIO-compatible ESP32/Arduino
scaffold (`platformio-arduino-esp32-v1`) via
`POST .../artifacts/firmware/workspace/scaffold`. Generation refuses unsafe
overwrite of existing target paths, records `workspace.scaffold-generated`
ledger provenance, and does not install or invoke PlatformIO.

## Phase 17 VERIFY (Test Plan / Risk Register)

Phase 17A–17E adds structured `test-plan` and `risk-register` board artifacts,
deterministic criterion assessment, requirement coverage aggregation, evidence
resolvers over existing ProducedOutput/ExecutionRun infrastructure, and
operational VERIFY UX. Golden `esp32-imu-vibration-monitor` includes T1–T8 with
R7 evidence closure and realistic risks (K6 remains monitoring without hardware
evidence).

Phase 17F adds product-path evidence promotion (`VerificationService` → Test Plan
revision), live LLM Test/Risk draft generation with deterministic validation and
fallback, Evidence Explorer chains, hermetic G1 E2E + negative paths N1–N9, and
idempotent reprocessing.

## Current status

Foundation modules plus the Phase 11–14 workspace/runtime kernel in
`packages/board` and `packages/persistence`. HTTP exposure is in `apps/api`;
UI surfaces remain separate. Phase 14 shared runtime is frozen; Phase 15–16
BUILD workspaces and Phase 17 VERIFY consume board artifacts without reopening
Phase 14.