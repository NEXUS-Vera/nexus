"""FastAPI application for the Nexus HTTP API."""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from typing import Any, cast

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from nexus_board import build_project_kernel
from nexus_board.errors import BoardError
from nexus_board.ids import new_id
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
    build_stores,
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
    "component-plan",
}
COMMAND_ID_RE = re.compile(r"^cmd_[A-Za-z0-9]{16,}$")

app = FastAPI(title="Nexus API", version="0.1.0")

_store, _kernel_store = build_stores(
    backend=settings.storage_backend,
    database_url=settings.database_url,
)
_kernel = build_project_kernel(_kernel_store, project_store=_store)


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


#: The expected credential as bytes, encoded once at import.
EXPECTED_SESSION_TOKEN = settings.session_token.encode("utf-8")


def _presented_session_token(request: Request) -> bytes:
    """The presented bearer credential, as the raw bytes that arrived.

    Deliberately bytes rather than ``str``. Starlette decodes headers as
    latin-1, so any byte from 0x80 upwards becomes a non-ASCII character, and
    ``secrets.compare_digest`` refuses to compare non-ASCII ``str`` at all - it
    raises ``TypeError``, which inside the middleware becomes a 500 and a stack
    trace where the documented 401 belongs. Encoding back to bytes recovers
    exactly what the client sent and removes the failure mode rather than
    guarding against it.
    """
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer":
        return b""
    # Undoing Starlette's latin-1 decode is lossless for every byte a header can
    # carry; ``replace`` only covers a caller that hands us a str from elsewhere,
    # and yields bytes that cannot match a real token.
    return value.strip().encode("latin-1", "replace")


@app.middleware("http")
async def require_session_token(request: Request, call_next: Any) -> Any:
    """Reject every loopback request that does not carry the session token.

    The sidecar listens on loopback, which any local process and any web page
    the user visits can reach. The per-session bearer token, not the network
    boundary, is what makes the API safe to expose.

    No request is exempt. A browser's CORS preflight carries no credentials, but
    it never arrives here either: ``CORSMiddleware`` sits outside this one and
    answers a preflight itself, which is every ``OPTIONS`` request that carries
    both an ``Origin`` and an ``Access-Control-Request-Method``. Waving the
    remaining shape - preflight-looking, but with no ``Origin``, which no
    browser sends - past the token check would widen the unauthenticated
    surface for nothing.
    """
    presented = _presented_session_token(request)
    if not secrets.compare_digest(presented, EXPECTED_SESSION_TOKEN):
        return _error(
            401,
            code="SESSION_TOKEN_REQUIRED",
            message="A valid session token is required.",
            request_id=_request_id(request),
        )
    return await call_next(request)


# Registered last, and that is the whole point: Starlette inserts each new
# middleware at the front of the stack, so the most recently added one runs
# outermost. CORS has to be outside the token check, or the 401 above is
# returned without ``Access-Control-Allow-Origin`` and the browser blocks the
# response body - turning an authentication failure into an opaque network
# error the renderer cannot report or act on.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id", "Authorization"],
)


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
        logger.error(
            "initialization_provider_failed code=%s request_id=%s details=%s",
            exc.code,
            request_id,
            exc.details,
        )
        extra: dict[str, Any] | None = None
        if exc.details:
            extra = {"details": list(exc.details)[:40]}
        return _error(
            status,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            extra=extra,
        )
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
async def get_project_artifacts(project_id: str, request: Request) -> dict[str, Any] | JSONResponse:
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


@app.get("/v1/artifact-types", response_model=None)
async def list_artifact_types() -> dict[str, Any]:
    return {"schemaVersion": "1.0.0", "artifactTypes": _kernel.list_artifact_types()}


@app.get("/v1/projects/{project_id}/board", response_model=None)
async def get_project_board(project_id: str, request: Request) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        return _kernel.get_board(project_id)
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("board_retrieval_failed request_id=%s", request_id)
        return _error(
            500,
            code="PROJECT_RETRIEVAL_FAILED",
            message="Failed to retrieve project board.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/artifacts/{artifact_type}/workspace", response_model=None)
async def get_artifact_workspace(
    project_id: str,
    artifact_type: str,
    request: Request,
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
        _store.get_project(project_id)  # type: ignore[attr-defined]
        existing = _kernel.workspaces.get_or_none(project_id, artifact_type)
        if existing is None:
            return _error(
                404,
                code="WORKSPACE_NOT_FOUND",
                message="Workspace not found.",
                request_id=request_id,
            )
        return existing
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )


