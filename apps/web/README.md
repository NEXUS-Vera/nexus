# Web Application

## Purpose

User-facing Vera UI for embedded project initialization and multi-turn
continuation of persisted projects.

## Ownership boundary

Deployable frontend only. Contract types are imported from `@nexus/contracts`
(generated from JSON Schemas).

## Routes

- `/` — create a new project
- `/projects/:projectId` — persisted workspace (refresh reloads from API)

## Local development

```bash
cp apps/web/.env.example apps/web/.env   # optional
make dev-web
```

The UI expects the API at `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`).

## Tests

```bash
pnpm --filter @nexus/web test
make test-e2e   # Playwright; starts API+web in fixture/memory mode
```
