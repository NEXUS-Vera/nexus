# Board

## Purpose

Artifact workspace and project-state kernel for Nexus: typed registries,
governance, workspace/command/execution services, ledger, graph reader, and
board projection — without React or HTTP routes.

## Ownership boundary

Application services consumed by `apps/api` and agents. Persistence adapters
live in `packages/persistence`. Contracts live in `packages/contracts`.

## What belongs here

- Artifact type, runtime capability, and external provider registries
- Approval / concurrency governance
- Workspace, command, execution, ledger, graph, and projection services
- `ProjectKernel` wiring via `build_project_kernel(store)`

## What must not be placed here

- UI components or React
- FastAPI / HTTP routes
- SQLAlchemy models or Alembic migrations
- Real vendor integrations (only the `fake` provider)

## Kernel entrypoint

```python
from nexus_persistence import build_stores
from nexus_board import build_project_kernel

project_store, kernel_store = build_stores(backend="memory")
kernel = build_project_kernel(kernel_store, project_store=project_store)
```

Commands are dispatched through a single service:

```python
kernel.dispatch(artifact_command_dict)
```

The hidden `execution-plan` structured artifact uses ordinary snapshot/proposal
revision governance. The application injects the owning embedded workflow's
revision validator and materializer; the shared kernel imports no domain agent.
Plan acceptance always requires a user and its original project/artifact basis.
A missing workflow handler blocks approval rather than accepting an inert plan.

## Component Plan (Phase 12)

The default artifact-type registry includes `component-plan` in the DESIGN phase
with a comparison workspace. Dependencies:

- `functional-architecture` → `component-plan` (required)
- `requirement-set` → `component-plan` (required)
- `component-plan` → `next-action` (optional)

Board projections populate optional Component Plan summary fields when the
artifact exists: `maturity`, `roleCount`, `candidateCount`, `selectedCount`,
`awaitingApprovalCount`, `blockedRoleCount`, and
`unresolvedCompatibilityCheckCount`.

## Filesystem workspaces and execution jobs

The hidden `code-scratch` artifact provides generic editable files backed by a
content-addressed file store. With file-backed SQLite, the default is a durable
`files/` directory beside the database. `NEXUS_FILE_STORE_ROOT` overrides it;
in-memory/no-file databases retain in-memory storage. Acquire an edit lease before
changing files or
creating/restoring an immutable snapshot. `kernel.workspace_runtime` exposes
artifact-scoped files, snapshots, execution, logs, cancellation and outputs.

Executions consume snapshots rather than mutable drafts. Jobs persist their
state and runtime identity, apply queue/concurrency/time/log/output limits, and
recover interrupted work on startup. Only declared successful outputs are
promoted. Retention protects referenced snapshots and reclaims orphan blobs.

The process runtime has limited isolation; use the container runtime for its
stronger filesystem/network/resource boundaries. Containers run as the nonroot
workspace owner so the materialized directory remains private (`0700`); root-owned
workspaces are rejected. Live Docker/Postgres acceptance
tests require explicit configuration and do not substitute process runs.

## Firmware workspace

The `firmware` artifact exposes deterministic ESP32 Arduino scaffolding, patch
proposals pinned to immutable snapshots, guarded patch application, history and
compile/test operations through `kernel.workspace_runtime`. Compile consumes a
pre-compile snapshot and promotes only declared successful outputs.

`NEXUS_FIRMWARE_USE_STUB=1` runs offline fixtures; when unset, Nexus uses
PlatformIO if `pio` is available and otherwise falls back to the stub. Fixture
outputs are not real build or device evidence. Set it to `0` to run PlatformIO
and configure the execution runtime/image for the preinstalled toolchain.
Live toolchain/container acceptance tests require explicit opt-in.

## Layered architecture

Electrical and Physical Architecture use graph workspaces with deterministic
validation, semantic editing, and functional-node deletion impact inspection.
Accepted revisions materialize graph entities and update board projections.
Electrical execution delegates to an injected `circuit-simulation` executor;
provider translation and invocation belong to `packages/circuit-simulation`.


## Analysis and deterministic VERIFY

The `analysis` workspace supports scaffolding, guarded patch proposals, input
upload/import, immutable execution snapshots, reruns, output comparison and
preview. Analysis patch payloads reuse the predecessor's durable patch store;
`anpatch_` IDs and artifact-type validation separate them from firmware proposals.
`NEXUS_ANALYSIS_USE_STUB=1` selects offline fixtures; set it to `0` for Python
execution with the configured runtime and preinstalled analysis dependencies.

