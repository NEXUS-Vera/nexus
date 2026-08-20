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
| `NEXUS_API_SESSION_TOKEN` | `nexus-dev-session-token` | Per-session bearer token; the desktop shell mints a fresh one per launch |

## Session-token authentication

The API is designed to run as a loopback sidecar of the desktop shell. Loopback
is not a security boundary: any local process, and any web page the user
visits, can reach it. Every request must therefore carry the session token:

```text
Authorization: Bearer <NEXUS_API_SESSION_TOKEN>
```

No route is exempt, including `GET /healthz`. Requests without a valid token
receive `401` with error code `SESSION_TOKEN_REQUIRED`.

The spawning process supplies `NEXUS_API_SESSION_TOKEN` in the environment so
the token is never written to disk. When the variable is unset the API falls
back to the well-known development token `nexus-dev-session-token`, which keeps
`make dev-api` and `make dev-web` working. Never run a packaged build without
setting a real token.

Multi-user tenancy is **not** implemented.

## Sidecar mode and the stdout handshake

The API is spawned as a loopback child process by the desktop shell:

```bash
NEXUS_API_PORT=0 NEXUS_API_SESSION_TOKEN=<token> python -m nexus_api
```

`NEXUS_API_PORT=0` asks the operating system for a free port, which avoids
colliding with the user's own tooling and with other users on a shared machine.
The sidecar binds and listens first, then writes **exactly one line** to stdout:

```json
{"event":"nexus.api.listening","schemaVersion":"1.0.0","host":"127.0.0.1","port":54321,"pid":4242}
```

This line is a contract consumed by the shell's sidecar supervisor. stdout
carries nothing else; all logging goes to stderr. The socket is already
listening when the line is written, so a connection made immediately on reading
it is accepted rather than refused.

The sidecar also watches the process that spawned it and shuts itself down when
that process disappears. Without this, force-quitting the shell leaves an
orphaned Python process holding the database file and the next launch fails
with no visible cause.

## Local development

```bash
make dev-db          # optional postgres
make db-migrate
make dev-api
```
