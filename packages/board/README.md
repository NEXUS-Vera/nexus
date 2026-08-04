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
