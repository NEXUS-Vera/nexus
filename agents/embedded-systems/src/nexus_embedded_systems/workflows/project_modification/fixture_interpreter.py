"""Fixture-mode deterministic project change interpretation."""

from __future__ import annotations

import re
from typing import Any

from .impact import analyze_impact

SUPPORTED_OPS = {
    "clarify-requirement",
    "add-requirement",
    "change-requirement",
    "remove-proposed-requirement",
    "answer-open-question",
    "change-project-scope",
}


class FixtureModificationError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_RUNTIME = re.compile(
    r"(?i)\b(run|operate|operating|runtime|battery|power).{0,40}"
    r"(six|6|eight|8|twelve|12|\d+)\s*(month|months|hour|hours|day|days)\b"
    r"|\b(six|6|eight|8)\s*(month|months|hour|hours).{0,20}(battery|runtime|power)\b"
)
_ACCURACY = re.compile(r"(?i)\b(accuracy|error bound|tolerance|\±|\+/-)\b")
_SAMPLING = re.compile(r"(?i)\b(sampl(e|ing)\s*rate|hz|hertz)\b")
_ENVIRONMENT = re.compile(r"(?i)\b(indoor|outdoor|ingress|ip[0-9]{2}|temperature range)\b")
_COMM = re.compile(r"(?i)\b(wifi|wi-?fi|ble|bluetooth|lora|mqtt|cellular)\b")
_SIZE = re.compile(r"(?i)\b(size|weight|form factor|footprint|compact)\b")
_BUDGET = re.compile(r"(?i)\b(budget|cost|bom|price|\$)\b")
_REJECT = re.compile(
    r"(?i)\b(reject|remove|drop|do not (need|want)|cancel)\b.{0,40}\b(requirement|proposed)\b"
)
_ANSWER_RUNTIME_Q = re.compile(
    r"(?i)\b(minimum|at least|should).{0,30}(runtime|operating time|battery).{0,20}"
    r"(\d+|eight|six|twelve)\s*(hour|hours|month|months)\b"
    r"|\b(\d+|eight|six|twelve)\s*(hour|hours).{0,20}(runtime|battery|operating)\b"
)


def interpret_fixture_change(
    message: str,
    *,
    source_turn_id: str,
    current_state: dict[str, Any],
) -> dict[str, Any]:
    text = message.strip()
    requirements = _requirements(current_state)
    questions = current_state.get("openQuestions") or []

    # Open-question answers first (runtime).
    if _ANSWER_RUNTIME_Q.search(text) or (
        _RUNTIME.search(text) and any(_looks_runtime_question(q) for q in questions)
    ):
        q = next(
            (q for q in questions if _looks_runtime_question(q) and q.get("status") == "open"), None
        )
        if q is None and _RUNTIME.search(text):
            # Treat as add/change runtime requirement even without an open Q.
            return _intent(
                operation="add-requirement",
                target_artifact_type="requirement-set",
                requested_change=text,
                source_turn_id=source_turn_id,
                confidence="high",
                category="runtime",
                extra={"pattern": "runtime"},
            )
        return _intent(
            operation="answer-open-question",
            target_artifact_type="requirement-set",
            requested_change=text,
            source_turn_id=source_turn_id,
            confidence="high",
            category="runtime",
            target_question_id=q["questionId"] if q else None,
            extra={"pattern": "answer-runtime-question"},
        )

    if _RUNTIME.search(text):
        matches = [
            r
            for r in requirements
            if _req_matches_category(r, "runtime") or _req_mentions_runtime(r)
        ]
        if len(matches) > 1:
            raise FixtureModificationError(
                code="AMBIGUOUS_PROJECT_CHANGE_TARGET",
                message=(
                    "Multiple runtime-related requirements match. "
                    "Clarify which requirement to update."
                ),
            )
        target = matches[0]["requirementId"] if len(matches) == 1 else None
        op = "change-requirement" if target else "add-requirement"
        return _intent(
            operation=op,
            target_artifact_type="requirement-set",
            requested_change=text,
            source_turn_id=source_turn_id,
            confidence="high",
            category="runtime",
            target_requirement_id=target,
            extra={"pattern": "runtime"},
        )

    if _REJECT.search(text):
        proposed = [r for r in requirements if r.get("confirmationStatus") == "proposed"]
        if len(proposed) == 0:
            raise FixtureModificationError(
                code="REQUIREMENT_NOT_FOUND",
                message="No proposed requirement is available to reject.",
            )
        if len(proposed) > 1:
            raise FixtureModificationError(
                code="AMBIGUOUS_PROJECT_CHANGE_TARGET",
                message=(
                    "Multiple proposed requirements match. "
                    "Specify which proposed requirement to reject."
                ),
            )
        return _intent(
            operation="remove-proposed-requirement",
            target_artifact_type="requirement-set",
            requested_change=text,
            source_turn_id=source_turn_id,
            confidence="high",
            category=str(proposed[0].get("category") or "other"),
            target_requirement_id=proposed[0]["requirementId"],
            extra={"pattern": "reject-proposed"},
        )

    for pattern, category, op in (
        (_ACCURACY, "accuracy", "clarify-requirement"),
        (_SAMPLING, "sampling", "change-requirement"),
        (_ENVIRONMENT, "environmental", "change-requirement"),
        (_COMM, "communication", "change-requirement"),
        (_SIZE, "size", "change-requirement"),
        (_BUDGET, "budget", "change-requirement"),
    ):
        if pattern.search(text):
            matches = [r for r in requirements if _req_matches_category(r, category)]
            # Also match open accuracy questions.
            if category == "accuracy":
                q = next(
                    (
                        q
                        for q in questions
                        if q.get("status") == "open" and "accuracy" in q.get("question", "").lower()
                    ),
                    None,
                )
                if q is not None:
                    return _intent(
                        operation="answer-open-question",
                        target_artifact_type="requirement-set",
                        requested_change=text,
                        source_turn_id=source_turn_id,
                        confidence="high",
                        category="accuracy",
                        target_question_id=q["questionId"],
                        extra={"pattern": "answer-accuracy-question"},
                    )
            if len(matches) > 1:
                raise FixtureModificationError(
                    code="AMBIGUOUS_PROJECT_CHANGE_TARGET",
                    message=(
                        f"Multiple {category} requirements match. Clarify the target requirement."
                    ),
                )
            target = matches[0]["requirementId"] if len(matches) == 1 else None
            return _intent(
                operation=op if target else "add-requirement",
                target_artifact_type="requirement-set",
                requested_change=text,
                source_turn_id=source_turn_id,
                confidence="medium",
                category=category,
                target_requirement_id=target,
                extra={"pattern": category},
            )

    raise FixtureModificationError(
        code="UNSUPPORTED_PROJECT_MODIFICATION_FOR_FIXTURE_PHASE",
        message=(
            "Fixture mode cannot interpret this modification. "
            "Supported examples include runtime/battery constraints, accuracy answers, "
            "sampling rate, environment, communication, size/weight, budget, "
            "and rejecting a proposed requirement."
        ),
    )


