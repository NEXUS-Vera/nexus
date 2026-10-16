"""Fixture-backed initialization provider (Phase 5–6 behavior preserved)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..fixture_router import FixtureRouteOutcome, route_fixture_family
from ..materializer import (
    initialization_dict_to_package_bundle,
    materialize_fixture_package,
)
from ..validation import (
    validate_initialization_package,
    validate_initialization_result_schema,
)
from ..workflow_ledger import WorkflowLedger
from .base import AutonomyMode, InitializationRequestContext

logger = logging.getLogger("nexus.embedded.project_initialization.fixture")

FIXTURES_ROOT = (
    Path(__file__).resolve().parents[7] / "packages" / "contracts" / "examples" / "valid"
)


class FixtureRoutingError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        matched_families: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.matched_families = matched_families


class FixtureValidationError(Exception):
    def __init__(
        self,
        *,
        codes: list[str],
        message: str,
        workflow_run: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.codes = codes
        self.message = message
        self.workflow_run = workflow_run


@dataclass
class FixtureInitializationProvider:
    fixtures_root: Path = FIXTURES_ROOT

    async def initialize(
        self,
        message: str,
        autonomy_mode: AutonomyMode,
        request_context: InitializationRequestContext,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = request_context.request_id
        decision = route_fixture_family(message)
        if decision.outcome is FixtureRouteOutcome.UNSUPPORTED:
            raise FixtureRoutingError(
                code="UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE",
                message=(
                    "This prompt does not match a supported fixture-backed embedded "
                    "project family for the current phase."
                ),
                matched_families=(),
            )
        if decision.outcome is FixtureRouteOutcome.AMBIGUOUS:
            raise FixtureRoutingError(
                code="AMBIGUOUS_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE",
                message=(
                    "This prompt matches multiple supported fixture families. "
                    "Narrow the project description to one family."
                ),
                matched_families=decision.matched_families,
            )

        family = decision.family
        assert family is not None
        fixture_folder = self.fixtures_root / family
        if not fixture_folder.is_dir():
            raise FixtureValidationError(
                codes=["FIXTURE_FAMILY_MISSING"],
                message=f"Fixture family directory missing: {family}",
            )

        result, _id_map = materialize_fixture_package(
            fixture_folder,
            message=message,
            autonomy_mode=autonomy_mode,
        )

        fixture_workflow = result.get("workflowRun") or {}
        ledger = WorkflowLedger(
            workflow_run_id=str(fixture_workflow.get("workflowRunId")),
            workflow_type=str(
                fixture_workflow.get("workflowType") or "embedded-project-initialization"
            ),
            project_id=str(result["project"]["projectId"]),
            turn_id=str(result["userTurn"]["turnId"]),
            warnings=list(fixture_workflow.get("warnings") or []),
            error_references=[],
        )
        ledger.begin_run()

        for step_type in (
            "route-turn",
            "select-fixture-family",
            "create-project-context",
        ):
            step = ledger.start_step(step_type)
            ledger.complete_step(step)

        artifact_refs = _artifact_refs(result)
        step = ledger.start_step("materialize-fixture-package")
        ledger.complete_step(step, output_artifact_references=artifact_refs)
        result["workflowRun"] = ledger.to_workflow_run()

        result = _ensure_layered_architecture_artifacts(result, ledger)
        artifact_refs = _artifact_refs(result)
        result["workflowRun"] = ledger.to_workflow_run()

        step = ledger.start_step("validate-schema")
        schema_errors = validate_initialization_result_schema(result)
        if schema_errors:
            ledger.fail_step(step)
            failed_run = ledger.to_workflow_run()
            raise FixtureValidationError(
                codes=["SCHEMA_VALIDATION_FAILED"],
                message="Materialized package failed schema validation.",
                workflow_run=failed_run,
            )
        ledger.complete_step(step)
        result["workflowRun"] = ledger.to_workflow_run()

        step = ledger.start_step("validate-project-package")
        package_bundle = initialization_dict_to_package_bundle(result)
        semantic_errors = validate_initialization_package(package_bundle)
        blocking = [e for e in semantic_errors if getattr(e, "blocking", True)]
        if blocking:
            codes = sorted({e.code for e in blocking})
            ledger.fail_step(step)
            failed_run = ledger.to_workflow_run()
            raise FixtureValidationError(
                codes=codes,
                message="Materialized package failed project-package semantic validation.",
                workflow_run=failed_run,
            )
        ledger.complete_step(step)

        step = ledger.start_step("build-result")
        ledger.complete_step(step, output_artifact_references=artifact_refs)
        step = ledger.start_step("complete-workflow")
        ledger.complete_step(step, output_artifact_references=artifact_refs)
        ledger.finish_success()
        result["workflowRun"] = ledger.to_workflow_run()

        final_schema_errors = validate_initialization_result_schema(result)
        if final_schema_errors:
            raise FixtureValidationError(
                codes=["SCHEMA_VALIDATION_FAILED"],
                message="Completed initialization package failed schema validation.",
                workflow_run=result["workflowRun"],
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "fixture_initialization_completed",
            extra={
                "request_id": request_id,
                "route_family": family,
                "duration_ms": duration_ms,
            },
        )
        return result


def _artifact_refs(result: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for art in result.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        refs.append(
            {
                "artifactType": art["artifactType"],
                "artifactId": art["artifactId"],
                "artifactVersion": art.get("artifactVersion", 1),
                "contentSchemaVersion": art.get("contentSchemaVersion", "1.0.0"),
            }
        )
    return refs


def _ensure_layered_architecture_artifacts(
    result: dict[str, Any],
    ledger: WorkflowLedger,
) -> dict[str, Any]:
    """Compose provisional Electrical/Physical Architecture when missing from fixtures."""

    from nexus_embedded_systems.workflows.layered_architecture import (
        ensure_layered_architecture_artifacts,
    )

    artifacts = list(result.get("artifacts") or [])
    ensured = ensure_layered_architecture_artifacts(
        project_id=str(result["project"]["projectId"]),
        artifacts=artifacts,
        actor=(artifacts[0].get("createdBy") if artifacts else None),
        turn_id=str(result["userTurn"]["turnId"]),
        workflow_run_id=str(result["workflowRun"]["workflowRunId"]),
        now=str(
            (artifacts[0].get("updatedAt") or artifacts[0].get("createdAt")) if artifacts else None
        ),
    )
    if ensured.get("skippedReason"):
        return result

    created = ensured.get("created") or []
    for art in created:
        atype = art.get("artifactType")
        step_name = (
            "compose-electrical-architecture"
            if atype == "electrical-architecture"
            else "compose-physical-architecture"
        )
        step = ledger.start_step(step_name)
        ledger.complete_step(
            step,
            output_artifact_references=[
                {
                    "artifactType": art["artifactType"],
                    "artifactId": art["artifactId"],
                    "artifactVersion": art.get("artifactVersion", 1),
                    "contentSchemaVersion": art.get("contentSchemaVersion", "1.0.0"),
                }
            ],
        )

    ordered = list(ensured.get("artifacts") or artifacts)
    result = dict(result)
    result["artifacts"] = ordered
    result["project"] = dict(result["project"])
    result["project"]["currentArtifactReferences"] = _artifact_refs({"artifacts": ordered})

    vera = dict(result.get("veraResponse") or {})
    created_refs = list(vera.get("createdArtifactReferences") or [])
    existing_types = {r.get("artifactType") for r in created_refs if isinstance(r, dict)}
    for art in created:
        if art.get("artifactType") in existing_types:
            continue
        created_refs.append(
            {
                "artifactType": art["artifactType"],
                "artifactId": art["artifactId"],
                "artifactVersion": art.get("artifactVersion", 1),
                "contentSchemaVersion": art.get("contentSchemaVersion", "1.0.0"),
            }
        )
    vera["createdArtifactReferences"] = created_refs
    result["veraResponse"] = vera
    return result
