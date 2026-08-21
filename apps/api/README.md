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
| `NEXUS_STORAGE_BACKEND` | `memory` | `memory`, `sqlite`, or `postgres`. The packaged desktop shell always runs `sqlite` |
| `NEXUS_DATABASE_URL` | local postgres URL | Used by both `sqlite` and `postgres`. For SQLite it is `sqlite:///<absolute-path>` - note the four slashes an absolute path produces |
| `NEXUS_INITIALIZATION_PROVIDER` | `fixture` | `fixture`, `llm`, or `shadow` |
| `NEXUS_API_CORS_ORIGINS` | conditional, see below | Explicit allowlist of browser origins; overrides the default either way |
| `NEXUS_API_SESSION_TOKEN` | `nexus-dev-session-token` | Per-session bearer token; the desktop shell mints a fresh one per launch |

The desktop shell points `NEXUS_DATABASE_URL` at `nexus.sqlite3` under Electron's
per-user application data directory, so a student's projects survive a quit.
Alembic is the sole schema authority for that file as it is for Postgres: the
store runs migrations to head when it opens the database.

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

CORS is not the security boundary here; the session token is. A cross-origin
page cannot obtain a token it does not know, and an origin allowlist stops no
local process that is not a browser. A packaged renderer loads over `file://`
and sends `Origin: null`, which no useful allowlist contains - so when the token
is a real per-launch secret the default is unrestricted, which is what makes the
shipped shell work at all.

That argument holds only while the token is secret. With `NEXUS_API_SESSION_TOKEN`
unset the token is `nexus-dev-session-token`, a constant published in this
repository and baked into the built web bundle, so any page the user visits
could present it. The default therefore depends on the token:

| `NEXUS_API_SESSION_TOKEN` | Default allowed origins |
| --- | --- |
| set to a real secret | any origin |
| unset (development token) | `http://localhost:5173` and `http://127.0.0.1:5173` |

Those two are the Vite dev server, which is the browser `make dev-api` and
`make dev-web` are for. **Serving the web app from any other port** - a
`vite --port 3000`, a preview server, a Storybook - **needs
`NEXUS_API_CORS_ORIGINS` set to that origin**, or the browser blocks the
response with no `Access-Control-Allow-Origin`. Setting the variable is an
explicit override and replaces the default in both cases.

No request reaches the router without a valid token, preflights included -
because a browser's preflight never reaches the token check in the first place.
`CORSMiddleware` is registered outside it and answers any `OPTIONS` carrying
both an `Origin` and an `Access-Control-Request-Method` itself, which is exactly
what a browser sends and nothing else does. Every other response, a `401`
included, passes back out through that same layer, so a browser can read why it
was rejected instead of seeing an opaque network error.

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
