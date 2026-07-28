# API Application

## Purpose

Public HTTP API for Nexus. Exposes embedded project initialization backed by
the `fixture`, `llm`, or `shadow` provider (see
`agents/embedded-systems/README.md`).

## Ownership boundary

Deployable API application only. Domain workflow logic lives in `agents/embedded-systems`.

## Endpoints

- `GET /healthz`
- `POST /v1/projects/initialize`

Request body:

```json
{
  "message": "I want to build a wrist-worn device that measures hand tremors...",
  "autonomyMode": "collaborate"
}
```

Successful responses return the canonical `ProjectInitializationResult` contract.

Unsupported or ambiguous prompts return HTTP 422 with a stable error code.

The active provider is controlled by `NEXUS_INITIALIZATION_PROVIDER`
(`fixture` default, `llm`, or `shadow`); `llm`/`shadow` also read
`NEXUS_MODEL_PROVIDER`, `NEXUS_MODEL_NAME`, `NEXUS_MODEL_API_KEY`,
`NEXUS_MODEL_TIMEOUT_SECONDS`, and `NEXUS_MODEL_MAX_REPAIR_ATTEMPTS` (see
`.env.example`). Nothing is persisted beyond the process lifetime.

## Local development

```bash
make dev-api
# or
PYTHONPATH=apps/api/src:agents/embedded-systems/src:packages/contracts/src:packages/model-gateway/src:packages/observability/src \
  python3 -m uvicorn nexus_api.main:app --reload --host 127.0.0.1 --port 8000
```

CORS origins default to `http://localhost:5173` and can be overridden with `NEXUS_API_CORS_ORIGINS`.
