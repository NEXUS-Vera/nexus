"""FastAPI application for the Nexus HTTP API."""

from __future__ import annotations

import logging
import uuid
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from nexus_embedded_systems.workflows.project_initialization import (
    InitializationProviderError,
    InitializationRoutingError,
    InitializationService,
    InitializationValidationError,
    InMemoryInitializationStore,
    supported_family_examples,
)
from nexus_embedded_systems.workflows.project_initialization.providers import (
    build_initialization_provider,
)
from project_initialization_result_v1 import ProjectInitializationResultV1

from .config import settings
from .models import InitializeProjectRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("nexus.api")

app = FastAPI(title="Nexus API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
)

_store = InMemoryInitializationStore()


def _build_service() -> InitializationService:
    mode = settings.initialization_provider
    provider = build_initialization_provider(mode)  # type: ignore[arg-type]
    return InitializationService(store=_store, provider=provider)


_service = _build_service()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "initializationProvider": settings.initialization_provider,
    }


@app.post("/v1/projects/initialize", response_model=None)
async def initialize_project(
    body: InitializeProjectRequest, request: Request
) -> ProjectInitializationResultV1 | JSONResponse:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    try:
        result = await _service.initialize_embedded_project(
            message=body.message.strip(),
            autonomy_mode=body.autonomyMode,
            request_id=request_id,
        )
        return cast(ProjectInitializationResultV1, result)
    except InitializationRoutingError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "requestId": request_id,
                    "supportedFamilies": supported_family_examples(),
                    "matchedFamilies": list(exc.matched_families),
                }
            },
        )
    except InitializationProviderError as exc:
        status = 422 if exc.code == "UNSUPPORTED_EMBEDDED_PROJECT_INITIALIZATION" else 500
        if exc.code in {
            "MODEL_PROVIDER_UNAVAILABLE",
            "MODEL_CONFIGURATION_MISSING",
        }:
            status = 503
        logger.error(
            "initialization_provider_failed code=%s request_id=%s",
            exc.code,
            request_id,
        )
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "requestId": request_id,
                }
            },
        )
    except InitializationValidationError as exc:
        logger.error(
            "initialization_validation_failed codes=%s request_id=%s",
            exc.codes,
            request_id,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INITIALIZATION_PACKAGE_VALIDATION_FAILED",
                    "message": "Project initialization failed validation. No package was returned.",
                    "requestId": request_id,
                }
            },
        )
