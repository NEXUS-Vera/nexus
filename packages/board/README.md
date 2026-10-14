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
content-addressed file store. Acquire an edit lease before changing files or
creating/restoring an immutable snapshot. `kernel.workspace_runtime` exposes
artifact-scoped files, snapshots, execution, logs, cancellation and outputs.

Executions consume snapshots rather than mutable drafts. Jobs persist their
state and runtime identity, apply queue/concurrency/time/log/output limits, and
recover interrupted work on startup. Only declared successful outputs are
promoted. Retention protects referenced snapshots and reclaims orphan blobs.

The process runtime has limited isolation; use the container runtime for its
stronger filesystem/network/resource boundaries. Live Docker/Postgres acceptance
tests require explicit configuration and do not substitute process runs.
