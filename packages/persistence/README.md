# Persistence

## Purpose

Shared project-package persistence for Nexus: repository interfaces, an
in-memory adapter, and a SQLAlchemy adapter that serves both SQLite (the
packaged desktop shell) and PostgreSQL.

## Ownership boundary

Applications and domain agents depend on the `ProjectPackageStore` protocol.
SQL and ORM details stay inside this package.

## What belongs here

- Store protocol and errors
- In-memory and SQL implementations (SQLite and PostgreSQL share one adapter)
- Alembic migrations for the project-package schema, shipped inside the
  installed package at `src/nexus_persistence/alembic/`
- Behavioral contract tests for every backend

## What must not be placed here

- HTTP routes
- Agent prompts or modification interpretation
- UI code
- Secrets

## Artifact revision identity

- Each physical revision gets a new `artifactId`
- `artifactVersion` is monotonic per `(projectId, artifactType)`
- New revisions set `supersedesArtifactId` / `supersedesArtifactVersion`
- `project.currentArtifactReferences` point at current heads
- Uniqueness: `(project_id, artifact_type, artifact_version)` and unique `artifact_id`

## Storage backends

| Backend | Env |
| --- | --- |
| `memory` (default for tests) | `NEXUS_STORAGE_BACKEND=memory` |
| `sqlite` (packaged desktop shell) | `NEXUS_STORAGE_BACKEND=sqlite` and `NEXUS_DATABASE_URL=sqlite:///<absolute-path>` |
| `postgres` (local demo) | `NEXUS_STORAGE_BACKEND=postgres` and `NEXUS_DATABASE_URL` |

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
