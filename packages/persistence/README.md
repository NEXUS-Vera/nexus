# Persistence

## Purpose

Shared project-package and Phase 11 workspace-kernel persistence for Nexus:
repository interfaces and in-memory / PostgreSQL adapters.

## Ownership boundary

Applications and domain agents depend on the `ProjectPackageStore` and
`ProjectKernelStore` protocols. SQL and ORM details stay inside this package.

## What belongs here

- Store protocols and errors
- In-memory and PostgreSQL implementations (`InMemoryProjectStore`,
  `InMemoryKernelStore`, `PostgresProjectStore`, `PostgresKernelStore`)
- Alembic migrations for project packages and the workspace kernel
- Behavioral contract tests for both backends

## What must not be placed here

- HTTP routes
- Agent prompts or modification interpretation
- UI code
- Secrets
- Board application policy (lives in `packages/board`)

## Artifact revision identity

- Each physical revision gets a new `artifactId`
- `artifactVersion` is monotonic per `(projectId, artifactType)`
- New revisions set `supersedesArtifactId` / `supersedesArtifactVersion`
- `project.currentArtifactReferences` point at current heads
- Uniqueness: `(project_id, artifact_type, artifact_version)` and unique `artifact_id`

## Phase 11 kernel tables

Workspaces, drafts, immutable snapshots, proposals, command runs, execution
runs, produced outputs, append-only project events, board projections, and
graph nodes/edges. Migration: `0002_phase11_workspace_kernel`.

`accept_proposal_transaction` atomically validates concurrency, inserts a new
artifact revision, advances `currentStateVersion`, appends events, updates
graph edges, and upserts the board projection.

## Storage backends

| Backend | Env |
| --- | --- |
| `memory` (default for tests) | `NEXUS_STORAGE_BACKEND=memory` |
| `postgres` (local demo) | `NEXUS_STORAGE_BACKEND=postgres` and `NEXUS_DATABASE_URL` |

Use `build_stores()` so project and kernel stores share the same backend.

Authentication and multi-user tenancy are **not** implemented. Treat local
projects as prototype data only.

## Migrations

```bash
make dev-db
make db-migrate
```
