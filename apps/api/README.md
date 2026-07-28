# API Application

## Purpose

Public HTTP API for Nexus. Phase 5 exposes fixture-backed embedded project initialization.

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

Unsupported or ambiguous fixture-phase prompts return HTTP 422 with a stable error code.

## Local development

```bash
make dev-api
# or
PYTHONPATH=apps/api/src:agents/embedded-systems/src:packages/contracts/src \
  python3 -m uvicorn nexus_api.main:app --reload --host 127.0.0.1 --port 8000
```

CORS origins default to `http://localhost:5173` and can be overridden with `NEXUS_API_CORS_ORIGINS`.
