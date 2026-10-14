# Persistence

## Purpose

Shared project-package and Phase 11 workspace-kernel persistence for Nexus:
repository interfaces, in-memory adapters, and a SQLAlchemy adapter that serves
both SQLite (the packaged desktop shell) and PostgreSQL.

## Ownership boundary

Applications and domain agents depend on the `ProjectPackageStore` and
`ProjectKernelStore` protocols. SQL and ORM details stay inside this package.

## What belongs here

- Store protocols and errors
- In-memory and SQL implementations (`InMemoryProjectStore`,
  `InMemoryKernelStore`, SQL project store for SQLite/PostgreSQL,
  `PostgresKernelStore`)
- Alembic migrations for project packages and the workspace kernel, shipped
  inside the installed package at `src/nexus_persistence/alembic/`
- Behavioral contract tests for every backend

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

Phase 14A adds `workspace_files` (mutable filesystem index metadata) in
migration `0003_phase14a_workspace_files`. File bytes live in a replaceable
content-addressed `FileStore` (`InMemoryFileStore` / `LocalFileStore`), not in
JSONB rows.

Phase 14B adds `execution_jobs` and `execution_log_chunks` in migration
`0004_phase14b_execution_jobs`. Jobs are infrastructure-only; the product
record remains `execution_runs`.

Phase 14C adds reference-aware GC helpers on the kernel store
(`list_referenced_content_hashes` includes ProducedOutput file-store URIs,
`reclaim_snapshot`, `delete_execution_log_chunks`, and global list helpers).
No new migration is required for 14C retention metadata.

Phase 15C adds `firmware_patch_proposals` in migration
`0005_phase15c_firmware_patches`. Firmware patch create/get/update operations
share the same persistence protocol across memory, SQLite and PostgreSQL.

`accept_proposal_transaction` atomically validates concurrency, inserts a new
artifact revision, advances `currentStateVersion`, appends events, updates
graph edges, and upserts the board projection.

## Storage backends

| Backend | Env |
| --- | --- |
| `memory` (default for tests) | `NEXUS_STORAGE_BACKEND=memory` |
| `sqlite` (packaged desktop shell) | `NEXUS_STORAGE_BACKEND=sqlite` and `NEXUS_DATABASE_URL=sqlite:///<absolute-path>` |
| `postgres` (local demo) | `NEXUS_STORAGE_BACKEND=postgres` and `NEXUS_DATABASE_URL` |

Use `build_stores()` so project and kernel stores share the same backend.

Request authentication belongs to the API, not to this package; see
[`apps/api/README.md`](../../apps/api/README.md). Multi-user tenancy is **not**
implemented, so treat local projects as prototype data only.

## Migrations

Alembic is the only schema authority for both SQL backends, so a database it
created carries a version stamp and a later release can upgrade it in place.

For local Postgres, run the migrations explicitly:

```bash
make dev-db
make db-migrate
```

The `sqlite` backend has no such step: `build_project_store` upgrades the file
to head when it opens it, because the process that opens an embedded database
file is the only one that can create its schema.
