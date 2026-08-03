# Persistence

## Purpose

Shared project-package persistence for Nexus: repository interfaces and
in-memory / PostgreSQL adapters.

## Ownership boundary

Applications and domain agents depend on the `ProjectPackageStore` protocol.
SQL and ORM details stay inside this package.

## What belongs here

- Store protocol and errors
- In-memory and PostgreSQL implementations
- Alembic migrations for the project-package schema
- Behavioral contract tests for both backends

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
| `postgres` (local demo) | `NEXUS_STORAGE_BACKEND=postgres` and `NEXUS_DATABASE_URL` |

Authentication and multi-user tenancy are **not** implemented. Treat local
projects as prototype data only.

## Migrations

```bash
make dev-db
make db-migrate
```