`kernel.verification` promotes evidence only from completed execution runs into
new Test Plan revisions and projects requirement coverage separately from
verification. Analysis summary promotion also requires an existing run in the same
project with status `completed` or `completed-with-warnings` and no truncated job
logs; missing run IDs are rejected rather than generated. The HTTP summary route
requires `executionRunId` and returns 422 for gate failures (404 for unknown runs).
Metric criteria are assessed by deterministic code. Repeated promotion is idempotent, and the
Risk Register retains monitoring for risks requiring physical evidence. Mitigation
verification requires every declared verification test to exist and pass. The API
and Evidence Explorer expose the resulting evidence chain.

Verification promotions pin requirement-entry and criterion hashes, producer snapshots,
and graph dependencies in each case's `verificationBasis`. Accepted artifact changes
write a system Test Plan revision marking affected cases `STALE`; missing or unresolved
basis yields `RECHECK_REQUIRED`, including a recorded backfill on projection reads.
Historical observations and evidence remain intact. Only a completed, non-truncated
run against current inputs can restore `CURRENT`; model-authored revisions cannot
edit applicability or basis. These states persist in existing artifacts, graph and ledger.

The golden ESP32/MPU6050 fixture uses `time_s` (seconds) and `accel_*_g`
(acceleration in g) throughout firmware telemetry and analysis CSVs. Firmware
emits the CSV header at startup; strip the `TEL,` frame prefix when capturing
samples as CSV. Golden G1 runs real Python analysis and promotes its execution
outputs into R7/R8 verification; a failed execution is rejected. Its report is
written under pytest's temporary directory. Firmware stub outputs and unavailable
live compile/Wokwi gates remain explicit gaps.

W6 handoffs reuse `ExecutionRun.inputOutputReferences` for the simulator's ELF
and snapshot manifest `generatedFrom: imported-output:<outputId>` for analysis
observations. Dependency edges connect consuming runs to producing runs; the
assessment basis retains each producer's exact snapshot hash and revision.
Foreign, missing, or byte-mismatched imported output basis remains unresolved
and yields `RECHECK_REQUIRED`, while direct user datasets have no invented
simulation parent. Inline output digests cover structured content; imported
file hashes cover the actual text bytes, so these are compared in their proper
representations.

N162 map decisions: W3 already supplies electrical/approved-plan content and W4
already delivers explicit ELF bytes. No new output graph node type or delivery
protocol is needed: output records retain IDs/digests, existing execution nodes
capture causality. Analysis must follow the actual imported output rather than
pin every analysis to whichever firmware happens to be current. Firmware
requests retain reviewed plan source content in `artifacts` and also expose
`currentArtifacts`; `inputArtifactReferences` names every inspected revision,
including both versions when they differ. Analysis requests include current
requirements, components, interfaces, plan and test criteria, plus imported-output
markers and hashes in snapshot files. Ordinary authoring and repair use the same
context assembly and proposal store; there is no second context ledger.

The HTTP W6 regression uses a scripted compiler and simulator with real Python
analysis and durable SQLite/blob storage. It proves identity/hash/byte continuity
through restart, not live engineering acceptance. Live model/build/simulator
acceptance remains unresolved unless separately executed. Provenance assertions
alone do not establish the accepted-change, replay and revalidation lifecycle gate.

W7 extends that HTTP regression with accepted requirement, electrical-interface
pin intent, firmware source and analysis-input revisions. Each linked project
checks transitive applicability and graph paths, unrelated requirement/result
stability, byte-equivalent historical Test Plan content and output previews,
old-run replay, current reruns and user-authorized verification. It repeats the
cycle after SQLite restart and delivers invalidation triggers twice at the
existing service seam. Product operations use authenticated HTTP; scripted
compiler/simulator injection and duplicate delivery are explicit test seams.
Re-import replaces the consumed output marker even when telemetry bytes are
identical. Reason traversal selects the assessed run and follows its upstream
runs rather than cutting off multi-tool paths. Revalidation events remain in
the existing event feed; the invalidations endpoint retains its invalidation-only
contract. No public schema, prompt or UI state is added.

W7 pre-map hunches: analysis's empty static dependency list is intentional;
actual imported outputs supply dependencies. Accepted workspace snapshots already
support the tested current-hash comparison, so no draft-hash fallback is added.
After an interface change, firmware is revised and accepted before rerunning.
Open live acceptance question: the current golden simulator uses a fixed pin
profile; changing pin intent in the architecture description and firmware does
not establish alternate-pin simulation fidelity. Scripted regression results
cannot close that gate or the configured live model/build/simulator gate. These
remain unresolved pending actual live acceptance; W8 UI work is separate.