def impact_for_intent(intent: dict[str, Any]) -> dict[str, Any]:
    category = (intent.get("_meta") or {}).get("category")
    categories = [category] if category else []
    semantic = intent["operation"] != "clarify-requirement" or category in {
        "runtime",
        "power",
        "communication",
    }
    # Wording-only clarify without architecture categories leaves architecture unchanged.
    if intent["operation"] == "clarify-requirement" and category in {"accuracy"}:
        semantic = False
    return analyze_impact(
        operation=intent["operation"],
        requirement_categories=categories,
        semantic_change=semantic,
        architecture_coverage_changed=intent["operation"] == "remove-proposed-requirement",
    )


def _intent(
    *,
    operation: str,
    target_artifact_type: str | None,
    requested_change: str,
    source_turn_id: str,
    confidence: str,
    category: str,
    target_requirement_id: str | None = None,
    target_question_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intent: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "operation": operation,
        "targetArtifactType": target_artifact_type,
        "requestedChange": requested_change,
        "sourceTurnId": source_turn_id,
        "confidence": confidence,
        "ambiguities": [],
        "requiresUserConfirmation": False,
        "_meta": {"category": category, **(extra or {})},
    }
    if target_requirement_id:
        intent["targetRequirementId"] = target_requirement_id
    if target_question_id:
        intent["targetQuestionId"] = target_question_id
    return intent


def _requirements(state: dict[str, Any]) -> list[dict[str, Any]]:
    for art in state.get("artifacts") or []:
        if art.get("artifactType") == "requirement-set":
            return list(art.get("content", {}).get("requirements") or [])
    return []


def _req_matches_category(req: dict[str, Any], category: str) -> bool:
    raw = str(req.get("category", "")).lower()
    statement = str(req.get("statement", "")).lower()
    if category == "runtime":
        return raw in {"resource", "performance"} or _req_mentions_runtime(req)
    if category == "accuracy":
        return "accur" in statement or raw == "performance"
    if category == "sampling":
        return "sampl" in statement or raw == "performance"
    if category == "communication":
        return raw == "interface" or any(t in statement for t in ("wifi", "ble", "mqtt", "radio"))
    if category == "size":
        return raw == "physical"
    if category == "budget":
        return raw == "project-constraint" or "budget" in statement or "cost" in statement
    return raw == category.lower()


def _req_mentions_runtime(req: dict[str, Any]) -> bool:
    statement = str(req.get("statement", "")).lower()
    return any(token in statement for token in ("runtime", "battery", "power", "operate"))


def _looks_runtime_question(question: dict[str, Any]) -> bool:
    text = f"{question.get('question', '')} {question.get('reason', '')}".lower()
    return any(token in text for token in ("runtime", "battery", "operating time", "power budget"))
