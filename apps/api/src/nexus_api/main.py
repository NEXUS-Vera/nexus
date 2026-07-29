"""FastAPI application for the Nexus HTTP API."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, cast

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from nexus_embedded_systems.workflows.project_initialization import (
    InitializationProviderError,
    InitializationRoutingError,
    InitializationService,
    InitializationValidationError,
    supported_family_examples,
)
from nexus_embedded_systems.workflows.project_initialization.providers import (
    build_initialization_provider,
)
from nexus_embedded_systems.workflows.project_modification import (
    ModificationError,
    ModificationService,
)
from nexus_persistence import (
    ArtifactNotFoundError,
    ArtifactVersionNotFoundError,
    ProjectNotFoundError,
    ProjectPersistenceError,
    ProjectRetrievalError,
    build_project_store,
)
from project_initialization_result_v1 import ProjectInitializationResultV1

from .config import settings
from .models import InitializeProjectRequest, ProjectTurnRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("nexus.api")

PROJECT_ID_RE = re.compile(r"^proj_[A-Za-z0-9]{16,}$")
ARTIFACT_TYPES = {
    "project-brief",
    "requirement-set",
    "functional-architecture",
    "next-action",
}

app = FastAPI(title="Nexus API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
)

_store = build_project_store(
    backend=settings.storage_backend,
    database_url=settings.database_url,
)


def _build_init_service() -> InitializationService:
    mode = settings.initialization_provider
    provider = build_initialization_provider(mode)  # type: ignore[arg-type]
    return InitializationService(store=_store, provider=provider)


_init_service = _build_init_service()
_mod_service = ModificationService(store=_store, mode=settings.initialization_provider)


def _error(
    status: int,
    *,
    code: str,
    message: str,
    request_id: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id,
        }
    }
    if extra:
        body["error"].update(extra)
    return JSONResponse(status_code=status, content=body)


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def _validate_project_id(project_id: str, request_id: str) -> JSONResponse | None:
    if not PROJECT_ID_RE.match(project_id):
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    return None


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "initializationProvider": settings.initialization_provider,
        "storageBackend": settings.storage_backend,
    }


@app.post("/v1/projects/initialize", response_model=None)
async def initialize_project(
    body: InitializeProjectRequest, request: Request
) -> ProjectInitializationResultV1 | JSONResponse:
    request_id = _request_id(request)
    try:
        result = await _init_service.initialize_embedded_project(
            message=body.message.strip(),
            autonomy_mode=body.autonomyMode,
            request_id=request_id,
        )
        return cast(ProjectInitializationResultV1, result)
    except InitializationRoutingError as exc:
        return _error(
            422,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            extra={
                "supportedFamilies": supported_family_examples(),
                "matchedFamilies": list(exc.matched_families),
            },
        )
    except InitializationProviderError as exc:
        status = 422 if exc.code == "UNSUPPORTED_EMBEDDED_PROJECT_INITIALIZATION" else 500
        if exc.code in {
            "MODEL_PROVIDER_UNAVAILABLE",
            "MODEL_CONFIGURATION_MISSING",
        }:
            status = 503
        logger.error("initialization_provider_failed code=%s request_id=%s", exc.code, request_id)
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)
    except InitializationValidationError as exc:
        logger.error(
            "initialization_validation_failed codes=%s request_id=%s",
            exc.codes,
            request_id,
        )
        return _error(
            500,
            code="INITIALIZATION_PACKAGE_VALIDATION_FAILED",
            message="Project initialization failed validation. No package was returned.",
            request_id=request_id,
        )
    except ProjectPersistenceError as exc:
        return _error(
            500,
            code=exc.code,
            message="Failed to persist the initialized project.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}", response_model=None)
async def get_project(project_id: str, request: Request) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return _store.get_current_state(project_id)
    except ProjectNotFoundError as exc:
        return _error(404, code=exc.code, message="Project not found.", request_id=request_id)
    except Exception:  # noqa: BLE001
        logger.exception("project_retrieval_failed request_id=%s", request_id)
        return _error(
            500,
            code="PROJECT_RETRIEVAL_FAILED",
            message="Failed to retrieve the project.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/artifacts", response_model=None)
async def get_project_artifacts(
    project_id: str, request: Request
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return {"schemaVersion": "1.0.0", "artifacts": _store.get_artifacts(project_id)}
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except Exception:  # noqa: BLE001
        return _error(
            500,
            code="PROJECT_RETRIEVAL_FAILED",
            message="Failed to retrieve project artifacts.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/artifacts/{artifact_type}", response_model=None)
async def get_project_artifact(
    project_id: str,
    artifact_type: str,
    request: Request,
    version: int | None = Query(default=None, ge=1),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    if artifact_type not in ARTIFACT_TYPES:
        return _error(
            404,
            code="ARTIFACT_NOT_FOUND",
            message="Artifact type not found.",
            request_id=request_id,
        )
    try:
        return _store.get_artifact(project_id, artifact_type, version=version)
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except ArtifactVersionNotFoundError as exc:
        return _error(404, code=exc.code, message=exc.message, request_id=request_id)
    except ArtifactNotFoundError as exc:
        return _error(404, code=exc.code, message=exc.message, request_id=request_id)
    except Exception:  # noqa: BLE001
        return _error(
            500,
            code="PROJECT_RETRIEVAL_FAILED",
            message="Failed to retrieve the artifact.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/history", response_model=None)
async def get_project_history(
    project_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return _store.get_history(project_id, limit=limit)
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except Exception:  # noqa: BLE001
        return _error(
            500,
            code="PROJECT_RETRIEVAL_FAILED",
            message="Failed to retrieve project history.",
            request_id=request_id,
        )


@app.post("/v1/projects/{project_id}/turns", response_model=None)
async def submit_project_turn(
    project_id: str,
    body: ProjectTurnRequest,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return await _mod_service.submit_turn(
            project_id,
            body.message.strip(),
            autonomy_mode=body.autonomyMode,
            request_id=request_id,
        )
    except ModificationError as exc:
        status = 422
        if exc.code in {
            "PROJECT_NOT_FOUND",
            "OPEN_QUESTION_NOT_FOUND",
            "REQUIREMENT_NOT_FOUND",
        }:
            status = 404
        if exc.code in {
            "PROJECT_CHANGE_VALIDATION_FAILED",
            "PROJECT_CHANGE_PERSISTENCE_FAILED",
            "PROJECT_RETRIEVAL_FAILED",
        }:
            status = 500
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)
    except ProjectRetrievalError as exc:
        return _error(500, code=exc.code, message=exc.message, request_id=request_id)
