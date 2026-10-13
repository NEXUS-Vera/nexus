"""Multi-turn project modification service."""

from __future__ import annotations

import copy
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from nexus_contracts.validation.semantic_validators import SemanticValidationError

from nexus_embedded_systems.workflows.project_initialization.materializer import (
    initialization_dict_to_package_bundle,
)
from nexus_embedded_systems.workflows.project_initialization.validation import (
    validate_initialization_package,
    validate_initialization_result_schema,
)

from .fixture_interpreter import (
    FixtureModificationError,
    impact_for_intent,
    interpret_fixture_change,
)
from .regenerate import apply_open_question_resolution, revise_artifacts

AutonomyMode = Literal["collaborate", "delegate"]
logger = logging.getLogger("nexus.embedded.project_modification")


class ModificationError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


@dataclass
class ModificationService:
    store: Any
    mode: str = "fixture"

    async def submit_turn(
        self,
        project_id: str,
        message: str,
        autonomy_mode: AutonomyMode = "collaborate",
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        text = message.strip()
        if not text:
            raise ModificationError(
                code="UNSUPPORTED_PROJECT_MODIFICATION",
                message="Message must not be empty.",
            )
        if len(text) > 8000:
            raise ModificationError(
                code="UNSUPPORTED_PROJECT_MODIFICATION",
                message="Message exceeds the maximum allowed length.",
            )

        try:
            current = self.store.get_current_state(project_id)
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None)
            if code == "PROJECT_NOT_FOUND":
                raise ModificationError(
                    code=code, message=str(getattr(exc, "message", exc))
                ) from exc
            raise ModificationError(
                code="PROJECT_RETRIEVAL_FAILED",
                message="Failed to load the project for modification.",
            ) from exc

        turn_id = _new_id("turn")
        run_id = _new_id("run")
        route_id = _new_id("route")
        ts = _now()
        actor = {
            "schemaVersion": "1.0.0",
            "actorId": "actor_user00000000000001",
            "actorType": "user",
            "displayName": "User",
        }
        vera_actor = {
            "schemaVersion": "1.0.0",
            "actorId": "actor_vera00000000000001",
            "actorType": "vera",
            "displayName": "Vera",
        }

        steps: list[dict[str, Any]] = [
            {
                "stepId": "load-project",
                "stepType": "load-project",
                "status": "completed",
                "attempt": 1,
            },
            {"stepId": "route-turn", "stepType": "route-turn", "status": "completed", "attempt": 1},
        ]

        try:
            if self.mode != "fixture":
                # LLM modification path reserved; fixture is the default/local path.
                raise ModificationError(
                    code="UNSUPPORTED_PROJECT_MODIFICATION",
                    message=(
                        "Non-fixture modification providers are not enabled for this phase. "
                        "Set NEXUS_INITIALIZATION_PROVIDER=fixture for local modifications."
                    ),
                )
            intent = interpret_fixture_change(text, source_turn_id=turn_id, current_state=current)
            steps.append(
                {
                    "stepId": "interpret-change",
                    "stepType": "interpret-change",
                    "status": "completed",
                    "attempt": 1,
                }
            )
            steps.append(
                {
                    "stepId": "resolve-target",
                    "stepType": "resolve-target",
                    "status": "completed",
                    "attempt": 1,
                }
            )
        except FixtureModificationError as exc:
            raise ModificationError(code=exc.code, message=exc.message) from exc

        if intent.get("requiresUserConfirmation") and autonomy_mode == "collaborate":
            raise ModificationError(
                code="AMBIGUOUS_PROJECT_CHANGE_TARGET",
                message="This change requires confirmation before it can be applied.",
            )

        impact = impact_for_intent(intent)
        steps.append(
            {
                "stepId": "analyze-impact",
                "stepType": "analyze-impact",
                "status": "completed",
                "attempt": 1,
            }
        )

        try:
            artifacts, new_revisions, project = revise_artifacts(
                current_state=current,
                intent=intent,
                impact=impact,
                turn_id=turn_id,
                run_id=run_id,
                actor=vera_actor,
            )
        except ValueError as exc:
            if str(exc) == "OPEN_QUESTION_NOT_FOUND":
                raise ModificationError(
                    code="OPEN_QUESTION_NOT_FOUND",
                    message="The referenced open question was not found.",
                ) from exc
            raise

        if "requirement-set" in impact.get("regenerate", []):
            steps.append(
                {
                    "stepId": "create-requirement-revision",
                    "stepType": "create-requirement-revision",
                    "status": "completed",
                    "attempt": 1,
                }
            )
        if "functional-architecture" in impact.get("regenerate", []):
            steps.append(
                {
                    "stepId": "regenerate-functional-architecture",
                    "stepType": "regenerate-functional-architecture",
                    "status": "completed",
                    "attempt": 1,
                }
            )
        steps.append(
            {
                "stepId": "derive-next-action",
                "stepType": "derive-next-action",
                "status": "completed",
                "attempt": 1,
            }
        )

        questions = apply_open_question_resolution(current.get("openQuestions") or [], intent)
        # Drop resolved from openQuestionReferences on project
        project["openQuestionReferences"] = [
            ref
            for ref in project.get("openQuestionReferences") or []
            if any(
                q["questionId"] == ref["questionId"] and q.get("status") == "open"
                for q in questions
            )
        ]

        user_turn = {
            "schemaVersion": "1.0.0",
            "turnId": turn_id,
            "projectId": project_id,
            "rawUserMessage": text,
            "actor": actor,
            "timestamp": ts,
            "parentTurnId": current["userTurn"]["turnId"],
        }
        turn_route = {
            "schemaVersion": "1.0.0",
            "routeId": route_id,
            "turnId": turn_id,
            "supported": True,
            "routeType": "project-modification",
            "domain": "embedded-products",
            "projectOperation": intent["operation"],
            "complexity": "medium",
            "autonomyMode": autonomy_mode,
            "chairmanRequiredEventually": False,
            "reasons": [f"Fixture modification matched operation {intent['operation']}"],
        }

        next_action = next(a for a in artifacts if a["artifactType"] == "next-action")
        vera = {
            "schemaVersion": "1.0.0",
            "turnId": turn_id,
            "projectId": project_id,
            "userFacingMessage": _vera_message(intent, impact),
            "createdArtifactReferences": [
                {
                    "artifactType": a["artifactType"],
                    "artifactId": a["artifactId"],
                    "artifactVersion": a["artifactVersion"],
                    "contentSchemaVersion": "1.0.0",
                }
                for a in new_revisions
            ]
            or [
                {
                    "artifactType": next_action["artifactType"],
                    "artifactId": next_action["artifactId"],
                    "artifactVersion": next_action["artifactVersion"],
                    "contentSchemaVersion": "1.0.0",
                }
            ],
            "warningIssueReferences": [],
            "blockerIssueReferences": [],
            "openQuestionReferences": [
                {
                    "schemaVersion": "1.0.0",
                    "questionId": q["questionId"],
                    "displayId": q.get("displayId", "Q"),
                }
                for q in questions
                if q.get("status") == "open"
            ],
            "nextActionArtifactReference": {
                "artifactType": "next-action",
                "artifactId": next_action["artifactId"],
                "artifactVersion": next_action["artifactVersion"],
                "contentSchemaVersion": "1.0.0",
            },
            "projectStateSummary": {
                "projectPhase": project["projectPhase"],
                "autonomyMode": autonomy_mode,
                "openQuestionCount": sum(1 for q in questions if q.get("status") == "open"),
                "validationIssueCount": len(current.get("validationIssues") or []),
            },
            "completionStatus": "completed-with-warnings"
            if any(q.get("status") == "open" for q in questions)
            else "completed",
        }
        steps.append(
            {
                "stepId": "compose-vera-response",
                "stepType": "compose-vera-response",
                "status": "completed",
                "attempt": 1,
            }
        )

        workflow_run = {
            "schemaVersion": "1.0.0",
            "workflowRunId": run_id,
            "workflowType": "embedded-project-modification",
            "projectId": project_id,
            "turnId": turn_id,
            "runStatus": "completed",
            "stepRecords": steps
            + [
                {
                    "stepId": "validate-updated-state",
                    "stepType": "validate-updated-state",
                    "status": "completed",
                    "attempt": 1,
                },
                {
                    "stepId": "persist-updated-state",
                    "stepType": "persist-updated-state",
                    "status": "completed",
                    "attempt": 1,
                },
                {
                    "stepId": "complete-workflow",
                    "stepType": "complete-workflow",
                    "status": "completed",
                    "attempt": 1,
                },
            ],
            "startTime": ts,
            "completionTime": _now(),
            "warnings": [],
            "errorReferences": [],
        }

        package = {
            "schemaVersion": "1.0.0",
            "project": project,
            "userTurn": user_turn,
            "turnRoute": turn_route,
            "workflowRun": workflow_run,
            "artifacts": artifacts,
            "validationIssues": copy.deepcopy(current.get("validationIssues") or []),
            "openQuestions": questions,
            "veraResponse": vera,
            "dependencies": copy.deepcopy(current.get("dependencies") or []),
            "previousTurnIds": list(current.get("previousTurnIds") or [])
            + [current["userTurn"]["turnId"]],
        }

        # Validate using initialization package validator (same cross-record rules).
        # Strip fields not in ProjectInitializationResult before validation if needed.
        validation_package = {
            k: package[k]
            for k in (
                "schemaVersion",
                "project",
                "userTurn",
                "turnRoute",
                "workflowRun",
                "artifacts",
                "validationIssues",
                "openQuestions",
                "veraResponse",
            )
        }
        schema_errors = validate_initialization_result_schema(validation_package)
        if schema_errors:
            logger.error(
                "modification_schema_failed request_id=%s errors=%s",
                request_id,
                schema_errors[:5],
            )
            raise ModificationError(
                code="PROJECT_CHANGE_VALIDATION_FAILED",
                message="The updated project state failed schema validation and was not saved.",
            )
        # Init-time semantic rules assume a single-turn package. Multi-turn packages keep
        # historical sourceTurnId / user-explicit provenance on unchanged requirements.
        multi_turn_allow = {
            "TURN_ID_MISMATCH",
            "WORKFLOW_RUN_ID_MISMATCH",
            "REQ_USER_EXPLICIT_REFERENCE_WRONG_TURN",
            "REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT",
            "REQ_SOURCE_REFERENCE_USER_TURN_MISMATCH",
            "REQ_SOURCE_REFERENCE_UNKNOWN_TURN",
            "ARTIFACT_SOURCE_TURN_UNKNOWN",
            "ARTIFACT_WORKFLOW_RUN_UNKNOWN",
        }
        semantic_errors = validate_initialization_package(
            initialization_dict_to_package_bundle(validation_package)
        )
        blocking = [
            e
            for e in semantic_errors
            if getattr(e, "blocking", True) and getattr(e, "code", "") not in multi_turn_allow
        ]
        for art in new_revisions:
            if art.get("sourceTurnId") != turn_id or art.get("workflowRunId") != run_id:
                blocking.append(
                    SemanticValidationError(
                        code="MOD_REVISION_TURN_MISMATCH",
                        message="New revision must reference the modification turn.",
                    )
                )
                break
        if blocking:
            logger.error(
                "modification_validation_failed request_id=%s codes=%s",
                request_id,
                [getattr(e, "code", str(e)) for e in blocking[:5]],
            )
            raise ModificationError(
                code="PROJECT_CHANGE_VALIDATION_FAILED",
                message="The updated project state failed validation and was not saved.",
            )

        public_intent = {k: v for k, v in intent.items() if not k.startswith("_")}
        try:
            self.store.save_modification_package(
                package,
                dependencies=package.get("dependencies"),
                new_artifact_revisions=new_revisions,
            )
        except Exception as exc:  # noqa: BLE001
            raise ModificationError(
                code="PROJECT_CHANGE_PERSISTENCE_FAILED",
                message="Failed to persist the project modification.",
            ) from exc

        return {
            "schemaVersion": "1.0.0",
            "currentState": package,
            "changeIntent": public_intent,
            "impactAnalysis": impact,
            "changedArtifactTypes": list(impact.get("changed") or []),
            "regeneratedArtifactTypes": list(impact.get("regenerate") or []),
        }


def _vera_message(intent: dict[str, Any], impact: dict[str, Any]) -> str:
    regen = ", ".join(impact.get("regenerate") or []) or "none"
    return (
        f"I applied your update ({intent['operation']}). "
        f"Regenerated artifacts: {regen}. "
        f"Change summary: {intent['requestedChange']}"
    )
