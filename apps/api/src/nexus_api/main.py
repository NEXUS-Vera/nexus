"""FastAPI application for the Nexus HTTP API."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from nexus_board import build_project_kernel
from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
from nexus_board.errors import BoardError
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.runtime_factory import build_execution_runtime
from nexus_board.execution.scheduler import SchedulerConfig
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_board.ids import new_id
from nexus_board.registries.external_providers import default_external_provider_registry
from nexus_board.registries.runtime_capabilities import default_runtime_capability_registry
from nexus_board.services.architecture_graph import materialize_layered_architecture_graph
from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits
from nexus_board.services.retention import RetentionPolicy
from nexus_circuit_simulation import CircuitSimulationError, WokwiProvider
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
from nexus_model_gateway import AnthropicGateway, ModelPolicy, OpenAICompatibleGateway
from nexus_persistence import (
    ArtifactNotFoundError,
    ArtifactVersionNotFoundError,
    ExecutionNotFoundError,
    InMemoryFileStore,
    LocalFileStore,
    ProjectNotFoundError,
    ProjectPersistenceError,
    ProjectRetrievalError,
    WorkspaceNotFoundError,
    build_stores,
)
from project_initialization_result_v1 import ProjectInitializationResultV1

from .circuit_simulation import (
    CircuitSimulationExecutionAdapter,
    materialization_request,
    serialize_availability,
    serialize_provider_preview,
    serialize_support_assessment,
    serialize_validation,
)
from .config import settings
from .models import InitializeProjectRequest, ProjectTurnRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("nexus.api")

PROJECT_ID_RE = re.compile(r"^proj_[A-Za-z0-9]{16,}$")
ARTIFACT_TYPES = {
    "analysis",
    "test-plan",
    "risk-register",
    "project-brief",
    "requirement-set",
    "functional-architecture",
    "next-action",
    "component-plan",
    "code-scratch",
    "firmware",
    "electrical-architecture",
    "physical-architecture",
}
COMMAND_ID_RE = re.compile(r"^cmd_[A-Za-z0-9]{16,}$")

app = FastAPI(title="Nexus API", version="0.1.0")

_store, _kernel_store = build_stores(
    backend=settings.storage_backend,
    database_url=settings.database_url,
)
_wokwi_provider = WokwiProvider(
    token=settings.wokwi_cli_token or None,
    executable=settings.wokwi_cli_executable,
    firmware_elf_path=settings.wokwi_firmware_elf or None,
)
_wokwi_availability = _wokwi_provider.availability()
_firmware_ready = bool(
    settings.wokwi_firmware_elf
    and Path(settings.wokwi_firmware_elf).is_file()
    and Path(settings.wokwi_firmware_elf).suffix.lower() == ".elf"
)
_capabilities = default_runtime_capability_registry()
_capabilities.register(
    {
        "schemaVersion": "1.0.0",
        "capabilityId": "circuit-simulation",
        "displayName": "Circuit Simulation",
        "providerId": "wokwi",
        "available": _wokwi_availability.ready,
        "description": "Provider-neutral circuit simulation through Wokwi CLI",
    }
)
_providers = default_external_provider_registry()
_providers.register(
    {
        "providerId": "wokwi",
        "displayName": "Wokwi",
        "available": _wokwi_availability.ready,
        "capabilities": ["circuit-simulation"],
    }
)
_file_store = (
    LocalFileStore(settings.file_store_root) if settings.file_store_root else InMemoryFileStore()
)


def _build_firmware_patch_generator() -> LiveFirmwarePatchGenerator | None:
    mode = settings.initialization_provider
    if mode not in {"llm", "shadow"}:
        return None
    credential = settings.model_credential.strip()
    if not credential:
        return None
    provider = settings.model_provider.strip().lower()
    gateway: Any
    if provider in {"anthropic", "claude"}:
        gateway = AnthropicGateway(
            model_credential=credential,
            base_url=settings.model_base_url,
        )
    else:
        gateway = OpenAICompatibleGateway(
            model_credential=credential,
            base_url=settings.model_base_url,
        )
    policy = ModelPolicy(
        provider=provider,
        model=settings.model_name,
        timeout_seconds=settings.model_timeout_seconds,
    )
    return LiveFirmwarePatchGenerator(gateway=gateway, model_policy=policy)


def _build_analysis_patch_generator() -> LiveAnalysisPatchGenerator | None:
    """Reuse the same Nexus model gateway config as firmware (Phase 16G)."""
    mode = settings.initialization_provider
    if mode not in {"llm", "shadow"}:
        return None
    credential = settings.model_credential.strip()
    if not credential:
        return None
    provider = settings.model_provider.strip().lower()
    gateway: Any
    if provider in {"anthropic", "claude"}:
        gateway = AnthropicGateway(
            model_credential=credential,
            base_url=settings.model_base_url,
        )
    else:
        gateway = OpenAICompatibleGateway(
            model_credential=credential,
            base_url=settings.model_base_url,
        )
    policy = ModelPolicy(
        provider=provider,
        model=settings.model_name,
        timeout_seconds=settings.model_timeout_seconds,
    )
    return LiveAnalysisPatchGenerator(gateway=gateway, model_policy=policy)


_analysis_patch_generator = _build_analysis_patch_generator()
_firmware_patch_generator = _build_firmware_patch_generator()

_kernel = build_project_kernel(
    _kernel_store,
    project_store=_store,
    capabilities=_capabilities,
    providers=_providers,
    capability_executors={
        "circuit-simulation": CircuitSimulationExecutionAdapter(
            provider=_wokwi_provider,
            project_store=_store,
            firmware_ready=_firmware_ready,
        )
    },
    file_store=_file_store,
    filesystem_limits=WorkspaceFilesystemLimits(
        max_file_bytes=settings.workspace_max_file_bytes,
        max_workspace_bytes=settings.workspace_max_bytes,
        max_file_count=settings.workspace_max_file_count,
    ),
    execution_limits=ExecutionLimits(
        wall_time_ms=settings.execution_wall_time_ms,
        stdout_bytes=settings.execution_stdout_bytes,
        stderr_bytes=settings.execution_stderr_bytes,
        total_log_bytes=settings.execution_total_log_bytes,
        produced_output_bytes=settings.execution_produced_output_bytes,
        memory_bytes=settings.execution_memory_bytes,
        cpu_millis=settings.execution_cpu_millis,
        process_count=settings.execution_process_count,
    ),
    scheduler_config=SchedulerConfig(
        max_running_global=settings.execution_max_running_global,
        max_running_per_project=settings.execution_max_running_per_project,
        max_queued=settings.execution_max_queued,
    ),
    execution_runtime=build_execution_runtime(
        settings.execution_runtime,
        container_image=settings.execution_container_image,
    ),
    retention_policy=RetentionPolicy.from_environ(),
    firmware_patch_generator=_firmware_patch_generator,
    analysis_patch_generator=_analysis_patch_generator,
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
        try:
            project_id = result["project"]["projectId"]
            materialize_layered_architecture_graph(
                _kernel_store,
                project_id,
                list(result.get("artifacts") or []),
                new_id("evt"),
            )
            _kernel.projection.update_after_write(project_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "initialization_graph_materialization_failed request_id=%s",
                request_id,
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
        return cast(dict[str, Any], _store.get_current_state(project_id))
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


@app.post("/v1/projects/{project_id}/ensure-layered-architecture", response_model=None)
async def ensure_layered_architecture(
    project_id: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Idempotently materialize Electrical/Physical for pre-Phase-13 projects."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        from nexus_embedded_systems.workflows.layered_architecture import (
            ensure_layered_architecture_artifacts,
        )

        project = _store.get_project(project_id)  # type: ignore[attr-defined]
        artifacts = _store.get_artifacts(project_id)
        body: dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        actor = body.get("requestedBy") or {
            "schemaVersion": "1.0.0",
            "actorId": new_id("actor"),
            "actorType": "system",
            "displayName": "System",
        }
        ensured = ensure_layered_architecture_artifacts(
            project_id=project_id,
            artifacts=list(artifacts),
            actor=actor,
        )
        if ensured.get("skippedReason"):
            return _error(
                422,
                code="LAYERED_ARCHITECTURE_ENSURE_BLOCKED",
                message=str(ensured["skippedReason"]),
                request_id=request_id,
            )
        created = list(ensured.get("created") or [])
        now = created[0]["createdAt"] if created else None
        state_version = int(project["currentStateVersion"])
        for art in created:
            state_version += 1
            stamp = str(art.get("updatedAt") or art.get("createdAt") or now)
            _store.apply_accepted_artifact_revision(  # type: ignore[attr-defined]
                project_id=project_id,
                new_artifact=art,
                next_state_version=state_version,
                updated_at=stamp,
                expected_project_state_version=state_version - 1,
            )
        if created:
            try:
                materialize_layered_architecture_graph(
                    _kernel_store,
                    project_id,
                    list(ensured.get("artifacts") or artifacts),
                    new_id("evt"),
                )
                _kernel.projection.update_after_write(project_id)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "ensure_layered_graph_materialization_failed request_id=%s",
                    request_id,
                )
        current = _store.get_current_state(project_id)
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "createdArtifactTypes": [a["artifactType"] for a in created],
            "currentState": current,
        }
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("ensure_layered_architecture_failed request_id=%s", request_id)
        return _error(
            500,
            code="LAYERED_ARCHITECTURE_ENSURE_FAILED",
            message="Failed to ensure layered architecture artifacts.",
            request_id=request_id,
        )


def _circuit_materialization(project_id: str) -> tuple[dict[str, Any], Any]:
    electrical = _store.get_artifact(project_id, "electrical-architecture")
    component_plan = _store.get_artifact(project_id, "component-plan")
    return electrical, materialization_request(
        electrical_artifact=electrical,
        component_plan_artifact=component_plan,
    )


@app.get(
    "/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/support",
    response_model=None,
)
async def get_circuit_simulation_support(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        electrical, materialization = _circuit_materialization(project_id)
        assessment = _wokwi_provider.assess_support(materialization)
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "artifactId": electrical["artifactId"],
            "providerAvailability": serialize_availability(
                _wokwi_provider, firmware_ready=_firmware_ready
            ),
            "assessment": serialize_support_assessment(
                assessment,
                firmware_ready=_firmware_ready,
                provider_id="wokwi",
            ),
        }
    except (ProjectNotFoundError, ArtifactNotFoundError):
        return _error(
            404,
            code="SIMULATION_INPUT_NOT_FOUND",
            message="Electrical Architecture or Component Plan was not found.",
            request_id=request_id,
        )


@app.get(
    "/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/preview",
    response_model=None,
)
async def get_circuit_simulation_preview(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _, materialization = _circuit_materialization(project_id)
        assessment = _wokwi_provider.assess_support(materialization)
        workspace = _wokwi_provider.materialize(materialization)
        return serialize_provider_preview(
            assessment=assessment,
            workspace=workspace,
            provider_id="wokwi",
        )
    except (ProjectNotFoundError, ArtifactNotFoundError):
        return _error(
            404,
            code="SIMULATION_INPUT_NOT_FOUND",
            message="Electrical Architecture or Component Plan was not found.",
            request_id=request_id,
        )
    except CircuitSimulationError as exc:
        return _error(
            503,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )


@app.post(
    "/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/validate",
    response_model=None,
)
def validate_circuit_simulation(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _, materialization = _circuit_materialization(project_id)
        workspace = _wokwi_provider.materialize(materialization)
        result = _wokwi_provider.validate(workspace)
        return serialize_validation(result, workspace)
    except (ProjectNotFoundError, ArtifactNotFoundError):
        return _error(
            404,
            code="SIMULATION_INPUT_NOT_FOUND",
            message="Electrical Architecture or Component Plan was not found.",
            request_id=request_id,
        )
    except CircuitSimulationError as exc:
        return _error(
            503,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )


@app.get(
    "/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/export",
    response_model=None,
)
async def export_circuit_simulation_workspace(
    project_id: str,
    request: Request,
) -> JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        electrical = _store.get_artifact(project_id, "electrical-architecture")
        persisted = next(
            (
                output
                for output in reversed(_kernel.executions.list_outputs(project_id))
                if output.get("artifactId") == electrical["artifactId"]
                and output.get("name") == "provider-workspace-manifest"
            ),
            None,
        )
        if persisted is None:
            return _error(
                404,
                code="SIMULATION_EXPORT_NOT_FOUND",
                message="Run a simulation with provider workspace output before exporting.",
                request_id=request_id,
            )
        structured = (persisted.get("content") or {}).get("structuredResult") or {}
        return JSONResponse(
            content={
                "schemaVersion": "1.0.0",
                "providerId": "wokwi",
                "workspaceDigest": structured.get("workspaceDigest"),
                "manifest": structured.get("manifest"),
                "files": structured.get("files"),
            },
            headers={
                "Content-Disposition": (
                    f'attachment; filename="nexus-{project_id}-wokwi-workspace.json"'
                )
            },
        )
    except (ProjectNotFoundError, ArtifactNotFoundError):
        return _error(
            404,
            code="SIMULATION_INPUT_NOT_FOUND",
            message="Electrical Architecture or Component Plan was not found.",
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
        return cast(
            dict[str, Any],
            _store.get_artifact(project_id, artifact_type, version=version),
        )
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
        return cast(dict[str, Any], _store.get_history(project_id, limit=limit))
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
        return cast(
            dict[str, Any],
            await _mod_service.submit_turn(
                project_id,
                body.message.strip(),
                autonomy_mode=body.autonomyMode,
                request_id=request_id,
            ),
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
        if existing is not None:
            return existing
        # Lazily create workspace state for existing artifacts so editable
        # surfaces do not leave the UI on a permanent WORKSPACE_NOT_FOUND 404.
        actor = {
            "schemaVersion": "1.0.0",
            "actorId": new_id("actor"),
            "actorType": "user",
            "displayName": "User",
        }
        return _kernel.workspaces.create_if_missing(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
        )
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except ArtifactNotFoundError:
        return _error(
            404,
            code="ARTIFACT_NOT_FOUND",
            message="Artifact type not found for this project.",
            request_id=request_id,
        )
    except BoardError as exc:
        return _error(422, code=exc.code, message=exc.message, request_id=request_id)
    except Exception:  # noqa: BLE001
        logger.exception("workspace_resolve_failed request_id=%s", request_id)
        return _error(
            500,
            code="WORKSPACE_CREATE_FAILED",
            message="Failed to resolve workspace.",
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
        "workspace.acquire-edit-lease",
        "workspace.release-edit-lease",
        "workspace.discard-draft",
        "workspace.create-snapshot",
        "workspace.restore-snapshot",
        "artifact.validate-draft",
        "artifact.propose-revision",
        "artifact.accept-revision",
        "artifact.reject-revision",
        "artifact.execute",
        "artifact.inspect-deletion-impact",
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
        items, next_cursor = _kernel.executions.list_runs(project_id, limit=limit, cursor=cursor)
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
        items, next_cursor = _kernel.ledger.list_events(project_id, limit=limit, cursor=cursor)
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
            root = str(nodes[0]["nodeId"])
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


@app.get("/v1/runtime/health", response_model=None)
async def runtime_health(request: Request) -> dict[str, Any] | JSONResponse:
    """Internal/dev scheduler + runtime availability (not a product dashboard)."""
    request_id = _request_id(request)
    try:
        return {
            "requestId": request_id,
            **_kernel.jobs.health(),
            "executionRuntimeConfigured": settings.execution_runtime,
        }
    except Exception as exc:  # noqa: BLE001
        return _error(
            500,
            code="RUNTIME_HEALTH_FAILED",
            message=str(exc)[:300],
            request_id=request_id,
        )


@app.post("/v1/admin/retention/gc", response_model=None)
async def admin_retention_gc(
    request: Request,
    dry_run: bool = Query(default=True),
) -> dict[str, Any] | JSONResponse:
    """Dev/admin reference-aware GC. Defaults to dry-run; never deletes protected refs."""
    request_id = _request_id(request)
    try:
        plan = _kernel.retention.plan()
        result = _kernel.retention.apply(plan, dry_run=dry_run)
        return {"requestId": request_id, **result}
    except Exception as exc:  # noqa: BLE001
        return _error(
            500,
            code="RETENTION_GC_FAILED",
            message=str(exc)[:300],
            request_id=request_id,
        )


def _workspace_runtime_actor(body: dict[str, Any] | None) -> dict[str, Any]:
    raw = (body or {}).get("requestedBy")
    if isinstance(raw, dict) and raw.get("actorId"):
        return raw
    return {
        "schemaVersion": "1.0.0",
        "actorId": new_id("actor"),
        "actorType": "user",
        "displayName": "User",
    }


@app.get(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/runtime",
    response_model=None,
)
async def get_workspace_runtime_binding(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Phase 14D: resolve artifact ↔ filesystem-workspace binding + capabilities."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        binding = _kernel.workspace_runtime.resolve_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            create_if_missing=True,
        )
        return {
            "binding": {
                key: binding[key]
                for key in (
                    "schemaVersion",
                    "projectId",
                    "artifactId",
                    "artifactType",
                    "workspaceId",
                    "workspaceType",
                    "baseArtifactVersion",
                    "baseProjectStateVersion",
                    "currentSnapshotId",
                    "capabilities",
                    "requiredCapabilities",
                    "filesystemEnabled",
                )
            },
            "draft": binding["draft"],
        }
    except ProjectNotFoundError:
        return _error(
            404, code="PROJECT_NOT_FOUND", message="Project not found.", request_id=request_id
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/files",
    response_model=None,
)
async def list_artifact_workspace_files(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return _kernel.workspace_runtime.list_files(
            project_id=project_id, artifact_type=artifact_type
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/file",
    response_model=None,
)
async def read_artifact_workspace_file(
    project_id: str,
    artifact_type: str,
    request: Request,
    path: str = Query(..., min_length=1),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        result = _kernel.workspace_runtime.read_file(
            project_id=project_id, artifact_type=artifact_type, path=path
        )
        payload = _encode_file_content(result["content"])
        return {"binding": result["binding"], "file": result["file"], **payload}
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.put(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/file",
    response_model=None,
)
async def write_artifact_workspace_file(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    content, content_error = _decode_file_content(body)
    if content_error is not None or content is None:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=content_error or "Invalid file content.",
            request_id=request_id,
        )
    try:
        actor = _workspace_runtime_actor(body)
        return _kernel.workspace_runtime.write_file(
            project_id=project_id,
            artifact_type=artifact_type,
            path=str(body.get("path") or ""),
            content=content,
            actor=actor,
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
            origin=body.get("origin"),
            write_policy=body.get("writePolicy"),
            generated_from=body.get("generatedFrom"),
            media_type=body.get("mediaType"),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.delete(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/file",
    response_model=None,
)
async def delete_artifact_workspace_file(
    project_id: str,
    artifact_type: str,
    request: Request,
    path: str = Query(..., min_length=1),
    expectedDraftVersion: int = Query(...),
    baseArtifactVersion: int = Query(...),
    baseProjectStateVersion: int = Query(...),
    actorId: str | None = Query(default=None),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body: dict[str, Any] = {}
        try:
            raw = await request.json()
            if isinstance(raw, dict):
                body = raw
        except Exception:  # noqa: BLE001
            body = {}
        actor_body = body
        if actorId and not isinstance(body.get("requestedBy"), dict):
            actor_body = {
                **body,
                "requestedBy": {
                    "schemaVersion": "1.0.0",
                    "actorId": actorId,
                    "actorType": "user",
                    "displayName": "User",
                },
            }
        return _kernel.workspace_runtime.delete_file(
            project_id=project_id,
            artifact_type=artifact_type,
            path=path,
            actor=_workspace_runtime_actor(actor_body),
            expected_draft_version=expectedDraftVersion,
            base_artifact_version=baseArtifactVersion,
            base_project_state_version=baseProjectStateVersion,
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/snapshots",
    response_model=None,
)
async def list_artifact_workspace_snapshots(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return _kernel.workspace_runtime.list_snapshots(
            project_id=project_id, artifact_type=artifact_type
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/snapshots",
    response_model=None,
)
async def create_artifact_workspace_snapshot(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        create = (
            _kernel.workspace_runtime.create_firmware_snapshot
            if artifact_type == "firmware"
            else _kernel.workspace_runtime.create_snapshot
        )
        return create(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=_workspace_runtime_actor(body),
            reason=body.get("reason"),
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/snapshots/{snapshot_id}/restore",
    response_model=None,
)
async def restore_artifact_workspace_snapshot(
    project_id: str,
    artifact_type: str,
    snapshot_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        restore = (
            _kernel.workspace_runtime.restore_firmware_snapshot
            if artifact_type == "firmware"
            else _kernel.workspace_runtime.restore_analysis_snapshot
            if artifact_type == "analysis"
            else _kernel.workspace_runtime.restore_snapshot
        )
        return restore(
            project_id=project_id,
            artifact_type=artifact_type,
            snapshot_id=snapshot_id,
            actor=_workspace_runtime_actor(body),
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/executions",
    response_model=None,
)
async def start_artifact_workspace_execution(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Start validated sandbox execution (not an unrestricted remote shell)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        return _kernel.workspace_runtime.start_execution(
            project_id=project_id,
            artifact_type=artifact_type,
            snapshot_id=str(body["snapshotId"]),
            actor=_workspace_runtime_actor(body),
            command_spec=body["commandSpec"],
            base_artifact_version=(
                int(body["baseArtifactVersion"])
                if body.get("baseArtifactVersion") is not None
                else None
            ),
            base_project_state_version=(
                int(body["baseProjectStateVersion"])
                if body.get("baseProjectStateVersion") is not None
                else None
            ),
            max_duration_ms=(
                int(body["maxDurationMs"]) if body.get("maxDurationMs") is not None else None
            ),
            execution_kind=str(body.get("executionKind") or "sandbox-execution"),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


def _decode_file_content(body: dict[str, Any]) -> tuple[bytes | None, str | None]:
    """Return (content, error_message)."""
    encoding = str(body.get("encoding") or "utf-8")
    if body.get("contentBase64") is not None:
        import base64

        try:
            return base64.b64decode(str(body["contentBase64"]), validate=True), None
        except Exception:  # noqa: BLE001
            return None, "Invalid contentBase64 payload."
    if body.get("content") is None:
        return None, "File content is required."
    text = body["content"]
    if not isinstance(text, str):
        return None, "Text content must be a string."
    if encoding not in {"utf-8", "utf8"}:
        return None, "Unsupported text encoding."
    return text.encode("utf-8"), None


def _encode_file_content(content: bytes) -> dict[str, Any]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        import base64

        return {
            "encoding": "base64",
            "contentBase64": base64.b64encode(content).decode("ascii"),
            "sizeBytes": len(content),
        }
    return {"encoding": "utf-8", "content": text, "sizeBytes": len(content)}


@app.get("/v1/projects/{project_id}/workspaces/{workspace_id}/files", response_model=None)
async def list_workspace_files(
    project_id: str,
    workspace_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        workspace = _kernel.kernel_store.get_workspace(workspace_id)
        if workspace["projectId"] != project_id:
            return _error(
                404,
                code="WORKSPACE_NOT_FOUND",
                message="Workspace not found.",
                request_id=request_id,
            )
        files = _kernel.filesystem.list_files(workspace_id)
        return {"workspaceId": workspace_id, "files": files}
    except WorkspaceNotFoundError:
        return _error(
            404, code="WORKSPACE_NOT_FOUND", message="Workspace not found.", request_id=request_id
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get("/v1/projects/{project_id}/workspaces/{workspace_id}/file", response_model=None)
async def read_workspace_file(
    project_id: str,
    workspace_id: str,
    request: Request,
    path: str = Query(..., min_length=1),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        workspace = _kernel.kernel_store.get_workspace(workspace_id)
        if workspace["projectId"] != project_id:
            return _error(
                404,
                code="WORKSPACE_NOT_FOUND",
                message="Workspace not found.",
                request_id=request_id,
            )
        result = _kernel.filesystem.read_file(workspace_id, path)
        payload = _encode_file_content(result["content"])
        return {"file": result["file"], **payload}
    except WorkspaceNotFoundError:
        return _error(
            404, code="WORKSPACE_NOT_FOUND", message="Workspace not found.", request_id=request_id
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.put("/v1/projects/{project_id}/workspaces/{workspace_id}/file", response_model=None)
async def write_workspace_file(
    project_id: str,
    workspace_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    content, content_error = _decode_file_content(body)
    if content_error is not None or content is None:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=content_error or "Invalid file content.",
            request_id=request_id,
        )
    try:
        workspace = _kernel.kernel_store.get_workspace(workspace_id)
        if workspace["projectId"] != project_id:
            return _error(
                404,
                code="WORKSPACE_NOT_FOUND",
                message="Workspace not found.",
                request_id=request_id,
            )
        result = _kernel.filesystem.write_file(
            workspace_id=workspace_id,
            path=str(body.get("path") or ""),
            content=content,
            actor=body["requestedBy"],
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
            origin=body.get("origin"),
            write_policy=body.get("writePolicy"),
            generated_from=body.get("generatedFrom"),
            media_type=body.get("mediaType"),
        )
        return result
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except WorkspaceNotFoundError:
        return _error(
            404, code="WORKSPACE_NOT_FOUND", message="Workspace not found.", request_id=request_id
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/workspaces/{workspace_id}/files/rename",
    response_model=None,
)
async def rename_workspace_file(
    project_id: str,
    workspace_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        workspace = _kernel.kernel_store.get_workspace(workspace_id)
        if workspace["projectId"] != project_id:
            return _error(
                404,
                code="WORKSPACE_NOT_FOUND",
                message="Workspace not found.",
                request_id=request_id,
            )
        return _kernel.filesystem.rename_file(
            workspace_id=workspace_id,
            from_path=str(body.get("fromPath") or ""),
            to_path=str(body.get("toPath") or ""),
            actor=body["requestedBy"],
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except WorkspaceNotFoundError:
        return _error(
            404, code="WORKSPACE_NOT_FOUND", message="Workspace not found.", request_id=request_id
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.delete("/v1/projects/{project_id}/workspaces/{workspace_id}/file", response_model=None)
async def delete_workspace_file(
    project_id: str,
    workspace_id: str,
    request: Request,
    path: str = Query(..., min_length=1),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        workspace = _kernel.kernel_store.get_workspace(workspace_id)
        if workspace["projectId"] != project_id:
            return _error(
                404,
                code="WORKSPACE_NOT_FOUND",
                message="Workspace not found.",
                request_id=request_id,
            )
        return _kernel.filesystem.delete_file(
            workspace_id=workspace_id,
            path=path,
            actor=body["requestedBy"],
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except WorkspaceNotFoundError:
        return _error(
            404, code="WORKSPACE_NOT_FOUND", message="Workspace not found.", request_id=request_id
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get("/v1/projects/{project_id}/executions/{execution_run_id}", response_model=None)
async def get_project_execution(
    project_id: str,
    execution_run_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        run = _kernel.executions.get_run(execution_run_id)
        if run.get("projectId") != project_id:
            raise ExecutionNotFoundError(execution_run_id)
        job = _kernel.jobs.get_job_for_run(execution_run_id)
        return {
            "schemaVersion": "1.0.0",
            "executionRun": run,
            "executionJob": job,
        }
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except ExecutionNotFoundError:
        return _error(
            404,
            code="EXECUTION_NOT_FOUND",
            message="Execution run not found.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/executions/{execution_run_id}/logs", response_model=None)
async def get_project_execution_logs(
    project_id: str,
    execution_run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0, alias="after"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        run = _kernel.executions.get_run(execution_run_id)
        if run.get("projectId") != project_id:
            raise ExecutionNotFoundError(execution_run_id)
        return _kernel.executions.list_logs(
            execution_run_id,
            after_sequence=after,
            limit=limit,
        )
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except ExecutionNotFoundError:
        return _error(
            404,
            code="EXECUTION_NOT_FOUND",
            message="Execution run not found.",
            request_id=request_id,
        )
    except BoardError as exc:
        return _error(
            422,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )


@app.post("/v1/projects/{project_id}/executions/{execution_run_id}/cancel", response_model=None)
async def cancel_project_execution(
    project_id: str,
    execution_run_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        run = _kernel.executions.get_run(execution_run_id)
        if run.get("projectId") != project_id:
            raise ExecutionNotFoundError(execution_run_id)
        actor = body.get("requestedBy") if isinstance(body, dict) else None
        result = _kernel.executions.cancel(execution_run_id, actor=actor)
        return {
            "schemaVersion": "1.0.0",
            "executionRun": result["executionRun"],
            "executionJob": result["executionJob"],
        }
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except ExecutionNotFoundError:
        return _error(
            404,
            code="EXECUTION_NOT_FOUND",
            message="Execution run not found.",
            request_id=request_id,
        )
    except BoardError as exc:
        return _error(
            422,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/outputs", response_model=None)
async def list_project_outputs(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "items": _kernel.executions.list_outputs(project_id),
        }
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )


@app.get("/v1/projects/{project_id}/outputs/{output_id}", response_model=None)
async def get_project_output(
    project_id: str,
    output_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        output = _kernel.executions.get_output(output_id)
        if output.get("projectId") != project_id:
            raise ExecutionNotFoundError(f"Produced output not found: {output_id}")
        return output
    except ProjectNotFoundError:
        return _error(
            404,
            code="PROJECT_NOT_FOUND",
            message="Project not found.",
            request_id=request_id,
        )
    except ExecutionNotFoundError:
        return _error(
            404,
            code="OUTPUT_NOT_FOUND",
            message="Produced output not found.",
            request_id=request_id,
        )


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/scaffold", response_model=None
)
async def generate_artifact_workspace_scaffold(
    project_id: str, artifact_type: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Generate the deterministic Firmware scaffold (Phase 15B)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        actor = _workspace_runtime_actor(body)
        result = (
            _kernel.workspace_runtime.generate_analysis_scaffold
            if artifact_type == "analysis"
            else _kernel.workspace_runtime.generate_firmware_scaffold
        )(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
            profile_id=body.get("profileId"),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "status": result["status"],
            "generationId": result.get("generationId"),
            "generationKind": result.get("generationKind"),
            "profile": result.get("profile"),
            "generatedFiles": result.get("generatedFiles"),
            "primaryPath": result.get("primaryPath"),
            "binding": result.get("binding"),
            "draft": result.get("draft"),
            "workspace": result.get("workspace"),
        }
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        if exc.code == "WORKSPACE_SCAFFOLD_CONFLICT":
            status = 409
        elif "NOT_FOUND" in exc.code:
            status = 404
        else:
            status = 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/patch/propose",
    response_model=None,
)
async def propose_artifact_workspace_patch(
    project_id: str, artifact_type: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Generate a firmware patch proposal against an immutable base snapshot (Phase 15C)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    requested_change = body.get("requestedChange")
    if not isinstance(requested_change, str) or not requested_change.strip():
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="requestedChange must be a nonempty string.",
            request_id=request_id,
        )
    try:
        result = await asyncio.to_thread(
            _kernel.workspace_runtime.propose_analysis_patch
            if artifact_type == "analysis"
            else _kernel.workspace_runtime.propose_firmware_patch,
            project_id=project_id,
            artifact_type=artifact_type,
            actor=_workspace_runtime_actor(body),
            requested_change=requested_change,
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "status": result["status"],
            "proposal": result.get("proposal"),
            "baseSnapshotId": result.get("proposal", {}).get("baseSnapshotId"),
            "binding": result.get("binding"),
        }
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        if exc.code in {"FIRMWARE_PATCH_STALE"}:
            status = 409
        elif "NOT_FOUND" in exc.code:
            status = 404
        else:
            status = 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/patch/apply", response_model=None
)
async def apply_artifact_workspace_patch(
    project_id: str, artifact_type: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Apply a previously proposed firmware patch (Phase 15C)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        result = (
            _kernel.workspace_runtime.apply_analysis_patch
            if artifact_type == "analysis"
            else _kernel.workspace_runtime.apply_firmware_patch
        )(
            project_id=project_id,
            artifact_type=artifact_type,
            proposal_id=str(body["proposalId"]),
            actor=_workspace_runtime_actor(body),
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "status": result["status"],
            "proposal": result.get("proposal"),
            "appliedFiles": result.get("appliedFiles"),
            "applySemantics": result.get("applySemantics"),
            "binding": result.get("binding"),
            "draft": result.get("draft"),
            "workspace": result.get("workspace"),
        }
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        if exc.code in {"FIRMWARE_PATCH_STALE"}:
            status = 409
        elif "NOT_FOUND" in exc.code:
            status = 404
        else:
            status = 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/patch/discard",
    response_model=None,
)
async def discard_artifact_workspace_patch(
    project_id: str, artifact_type: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Discard a proposed firmware patch without workspace mutation (Phase 15C)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        result = (
            _kernel.workspace_runtime.discard_analysis_patch
            if artifact_type == "analysis"
            else _kernel.workspace_runtime.discard_firmware_patch
        )(
            project_id=project_id,
            artifact_type=artifact_type,
            proposal_id=str(body["proposalId"]),
            actor=_workspace_runtime_actor(body),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "status": result["status"],
            "proposal": result.get("proposal"),
            "binding": result.get("binding"),
        }
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/snapshots/{snapshot_id}/file",
    response_model=None,
)
async def read_artifact_workspace_snapshot_file(
    project_id: str, artifact_type: str, snapshot_id: str, request: Request, path: str = ""
) -> dict[str, Any] | JSONResponse:
    """Read-only preview of a file from an immutable filesystem snapshot (Phase 15D)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    if not path.strip():
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="path query parameter is required.",
            request_id=request_id,
        )
    try:
        return (
            _kernel.workspace_runtime.read_analysis_snapshot_file
            if artifact_type == "analysis"
            else _kernel.workspace_runtime.read_firmware_snapshot_file
        )(project_id=project_id, artifact_type=artifact_type, snapshot_id=snapshot_id, path=path)
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/compile", response_model=None
)
async def compile_artifact_firmware(
    project_id: str, artifact_type: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Compile firmware against an immutable pre-compile snapshot (Phase 15E)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        result = _kernel.workspace_runtime.compile_firmware(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=_workspace_runtime_actor(body),
            base_artifact_version=body.get("baseArtifactVersion"),
            base_project_state_version=body.get("baseProjectStateVersion"),
            max_duration_ms=body.get("maxDurationMs"),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "operation": result.get("operation"),
            "executionSnapshotId": result.get("executionSnapshotId"),
            "executionRun": result.get("executionRun"),
            "executionJob": result.get("executionJob"),
            "toolchainProfile": result.get("toolchainProfile"),
            "binding": result.get("binding"),
            "accepted": result.get("accepted"),
            "startedAt": result.get("startedAt"),
        }
    except BoardError as exc:
        status = 422
        if exc.code == "FIRMWARE_TOOLCHAIN_VALIDATION_FAILED":
            status = 422
        elif "NOT_FOUND" in exc.code:
            status = 404
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post("/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/test", response_model=None)
async def test_artifact_firmware(
    project_id: str, artifact_type: str, request: Request
) -> dict[str, Any] | JSONResponse:
    """Run firmware tests against an immutable pre-test snapshot (Phase 15E)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        result = _kernel.workspace_runtime.test_firmware(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=_workspace_runtime_actor(body),
            base_artifact_version=body.get("baseArtifactVersion"),
            base_project_state_version=body.get("baseProjectStateVersion"),
            max_duration_ms=body.get("maxDurationMs"),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "operation": result.get("operation"),
            "executionSnapshotId": result.get("executionSnapshotId"),
            "executionRun": result.get("executionRun"),
            "executionJob": result.get("executionJob"),
            "toolchainProfile": result.get("toolchainProfile"),
            "binding": result.get("binding"),
            "accepted": result.get("accepted"),
            "startedAt": result.get("startedAt"),
        }
    except BoardError as exc:
        status = 422
        if exc.code == "FIRMWARE_TEST_NOT_CONFIGURED":
            status = 422
        elif "NOT_FOUND" in exc.code:
            status = 404
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post("/v1/projects/{project_id}/verify/promote-execution", response_model=None)
async def promote_execution_evidence(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Promote ExecutionRun ProducedOutputs into a Test Plan revision (Phase 17F)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict) or not body.get("executionRunId"):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="executionRunId is required.",
            request_id=request_id,
        )
    try:
        return _kernel.verification.promote_execution_evidence(
            project_id=project_id,
            execution_run_id=str(body["executionRunId"]),
            actor=_workspace_runtime_actor(body),
            accept=bool(body.get("accept", True)),
        )
    except ExecutionNotFoundError as exc:
        return _error(404, code=exc.code, message=exc.message, request_id=request_id)
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post("/v1/projects/{project_id}/verify/promote-analysis-summary", response_model=None)
async def promote_analysis_summary(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Promote a deterministic Analysis summary into Test Plan revision (Phase 17F)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict) or not isinstance(body.get("summary"), dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="summary object is required.",
            request_id=request_id,
        )
    try:
        return _kernel.verification.promote_analysis_summary(
            project_id=project_id,
            summary=body["summary"],
            produced_output_names=list(body.get("producedOutputNames") or []),
            actor=_workspace_runtime_actor(body),
            execution_run_id=body.get("executionRunId"),
            accept=bool(body.get("accept", True)),
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post("/v1/projects/{project_id}/verify/promote-structural", response_model=None)
async def promote_structural_mapping(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Promote Electrical/Wokwi pin maps into structural Test Plan evidence (Phase 17F)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict) or not isinstance(body.get("signalMap"), dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="signalMap object is required.",
            request_id=request_id,
        )
    try:
        signal_map = {str(k): str(v) for k, v in body["signalMap"].items()}
        return _kernel.verification.promote_structural_mapping(
            project_id=project_id,
            signal_map=signal_map,
            actor=_workspace_runtime_actor(body),
            source_id=body.get("sourceId"),
            accept=bool(body.get("accept", True)),
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get("/v1/projects/{project_id}/verify/evidence-chain", response_model=None)
async def get_verification_evidence_chain(
    project_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Requirement → TestCase → EvidenceReference chain for Evidence Explorer."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        _store.get_project(project_id)  # type: ignore[attr-defined]
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "chains": _kernel.verification.evidence_chain(project_id),
            "requirementVerification": _kernel.verification.requirement_verification_projection(
                project_id
            ),
        }
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)
    except Exception:  # noqa: BLE001
        logger.exception("evidence_chain_failed request_id=%s", request_id)
        return _error(
            500,
            code="PROJECT_RETRIEVAL_FAILED",
            message="Failed to retrieve verification evidence chain.",
            request_id=request_id,
        )


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/inputs/upload",
    response_model=None,
)
async def upload_analysis_input_file(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Phase 16B: Analysis input upload into analysis `data/`."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )

    content, content_error = _decode_file_content(body)
    if content_error is not None or content is None:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=content_error or "Invalid file content.",
            request_id=request_id,
        )

    try:
        return _kernel.workspace_runtime.write_analysis_input_file(
            project_id=project_id,
            artifact_type=artifact_type,
            path=str(body["path"]),
            content=content,
            actor=_workspace_runtime_actor(body),
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
            media_type=body.get("mediaType"),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/inputs/import-produced-output",
    response_model=None,
)
async def import_produced_output_into_analysis_input(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Phase 16B: Copy an existing ProducedOutput into analysis `data/`."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )

    try:
        return _kernel.workspace_runtime.import_produced_output_into_analysis_input(
            project_id=project_id,
            artifact_type=artifact_type,
            output_id=str(body["outputId"]),
            path=str(body["path"]),
            actor=_workspace_runtime_actor(body),
            expected_draft_version=int(body["expectedDraftVersion"]),
            base_artifact_version=int(body["baseArtifactVersion"]),
            base_project_state_version=int(body["baseProjectStateVersion"]),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if exc.code.endswith("NOT_FOUND") else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/run",
    response_model=None,
)
async def run_artifact_analysis(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Run analysis.py against an immutable pre-run snapshot (Phase 16D)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        result = _kernel.workspace_runtime.run_analysis(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=_workspace_runtime_actor(body),
            base_artifact_version=body.get("baseArtifactVersion"),
            base_project_state_version=body.get("baseProjectStateVersion"),
            max_duration_ms=body.get("maxDurationMs"),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "operation": result.get("operation"),
            "executionSnapshotId": result.get("executionSnapshotId"),
            "executionRun": result.get("executionRun"),
            "executionJob": result.get("executionJob"),
            "toolchainProfile": result.get("toolchainProfile"),
            "binding": result.get("binding"),
            "accepted": result.get("accepted"),
            "startedAt": result.get("startedAt"),
        }
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/rerun",
    response_model=None,
)
async def rerun_artifact_analysis(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Re-run analysis against a specific immutable snapshot (Phase 16D)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        result = _kernel.workspace_runtime.rerun_analysis(
            project_id=project_id,
            artifact_type=artifact_type,
            snapshot_id=str(body["snapshotId"]),
            actor=_workspace_runtime_actor(body),
            base_artifact_version=body.get("baseArtifactVersion"),
            base_project_state_version=body.get("baseProjectStateVersion"),
            max_duration_ms=body.get("maxDurationMs"),
            causation_id=body.get("commandId") or body.get("causationId"),
        )
        return {
            "schemaVersion": "1.0.0",
            "operation": result.get("operation"),
            "rerun": result.get("rerun"),
            "executionSnapshotId": result.get("executionSnapshotId"),
            "executionRun": result.get("executionRun"),
            "executionJob": result.get("executionJob"),
            "toolchainProfile": result.get("toolchainProfile"),
            "binding": result.get("binding"),
            "accepted": result.get("accepted"),
            "startedAt": result.get("startedAt"),
        }
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.post(
    "/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/compare-outputs",
    response_model=None,
)
async def compare_artifact_analysis_outputs(
    project_id: str,
    artifact_type: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Compare ProducedOutput content hashes between baseline and rerun (Phase 16G)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    if artifact_type != "analysis":
        return _error(
            422,
            code="WORKSPACE_RUNTIME_CAPABILITY_DENIED",
            message="Output hash comparison is only available for artifact type analysis",
            request_id=request_id,
        )
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Invalid JSON body.",
            request_id=request_id,
        )
    if not isinstance(body, dict):
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message="Body must be an object.",
            request_id=request_id,
        )
    try:
        return _kernel.workspace_runtime.compare_analysis_run_outputs(
            project_id=project_id,
            baseline_execution_run_id=str(body["baselineExecutionRunId"]),
            rerun_execution_run_id=str(body["rerunExecutionRunId"]),
        )
    except KeyError as exc:
        return _error(
            422,
            code="COMMAND_VALIDATION_FAILED",
            message=f"Missing required field: {exc.args[0]}",
            request_id=request_id,
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)


@app.get(
    "/v1/projects/{project_id}/artifacts/analysis/workspace/outputs/{output_id}/preview",
    response_model=None,
)
async def preview_analysis_produced_output(
    project_id: str,
    output_id: str,
    request: Request,
) -> dict[str, Any] | JSONResponse:
    """Bounded Analysis ProducedOutput preview (Phase 16G)."""
    request_id = _request_id(request)
    invalid = _validate_project_id(project_id, request_id)
    if invalid:
        return invalid
    try:
        return _kernel.workspace_runtime.preview_analysis_output(
            project_id=project_id,
            output_id=output_id,
        )
    except BoardError as exc:
        status = 404 if "NOT_FOUND" in exc.code else 422
        return _error(status, code=exc.code, message=exc.message, request_id=request_id)
