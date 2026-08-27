# API Application

## Purpose

Public HTTP API for Nexus. Exposes embedded project initialization and
multi-turn modification with optional PostgreSQL persistence.

## Ownership boundary

Deployable API application only. Domain workflow logic lives in
`agents/embedded-systems`. Persistence adapters live in `packages/persistence`.

## Endpoints

- `GET /healthz`
- `GET /v1/runtime/health`
- `POST /v1/admin/retention/gc?dry_run=`
- `POST /v1/projects/initialize`
- `GET /v1/projects/{projectId}`
- `GET /v1/projects/{projectId}/artifacts`
- `GET /v1/projects/{projectId}/artifacts/{artifactType}?version=`
- `GET /v1/projects/{projectId}/history`
- `POST /v1/projects/{projectId}/turns`
- `GET /v1/artifact-types`
- `GET /v1/projects/{projectId}/board`
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace`
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace`
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/runtime`
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/files`
- `GET|PUT|DELETE /v1/projects/{projectId}/artifacts/{artifactType}/workspace/file`
- `GET|POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/snapshots`
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/snapshots/{snapshotId}/restore`
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/executions`
- `POST /v1/projects/{projectId}/artifacts/firmware/workspace/scaffold`
- `POST /v1/projects/{projectId}/artifact-commands`
- `GET /v1/projects/{projectId}/executions?limit=&cursor=`
- `GET /v1/projects/{projectId}/events?limit=&cursor=`
- `GET /v1/projects/{projectId}/graph?root=&direction=&maxDepth=`

Successful initialize responses return `ProjectInitializationResult`.
Successful turn responses return `ProjectTurnResult` (includes current state and
impact analysis). Artifact commands return `ArtifactCommandResult` (or a
structured conflict/governance error envelope).

Phase 12 initialize packages include five artifact types, including
`component-plan`. Board summaries expose Component Plan maturity/coverage
counts. Fixture-mode turns support component-plan operations (approve/reject
candidates, constraints, alternatives) in addition to requirement edits.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXUS_STORAGE_BACKEND` | `memory` | `memory` or `postgres` |
| `NEXUS_DATABASE_URL` | local postgres URL | Used when backend is `postgres` |
| `NEXUS_INITIALIZATION_PROVIDER` | `fixture` | `fixture`, `llm`, or `shadow` |
| `NEXUS_EXECUTION_RUNTIME` | `process` | `process` or `container` (no silent fallback) |
| `NEXUS_EXEC_CONTAINER_IMAGE` | `python:3.13-slim` | Used when runtime is `container` |

Authentication and multi-user tenancy are **not** implemented.

## Local development

```bash
make dev-db          # optional postgres
make db-migrate
make dev-api
```
