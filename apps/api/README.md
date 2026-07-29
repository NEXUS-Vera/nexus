# API Application

## Purpose

Public HTTP API for Nexus. Exposes embedded project initialization and
multi-turn modification with optional PostgreSQL persistence.

## Ownership boundary

Deployable API application only. Domain workflow logic lives in
`agents/embedded-systems`. Persistence adapters live in `packages/persistence`.

## Endpoints

- `GET /healthz`
- `POST /v1/projects/initialize`
- `GET /v1/projects/{projectId}`
- `GET /v1/projects/{projectId}/artifacts`
- `GET /v1/projects/{projectId}/artifacts/{artifactType}?version=`
- `GET /v1/projects/{projectId}/history`
- `POST /v1/projects/{projectId}/turns`

Successful initialize responses return `ProjectInitializationResult`.
Successful turn responses return `ProjectTurnResult` (includes current state and
impact analysis).

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXUS_STORAGE_BACKEND` | `memory` | `memory` or `postgres` |
| `NEXUS_DATABASE_URL` | local postgres URL | Used when backend is `postgres` |
| `NEXUS_INITIALIZATION_PROVIDER` | `fixture` | `fixture`, `llm`, or `shadow` |

Authentication and multi-user tenancy are **not** implemented.

## Local development

```bash
make dev-db          # optional postgres
make db-migrate
make dev-api
```
