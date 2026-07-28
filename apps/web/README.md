# Web Application

## Purpose

User-facing Vera prototype for embedded project initialization (Phase 6).

## Ownership boundary

Deployable frontend only. Contract types are imported from `@nexus/contracts` (generated from JSON Schemas).

## Local development

```bash
cp apps/web/.env.example apps/web/.env   # optional
make dev-web
# or
pnpm --filter @nexus/web dev
```

The UI expects the API at `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`).

## Tests

```bash
pnpm --filter @nexus/web test
```
