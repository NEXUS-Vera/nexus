"""FastAPI application for the Nexus HTTP API."""

from __future__ import annotations

import logging
import uuid
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from nexus_embedded_systems.workflows.project_initialization import (
    InitializationRoutingError,
    InitializationService,
    InitializationValidationError,
    InMemoryInitializationStore,
    supported_family_examples,
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
_service = InitializationService(store=_store)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


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
        status = 422
        return JSONResponse(
            status_code=status,
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