@app.post("/v1/projects/{project_id}/artifacts/{artifact_type}/workspace", response_model=None)
async def create_artifact_workspace(
    project_id: str,
    artifact_type: str,
    request: Request,
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
        body = {}
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        actor = body.get("requestedBy") or {
            "schemaVersion": "1.0.0",
            "actorId": new_id("actor"),
            "actorType": "user",
            "displayName": "User",
        }
        return _kernel.workspaces.create_if_missing(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            initial_content=body.get("initialContent"),
        )
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except BoardError as exc:
        return _error(422, code=exc.code, message=exc.message, request_id=request_id)
    except Exception:  # noqa: BLE001
        logger.exception("workspace_create_failed request_id=%s", request_id)
        return _error(
            500,
            code="WORKSPACE_CREATE_FAILED",
            message="Failed to create workspace.",
            request_id=request_id,
        )


@app.post("/v1/projects/{project_id}/artifact-commands", response_model=None)
async def dispatch_artifact_command(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        command = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(command, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Command must be an object.",
            request_id=request_id,
        )
    if command.get("projectId") and command["projectId"] != project_id:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="projectId mismatch.",
            request_id=request_id,
        )
    command = dict(command)
    command["projectId"] = project_id
    command_id = command.get("commandId")
    if not isinstance(command_id, str) or not COMMAND_ID_RE.match(command_id):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid commandId.",
            request_id=request_id,
        )
    if command.get("commandType") not in {
        "workspace.create",
        "workspace.update-draft",
        "workspace.create-snapshot",
        "workspace.restore-snapshot",
        "artifact.validate-draft",
        "artifact.propose-revision",
        "artifact.accept-revision",
        "artifact.reject-revision",
        "artifact.execute",
    }:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Unknown commandType.",
            request_id=request_id,
        )
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        result = _kernel.dispatch(command)
        if result.get("status") == "conflicted":
            code = (result.get("error") or {}).get("code") or "ARTIFACT_VERSION_CONFLICT"
            return _error(
                409,
                code=code,
                message=(result.get("error") or {}).get("message") or "Conflict.",
                request_id=request_id,
                extra={"commandResult": result},
            )
        if result.get("status") == "rejected":
            code = (result.get("error") or {}).get("code") or "GOVERNANCE_REJECTED"
            status = 403 if code in {"GOVERNANCE_REJECTED", "APPROVAL_REQUIRED"} else 422
            return _error(
                status,
                code=code,
                message=(result.get("error") or {}).get("message") or "Rejected.",
                request_id=request_id,
                extra={"commandResult": result},
            )
        return result
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except BoardError as exc:
        return _error(422, code=exc.code, message=exc.message, request_id=request_id)
    except Exception:  # noqa: BLE001
        logger.exception("artifact_command_failed request_id=%s", request_id)
        return _error(
            500,
            code="ARTIFACT_COMMAND_FAILED",
            message="Failed to dispatch artifact command.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/executions", response_model=None)
async def list_project_executions(
    project_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        items, next_cursor = _kernel.executions.list_runs(
            project_id, limit=limit, cursor=cursor
        )
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "items": items,
            "nextCursor": next_cursor,
        }
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/events", response_model=None)
async def list_project_events(
    project_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        items, next_cursor = _kernel.ledger.list_events(
            project_id, limit=limit, cursor=cursor
        )
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "items": items,
            "nextCursor": next_cursor,
        }
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/graph", response_model=None)
async def get_project_graph(
    project_id: str,
    request: Request,
    root: str | None = Query(default=None),
    direction: str = Query(default="both"),
    maxDepth: int = Query(default=5, ge=1, le=20, alias="maxDepth"),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    if direction not in {"outbound", "inbound", "both"}:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid direction.",
            request_id=request_id,
        )
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        if not root:
            nodes = _kernel_store.list_graph_nodes(project_id)
            if not nodes:
                return {
                    "schemaVersion": "1.0.0",
                    "projectId": project_id,
                    "rootNodeId": None,
                    "direction": direction,
                    "maxDepth": maxDepth,
                    "nodes": [],
                    "edges": [],
                    "truncated": False,
                    "cycleDetected": False,
                }
            root = nodes[0]["nodeId"]
        return _kernel.graph.reader.get_subgraph(
            project_id,
            root,
            direction=direction,  # type: ignore[arg-type]
            max_depth=maxDepth,
            max_nodes=100,
            max_edges=200,
        )
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except BoardError as exc:
        return _error(422, code=exc.code, message=exc.message, request_id=request_id)
