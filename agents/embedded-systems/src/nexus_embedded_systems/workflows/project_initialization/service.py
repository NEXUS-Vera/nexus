"""Fixture-backed embedded project initialization workflow service."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .fixture_router import (
    SUPPORTED_FAMILIES,
    FixtureRouteOutcome,
    route_fixture_family,
)
from .materializer import (
    initialization_dict_to_package_bundle,
    materialize_fixture_package,
    utc_now,
)
from .repository import InMemoryInitializationStore
from .validation import (
    validate_initialization_package,
    validate_initialization_result_schema,
)

AutonomyMode = Literal["collaborate", "delegate"]

logger = logging.getLogger("nexus.embedded.project_initialization")

FIXTURES_ROOT = (
    Path(__file__).resolve().parents[6] / "packages" / "contracts" / "examples" / "valid"
)

WORKFLOW_STEPS = (
    "route-turn",
    "select-fixture-family",
    "create-project-context",
    "materialize-fixture-package",
    "validate-schema",
    "validate-project-package",
    "build-result",
    "complete-workflow",
)


class InitializationRoutingError(Exception):
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


class InitializationValidationError(Exception):
    def __init__(self, *, codes: list[str], message: str) -> None:
        super().__init__(message)
        self.codes = codes
        self.message = message


@dataclass
class InitializationService:
    store: InMemoryInitializationStore
    fixtures_root: Path = FIXTURES_ROOT

    async def initialize_embedded_project(
        self,
        message: str,
        autonomy_mode: AutonomyMode = "collaborate",
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        logger.info(
            "initialization_requested",
            extra={"request_id": request_id, "autonomy_mode": autonomy_mode},
        )

        decision = route_fixture_family(message)
        if decision.outcome is FixtureRouteOutcome.UNSUPPORTED:
            logger.info(
                "unsupported_route",
                extra={"request_id": request_id, "route_family": None},
            )
            raise InitializationRoutingError(
                code="UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE",
                message=(
                    "This prompt does not match a supported fixture-backed embedded "
                    "project family for the current phase."
                ),
                matched_families=(),
            )
        if decision.outcome is FixtureRouteOutcome.AMBIGUOUS:
            logger.info(
                "ambiguous_route",
                extra={
                    "request_id": request_id,
                    "matched_families": list(decision.matched_families),
                },
            )
            raise InitializationRoutingError(
                code="AMBIGUOUS_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE",
                message=(
                    "This prompt matches multiple supported fixture families. "
                    "Narrow the project description to one family."
                ),
                matched_families=decision.matched_families,
            )

        family = decision.family
        assert family is not None
        logger.info(
            "fixture_route_selected",
            extra={"request_id": request_id, "route_family": family},
        )

        fixture_folder = self.fixtures_root / family
        if not fixture_folder.is_dir():
            raise InitializationValidationError(
                codes=["FIXTURE_FAMILY_MISSING"],
                message=f"Fixture family directory missing: {family}",
            )

        now = utc_now()
        result, _id_map = materialize_fixture_package(
            fixture_folder,
            message=message,
            autonomy_mode=autonomy_mode,
            now=now,
        )

        # Rewrite workflow step records to reflect actual execution.
        result["workflowRun"] = _rewrite_workflow_run(
            result,
            now=now,
            family=family,
        )

        schema_errors = validate_initialization_result_schema(result)
        if schema_errors:
            logger.error(
                "package_validation_failed",
                extra={
                    "request_id": request_id,
                    "route_family": family,
                    "validation_codes": ["SCHEMA_VALIDATION_FAILED"],
                },
            )
            raise InitializationValidationError(
                codes=["SCHEMA_VALIDATION_FAILED"],
                message="Materialized package failed schema validation.",
            )

        package_bundle = initialization_dict_to_package_bundle(result)
        semantic_errors = validate_initialization_package(package_bundle)
        blocking = [e for e in semantic_errors if getattr(e, "blocking", True)]
        if blocking:
            codes = sorted({e.code for e in blocking})
            logger.error(
                "package_validation_failed",
                extra={
                    "request_id": request_id,
                    "route_family": family,
                    "validation_codes": codes,
                    "workflow_run_id": result["workflowRun"]["workflowRunId"],
                },
            )
            raise InitializationValidationError(
                codes=codes,
                message="Materialized package failed project-package semantic validation.",
            )

        logger.info(
            "package_validation_passed",
            extra={
                "request_id": request_id,
                "route_family": family,
                "workflow_run_id": result["workflowRun"]["workflowRunId"],
            },
        )

        project_id = result["project"]["projectId"]
        self.store.save_project(result["project"])
        self.store.save_turn(result["userTurn"])
        self.store.save_workflow_run(result["workflowRun"])
        self.store.save_artifacts(result["artifacts"])
        self.store.save_package(project_id, result)

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "initialization_completed",
            extra={
                "request_id": request_id,
                "route_family": family,
                "workflow_run_id": result["workflowRun"]["workflowRunId"],
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


def _rewrite_workflow_run(result: dict[str, Any], *, now: str, family: str) -> dict[str, Any]:
    workflow = dict(result["workflowRun"])
    refs = _artifact_refs(result)
    warning_refs = list(workflow.get("warnings") or [])
    step_records = []
    for index, step_type in enumerate(WORKFLOW_STEPS, start=1):
        step: dict[str, Any] = {
            "stepId": f"step_{index:02d}_{step_type}",
            "stepType": step_type,
            "status": "completed",
            "attempt": 1,
            "startedAt": now,
            "completedAt": now,
        }
        if step_type in {"materialize-fixture-package", "build-result", "complete-workflow"}:
            step["outputArtifactReferences"] = refs
        step_records.append(step)

    run_status = "completed-with-warnings" if warning_refs else "completed"
    workflow["stepRecords"] = step_records
    workflow["runStatus"] = run_status
    workflow["startTime"] = now
    workflow["completionTime"] = now
    # Keep warnings/errorReferences as remapped from fixture content.
    workflow["warnings"] = warning_refs
    workflow["errorReferences"] = list(workflow.get("errorReferences") or [])
    # Family is used only for logging context; not a schema field.
    _ = family
    return workflow


def supported_family_examples() -> list[dict[str, str]]:
    examples = {
        "indoor-environmental-rover": (
            "I want to build a small indoor rover that drives around a room and maps "
            "temperature, humidity, and air quality."
        ),
        "wearable-tremor-monitor": (
            "I want to build a wrist-worn device that measures hand tremors "
            "and records the motion data for later analysis."
        ),
        "greenhouse-sensing-node": (
            "I want to build a greenhouse monitoring node that measures temperature, "
            "humidity, soil moisture, and light, and reports the readings remotely."
        ),
        "vibration-monitoring-device": (
            "I want to build a device that attaches to a machine and records vibration "
            "so I can detect changes in how the machine is operating."
        ),
        "robot-obstacle-detection-module": (
            "I want to build an obstacle-detection module for a small indoor robot "
            "so it can detect objects in front of it and react before it hits them."
        ),
    }
    return [
        {"family": family, "examplePrompt": examples[family]}
        for family in SUPPORTED_FAMILIES
        if family in examples
    ]
