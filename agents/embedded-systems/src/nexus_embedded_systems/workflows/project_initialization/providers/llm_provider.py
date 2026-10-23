"""Staged LLM-backed initialization provider."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from nexus_contracts.validation.semantic_validators import validate_component_plan_content
from nexus_model_gateway import ModelGateway, ModelGatewayError, ModelPolicy
from nexus_observability import GenerationObservation, ObservationRecorder, StructuredLogRecorder

from nexus_embedded_systems.workflows.component_planning import (
    compose_component_plan_content,
    compose_component_plan_envelope,
)
from nexus_embedded_systems.workflows.layered_architecture import (
    compose_electrical_architecture_content,
    compose_electrical_architecture_envelope,
    compose_physical_architecture_content,
    compose_physical_architecture_envelope,
)

from ..assembly import (
    ProjectStage,
    build_project_shell,
    compose_vera_response_deterministic,
    normalize_architecture_draft,
    normalize_brief_draft,
    normalize_requirement_draft,
)
from ..boundary import deterministic_boundary_check
from ..execution_plan import compose_execution_plan
from ..generation.repair import repair_artifact
from ..generation.schemas import (
    FUNCTIONAL_ARCHITECTURE_DRAFT_SCHEMA,
    PROJECT_BRIEF_DRAFT_SCHEMA,
    PROJECT_INTERPRETATION_SCHEMA,
    REQUIREMENT_SET_DRAFT_SCHEMA,
)
from ..ids import artifact_envelope, default_actor, new_id, utc_now
from ..materializer import initialization_dict_to_package_bundle
from ..next_action_selector import select_next_action
from ..prompts import get_prompt
from ..validation import (
    validate_initialization_package,
    validate_initialization_result_schema,
)
from ..workflow_ledger import WorkflowLedger
from .base import AutonomyMode, InitializationRequestContext

logger = logging.getLogger("nexus.embedded.project_initialization.llm")


class LlmInitializationError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        workflow_run: dict[str, Any] | None = None,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.workflow_run = workflow_run
        self.details = details or []


@dataclass
class LlmInitializationProvider:
    gateway: ModelGateway
    model_policy: ModelPolicy
    max_repair_attempts: int = 1
    recorder: ObservationRecorder = field(default_factory=StructuredLogRecorder)

    async def initialize(
        self,
        message: str,
        autonomy_mode: AutonomyMode,
        request_context: InitializationRequestContext,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = request_context.request_id
        now = utc_now()
        user_actor = default_actor("user", display_name="User")
        vera_actor = default_actor("vera", display_name="Vera")

        # Provisional IDs so the ledger can start before interpretation finishes.
        project_id = new_id("proj_")
        turn_id = new_id("turn_")
        run_id = new_id("run_")
        ledger = WorkflowLedger(
            workflow_run_id=run_id,
            workflow_type="embedded-project-initialization",
            project_id=project_id,
            turn_id=turn_id,
        )
        ledger.begin_run()

        try:
            interpretation = await self._interpret(message, ledger, request_id, run_id)
            title = interpretation.get("candidateProjectTitle") or "Embedded project"
            raw_stage = interpretation.get("projectStage")
            stage: ProjectStage = (
                raw_stage if raw_stage in {"concept", "prototype-planning"} else "concept"
            )

            project, user_turn, turn_route = build_project_shell(
                message=message,
                title=title,
                project_phase=stage,
                autonomy_mode=autonomy_mode,
                actor=user_actor,
                now=now,
            )
            # Rebind shell IDs to ledger IDs for consistency.
            project["projectId"] = project_id
            user_turn["projectId"] = project_id
            user_turn["turnId"] = turn_id
            turn_route["turnId"] = turn_id
            shell = {
                "project": project,
                "userTurn": user_turn,
                "turnRoute": turn_route,
            }

            open_questions: list[dict[str, Any]] = []
            issues: list[dict[str, Any]] = []

            brief_art = await self._generate_brief(
                message=message,
                interpretation=interpretation,
                project_id=project_id,
                turn_id=turn_id,
                run_id=run_id,
                now=now,
                vera_actor=vera_actor,
                open_questions=open_questions,
                ledger=ledger,
                request_id=request_id,
            )

            req_art, local_key_to_req_id, missing_dimensions = await self._generate_requirements(
                message=message,
                interpretation=interpretation,
                turn_id=turn_id,
                project_id=project_id,
                run_id=run_id,
                now=now,
                vera_actor=vera_actor,
                ledger=ledger,
                request_id=request_id,
            )

            arch_art = await self._generate_architecture(
                message=message,
                interpretation=interpretation,
                local_key_to_req_id=local_key_to_req_id,
                project_id=project_id,
                turn_id=turn_id,
                run_id=run_id,
                now=now,
                vera_actor=vera_actor,
                open_questions=open_questions,
                ledger=ledger,
                request_id=request_id,
            )

            # Seed blocking issues for open measurement gaps when present.
            if missing_dimensions:
                issues.append(
                    {
                        "schemaVersion": "1.0.0",
                        "issueId": new_id("issue_"),
                        "projectId": project_id,
                        "severity": "high",
                        "code": "missing-engineering-dimensions",
                        "message": (
                            "Key engineering dimensions remain unconfirmed: "
                            + ", ".join(missing_dimensions)
                        ),
                        "blocking": True,
                        "resolutionType": "manual-review",
                        "createdAt": now,
                        "resolutionStatus": "open",
                        "suggestedResolution": (
                            "Confirm the missing dimensions with the user before "
                            "component selection."
                        ),
                    }
                )

            component_plan_art = await self._compose_component_plan(
                architecture_content=arch_art["content"],
                requirement_set_content=req_art["content"],
                project_id=project_id,
                turn_id=turn_id,
                run_id=run_id,
                now=now,
                vera_actor=vera_actor,
                ledger=ledger,
            )

            electrical_art = self._compose_electrical_architecture(
                architecture_content=arch_art["content"],
                component_plan_content=component_plan_art["content"],
                project_id=project_id,
                turn_id=turn_id,
                run_id=run_id,
                now=now,
                vera_actor=vera_actor,
                ledger=ledger,
            )

            physical_art = self._compose_physical_architecture(
                electrical_content=electrical_art["content"],
                architecture_content=arch_art["content"],
                project_id=project_id,
                turn_id=turn_id,
                run_id=run_id,
                now=now,
                vera_actor=vera_actor,
                ledger=ledger,
            )

            step = ledger.start_step("derive-next-action")
            next_content = select_next_action(
                issues=issues,
                open_questions=open_questions,
                missing_dimensions=missing_dimensions,
                project_stage=stage,
                component_plan_content=component_plan_art.get("content"),
                electrical_content=electrical_art.get("content"),
                physical_content=physical_art.get("content"),
            )
            next_art_id = new_id("art_")
            next_art = {
                "schemaVersion": "1.0.0",
                "artifactId": next_art_id,
                "projectId": project_id,
                "artifactType": "next-action",
                "artifactVersion": 1,
                "contentSchemaVersion": "1.0.0",
                "lifecycleStatus": "ready",
                "evidenceStatus": "inferred",
                "approvalStatus": "proposed",
                "createdBy": vera_actor,
                "createdAt": now,
                "updatedAt": now,
                "sourceTurnId": turn_id,
                "workflowRunId": run_id,
                "content": next_content,
            }
            ledger.complete_step(
                step,
                output_artifact_references=[_ref(next_art)],
            )

            artifacts = [
                brief_art,
                req_art,
                arch_art,
                component_plan_art,
                electrical_art,
                physical_art,
                next_art,
            ]
            created_refs = [_ref(a) for a in artifacts]
            warning_issues = [i for i in issues if not i.get("blocking")]
            blocker_issues = [i for i in issues if i.get("blocking")]

            step = ledger.start_step("compose-vera-response")
            vera = compose_vera_response_deterministic(
                turn_id=turn_id,
                project_id=project_id,
                project_phase=stage,
                autonomy_mode=autonomy_mode,
                created_artifact_references=created_refs,
                warning_issues=warning_issues,
                blocker_issues=blocker_issues,
                open_questions=open_questions,
                next_action_reference=_ref(next_art),
                next_action_title=next_content["title"],
                completion_status=("completed-with-warnings" if issues else "completed"),
            )
            ledger.complete_step(step)

            step = ledger.start_step("assemble-result")
            # Update project current refs / open questions / blockers.
            shell["project"]["currentArtifactReferences"] = created_refs
            shell["project"]["openQuestionReferences"] = [
                {
                    "schemaVersion": "1.0.0",
                    "questionId": q["questionId"],
                    **({"displayId": q["_displayId"]} if q.get("_displayId") else {}),
                }
                for q in open_questions
            ]
            shell["project"]["blockerOrValidationIssueReferences"] = [
                {"issueId": i["issueId"]} for i in blocker_issues
            ]
            public_questions = [
                {k: v for k, v in q.items() if not k.startswith("_")} for q in open_questions
            ]
            result = {
                "schemaVersion": "1.0.0",
                "project": shell["project"],
                "userTurn": shell["userTurn"],
                "turnRoute": shell["turnRoute"],
                "workflowRun": ledger.to_workflow_run(),
                "artifacts": artifacts,
                "validationIssues": issues,
                "openQuestions": public_questions,
                "veraResponse": vera,
            }
            ledger.complete_step(step, output_artifact_references=created_refs)

            step = ledger.start_step("validate-complete-package")
            result["workflowRun"] = ledger.to_workflow_run()
            schema_errors = validate_initialization_result_schema(result)
            if not schema_errors:
                result["project"]["executionPlan"] = compose_execution_plan(result)
                schema_errors = validate_initialization_result_schema(result)
            if schema_errors:
                ledger.fail_step(step)
                logger.error(
                    "llm_package_schema_validation_failed request_id=%s errors=%s",
                    request_id,
                    schema_errors[:20],
                )
                raise LlmInitializationError(
                    code="LLM_INITIALIZATION_VALIDATION_FAILED",
                    message="Assembled LLM package failed schema validation.",
                    workflow_run=ledger.to_workflow_run(),
                    details=schema_errors[:20],
                )
            semantic = validate_initialization_package(
                initialization_dict_to_package_bundle(result)
            )
            blocking = [e for e in semantic if getattr(e, "blocking", True)]
            if blocking:
                ledger.fail_step(step)
                codes = sorted({e.code for e in blocking})
                logger.error(
                    "llm_package_semantic_validation_failed request_id=%s codes=%s",
                    request_id,
                    codes,
                )
                raise LlmInitializationError(
                    code="LLM_INITIALIZATION_VALIDATION_FAILED",
                    message="Assembled LLM package failed semantic validation.",
                    workflow_run=ledger.to_workflow_run(),
                    details=codes,
                )
            ledger.complete_step(step)

            step = ledger.start_step("complete-workflow")
            ledger.complete_step(step, output_artifact_references=created_refs)
            ledger.finish_success()
            result["workflowRun"] = ledger.to_workflow_run()

            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "llm_initialization_completed",
                extra={"request_id": request_id, "duration_ms": duration_ms},
            )
            return result
        except LlmInitializationError:
            raise
        except ModelGatewayError as exc:
            raise LlmInitializationError(
                code=exc.code,
                message=exc.message,
                workflow_run=ledger.to_workflow_run() if ledger.step_records else None,
            ) from exc

    async def _interpret(
        self,
        message: str,
        ledger: WorkflowLedger,
        request_id: str | None,
        run_id: str,
    ) -> dict[str, Any]:
        within, reasons = deterministic_boundary_check(message)
        step = ledger.start_step("interpret-project")
        prompt = get_prompt("embedded.project-interpretation.v1")
        result = await self.gateway.generate_structured(
            task_name="interpret-project",
            system_instructions=prompt.system_instructions,
            input_payload={
                "userMessage": message,
                "deterministicBoundaryHints": {
                    "withinBoundary": within,
                    "reasons": reasons,
                },
            },
            output_schema=PROJECT_INTERPRETATION_SCHEMA,
            model_policy=self.model_policy,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
        )
        self.recorder.record_generation(
            GenerationObservation(
                request_id=request_id,
                workflow_run_id=run_id,
                stage="interpret-project",
                provider=result.provider,
                model=result.model,
                duration_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                retry_count=result.retry_count,
                repair_count=0,
                validation_result="success",
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
            )
        )
        interpretation = result.parsed_output
        # Deterministic guard remains authoritative for clear out-of-scope prompts.
        if not within or not interpretation.get("withinBoundary", True):
            ledger.fail_step(step)
            merged_reasons = list(reasons) or list(interpretation.get("unsupportedReasons") or [])
            raise LlmInitializationError(
                code="UNSUPPORTED_EMBEDDED_PROJECT_INITIALIZATION",
                message=(
                    "This prompt is outside the supported embedded-project initialization boundary."
                ),
                workflow_run=ledger.to_workflow_run(),
                details=merged_reasons,
            )
        if not interpretation.get("physicalComputingPresent") or not interpretation.get(
            "embeddedProductPresent"
        ):
            ledger.fail_step(step)
            raise LlmInitializationError(
                code="UNSUPPORTED_EMBEDDED_PROJECT_INITIALIZATION",
                message=(
                    "This prompt does not describe an embedded or physical-computing product."
                ),
                workflow_run=ledger.to_workflow_run(),
            )
        ledger.complete_step(step)
        return interpretation

    async def _generate_brief(self, **kwargs: Any) -> dict[str, Any]:
        return await self._generate_content_artifact(
            step_generate="generate-project-brief",
            step_validate="validate-project-brief",
            step_repair="repair-project-brief",
            prompt_id="embedded.project-brief.v1",
            draft_schema=PROJECT_BRIEF_DRAFT_SCHEMA,
            artifact_type="project-brief",
            normalize=self._normalize_brief,
            **kwargs,
        )

    async def _generate_requirements(
        self, **kwargs: Any
    ) -> tuple[dict[str, Any], dict[str, str], list[str]]:
        local_map: dict[str, str] = {}
        missing: list[str] = []

        def normalize(draft: dict[str, Any], **_kw: Any) -> dict[str, Any]:
            nonlocal local_map, missing
            content, local_map = normalize_requirement_draft(draft, kwargs["turn_id"])
            missing = list(draft.get("missingDimensions") or [])
            return content

        artifact = await self._generate_content_artifact(
            step_generate="generate-requirements",
            step_validate="validate-requirements",
            step_repair="repair-requirements",
            prompt_id="embedded.requirements.v1",
            draft_schema=REQUIREMENT_SET_DRAFT_SCHEMA,
            artifact_type="requirement-set",
            normalize=normalize,
            **kwargs,
        )
        return artifact, local_map, missing

    async def _generate_architecture(self, **kwargs: Any) -> dict[str, Any]:
        return await self._generate_content_artifact(
            step_generate="generate-functional-architecture",
            step_validate="validate-functional-architecture",
            step_repair="repair-functional-architecture",
            prompt_id="embedded.functional-architecture.v1",
            draft_schema=FUNCTIONAL_ARCHITECTURE_DRAFT_SCHEMA,
            artifact_type="functional-architecture",
            normalize=self._normalize_architecture,
            **kwargs,
        )

    def _normalize_brief(self, draft: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return normalize_brief_draft(
            draft,
            kwargs["open_questions"],
            project_id=kwargs["project_id"],
            artifact_id=kwargs["artifact_id"],
            now=kwargs["now"],
            requested_from=kwargs["vera_actor"],
        )

    def _normalize_architecture(self, draft: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return normalize_architecture_draft(
            draft,
            kwargs["local_key_to_req_id"],
            kwargs["open_questions"],
            project_id=kwargs["project_id"],
            artifact_id=kwargs["artifact_id"],
            now=kwargs["now"],
            requested_from=kwargs["vera_actor"],
        )

    async def _compose_component_plan(
        self,
        *,
        architecture_content: dict[str, Any],
        requirement_set_content: dict[str, Any],
        project_id: str,
        turn_id: str,
        run_id: str,
        now: str,
        vera_actor: dict[str, Any],
        ledger: WorkflowLedger,
    ) -> dict[str, Any]:
        """Deterministic Phase 12 Component Plan composition with ledgered steps."""

        step = ledger.start_step("derive-component-roles")
        content = compose_component_plan_content(
            architecture_content=architecture_content,
            requirement_set_content=requirement_set_content,
            include_candidates=True,
            source="inferred",
            proposed_by=vera_actor,
            now=now,
        )
        ledger.complete_step(step)

        step = ledger.start_step("derive-selection-constraints")
        ledger.complete_step(step)

        step = ledger.start_step("propose-component-candidates")
        # Candidates and preferred (unapproved) selections are included at init.
        ledger.complete_step(step)

        step = ledger.start_step("identify-known-compatibility-checks")
        ledger.complete_step(step)

        step = ledger.start_step("propose-preferred-selections")
        ledger.complete_step(step)

        step = ledger.start_step("validate-component-plan")
        arch_ids = {
            node_id
            for node in (architecture_content.get("nodes") or [])
            if isinstance(node, dict)
            for node_id in [node.get("nodeId")]
            if isinstance(node_id, str)
        }
        req_ids = {
            requirement_id
            for req in (requirement_set_content.get("requirements") or [])
            if isinstance(req, dict)
            for requirement_id in [req.get("requirementId")]
            if isinstance(requirement_id, str)
        }
        semantic_errors = validate_component_plan_content(
            content,
            architecture_node_ids=arch_ids,
            requirement_ids=req_ids,
        )
        blocking = [e for e in semantic_errors if getattr(e, "blocking", True)]
        if blocking:
            ledger.fail_step(step)
            codes = sorted({e.code for e in blocking})
            raise LlmInitializationError(
                code="LLM_INITIALIZATION_VALIDATION_FAILED",
                message="Component plan failed semantic validation.",
                workflow_run=ledger.to_workflow_run(),
                details=codes,
            )
        ledger.complete_step(step)

        step = ledger.start_step("materialize-component-plan")
        envelope = compose_component_plan_envelope(
            content=content,
            project_id=project_id,
            turn_id=turn_id,
            workflow_run_id=run_id,
            created_by=vera_actor,
            now=now,
        )
        ledger.complete_step(step, output_artifact_references=[_ref(envelope)])
        return envelope

    def _compose_electrical_architecture(
        self,
        *,
        architecture_content: dict[str, Any],
        component_plan_content: dict[str, Any],
        project_id: str,
        turn_id: str,
        run_id: str,
        now: str,
        vera_actor: dict[str, Any],
        ledger: WorkflowLedger,
    ) -> dict[str, Any]:
        step = ledger.start_step("compose-electrical-architecture")
        content = compose_electrical_architecture_content(
            architecture_content=architecture_content,
            component_plan_content=component_plan_content,
        )
        envelope = compose_electrical_architecture_envelope(
            content=content,
            project_id=project_id,
            turn_id=turn_id,
            workflow_run_id=run_id,
            created_by=vera_actor,
            now=now,
        )
        ledger.complete_step(step, output_artifact_references=[_ref(envelope)])
        return envelope

    def _compose_physical_architecture(
        self,
        *,
        electrical_content: dict[str, Any],
        architecture_content: dict[str, Any],
        project_id: str,
        turn_id: str,
        run_id: str,
        now: str,
        vera_actor: dict[str, Any],
        ledger: WorkflowLedger,
    ) -> dict[str, Any]:
        step = ledger.start_step("compose-physical-architecture")
        project_context = {
            "systemBoundary": architecture_content.get("systemBoundary"),
            "summary": architecture_content.get("summary"),
        }
        content = compose_physical_architecture_content(
            electrical_content=electrical_content,
            project_context=project_context,
        )
        envelope = compose_physical_architecture_envelope(
            content=content,
            project_id=project_id,
            turn_id=turn_id,
            workflow_run_id=run_id,
            created_by=vera_actor,
            now=now,
        )
        ledger.complete_step(step, output_artifact_references=[_ref(envelope)])
        return envelope

    async def _generate_content_artifact(
        self,
        *,
        step_generate: str,
        step_validate: str,
        step_repair: str,
        prompt_id: str,
        draft_schema: dict[str, Any],
        artifact_type: str,
        normalize: Any,
        message: str,
        interpretation: dict[str, Any],
        project_id: str,
        turn_id: str,
        run_id: str,
        now: str,
        vera_actor: dict[str, Any],
        ledger: WorkflowLedger,
        request_id: str | None,
        open_questions: list[dict[str, Any]] | None = None,
        local_key_to_req_id: dict[str, str] | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        prompt = get_prompt(prompt_id)
        step = ledger.start_step(step_generate)
        gen = await self.gateway.generate_structured(
            task_name=step_generate,
            system_instructions=prompt.system_instructions,
            input_payload={
                "userMessage": message,
                "projectInterpretation": interpretation,
            },
            output_schema=draft_schema,
            model_policy=self.model_policy,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
        )
        self.recorder.record_generation(
            GenerationObservation(
                request_id=request_id,
                workflow_run_id=run_id,
                stage=step_generate,
                provider=gen.provider,
                model=gen.model,
                duration_ms=gen.latency_ms,
                input_tokens=gen.input_tokens,
                output_tokens=gen.output_tokens,
                retry_count=gen.retry_count,
                repair_count=0,
                validation_result="success",
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
            )
        )
        draft = gen.parsed_output
        artifact_id = new_id("art_")
        # The draft must pass schema validation before it is safe to hand to
        # `normalize`: normalization assumes every schema-required field is
        # present and will raise KeyError on a malformed draft rather than
        # routing it through bounded repair.
        provisional_ref = {
            "artifactType": artifact_type,
            "artifactId": artifact_id,
            "artifactVersion": 1,
            "contentSchemaVersion": "1.0.0",
        }
        ledger.complete_step(step, output_artifact_references=[provisional_ref])

        def _build_envelope(validated_draft: dict[str, Any]) -> dict[str, Any]:
            content = normalize(
                validated_draft,
                open_questions=open_questions if open_questions is not None else [],
                project_id=project_id,
                artifact_id=artifact_id,
                now=now,
                vera_actor=vera_actor,
                local_key_to_req_id=local_key_to_req_id or {},
                turn_id=turn_id,
            )
            built = artifact_envelope(
                artifact_type=artifact_type,
                content=content,
                project_id=project_id,
                turn_id=turn_id,
                workflow_run_id=run_id,
                created_by=vera_actor,
                now=now,
                lifecycle_status="ready",
            )
            built["artifactId"] = artifact_id
            return built

        step = ledger.start_step(step_validate)
        errors = _validate_content_shape(draft_schema, draft)
        if not errors:
            ledger.complete_step(step)
            return _build_envelope(draft)

        ledger.complete_step(step)  # validation executed; defects found
        # Bounded repair
        attempts = 0
        while attempts < self.max_repair_attempts:
            attempts += 1
            repair_step = ledger.start_step(step_repair)
            try:
                repaired = await repair_artifact(
                    gateway=self.gateway,
                    model_policy=self.model_policy,
                    artifact_name=artifact_type,
                    original_content=draft,
                    validation_codes=["DRAFT_SCHEMA_VALIDATION_FAILED"],
                    validation_messages=errors,
                    output_schema={
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["repairedContent"],
                        "properties": {"repairedContent": draft_schema},
                    },
                    recorder=self.recorder,
                    request_id=request_id,
                    workflow_run_id=run_id,
                )
            except ModelGatewayError as exc:
                ledger.fail_step(repair_step)
                raise LlmInitializationError(
                    code=exc.code,
                    message=exc.message,
                    workflow_run=ledger.to_workflow_run(),
                ) from exc
            draft = repaired
            if not isinstance(draft, dict):
                ledger.fail_step(repair_step)
                raise LlmInitializationError(
                    code="MODEL_STRUCTURED_OUTPUT_INVALID",
                    message="Repair returned non-object content.",
                    workflow_run=ledger.to_workflow_run(),
                )
            errors = _validate_content_shape(draft_schema, draft)
            if errors:
                ledger.fail_step(repair_step)
                continue
            envelope = _build_envelope(draft)
            ledger.complete_step(repair_step, output_artifact_references=[_ref(envelope)])
            return envelope

        raise LlmInitializationError(
            code="LLM_INITIALIZATION_VALIDATION_FAILED",
            message=f"{artifact_type} failed validation after bounded repair.",
            workflow_run=ledger.to_workflow_run(),
            details=errors,
        )


def _ref(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifactType": artifact["artifactType"],
        "artifactId": artifact["artifactId"],
        "artifactVersion": artifact.get("artifactVersion", 1),
        "contentSchemaVersion": artifact.get("contentSchemaVersion", "1.0.0"),
    }


def _validate_content_shape(schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in err.path) or '$'}: {err.message}"
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    ]
