"""Reusable `FakeModelGateway` script builders for LLM-provider unit tests.

Every function here returns a plain dict (or `ModelGatewayError`) shaped to
match the draft schemas in `generation/schemas.py`, or a `Script` callable
suitable for `FakeModelGateway.set_script`. Nothing here talks to a real
model; these are deterministic stand-ins for `generate_structured` output
used to exercise `LlmInitializationProvider` without live credentials.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nexus_model_gateway import FakeModelGateway, ModelGatewayError

Script = Callable[[str, dict[str, object], dict[str, object]], "dict[str, Any] | ModelGatewayError"]

WEARABLE_TREMOR_PROMPT = (
    "I want to build a wrist-worn device that measures hand tremors "
    "and records the motion data for later analysis."
)

SOFTWARE_ONLY_PROMPT = "Build me a web app for tracking personal expenses."

DEFAULT_LOCAL_REQUIREMENT_KEYS: tuple[str, ...] = (
    "req-sense-motion",
    "req-log-data",
    "req-battery-life",
)


def interpretation_within_boundary(
    *,
    candidate_title: str = "Wearable Tremor Monitor",
    explicit_claims: list[str] | None = None,
    missing_dimensions: list[str] | None = None,
    project_stage: str = "concept",
) -> dict[str, Any]:
    """A within-boundary interpretation for a wearable tremor-style prompt."""

    return {
        "withinBoundary": True,
        "supportedDomain": True,
        "projectStage": project_stage,
        "primaryGoal": "Measure and record hand tremor motion data for later analysis.",
        "physicalComputingPresent": True,
        "embeddedProductPresent": True,
        "candidateProjectTitle": candidate_title,
        "explicitUserClaims": explicit_claims
        or [
            "wrist-worn device",
            "measures hand tremors",
            "records the motion data for later analysis",
        ],
        "likelyMissingDimensions": missing_dimensions
        or [
            "battery life target",
            "connectivity requirements",
        ],
        "unsupportedReasons": [],
    }


def interpretation_unsupported_software(*, reasons: list[str] | None = None) -> dict[str, Any]:
    """An out-of-boundary interpretation for a software-only prompt."""

    return {
        "withinBoundary": False,
        "supportedDomain": False,
        "projectStage": "unsupported",
        "primaryGoal": "Track personal expenses in a web application.",
        "physicalComputingPresent": False,
        "embeddedProductPresent": False,
        "candidateProjectTitle": "Unsupported software-only request",
        "explicitUserClaims": ["web app", "tracking personal expenses"],
        "likelyMissingDimensions": [],
        "unsupportedReasons": reasons
        or [
            "This prompt describes a software-only product with no embedded "
            "or physical-computing element."
        ],
    }


def project_brief_draft(
    *,
    goal: str = "Measure and record hand tremor motion for later review.",
    scope: list[str] | None = None,
    success_criteria: list[str] | None = None,
    unknown_statements: list[str] | None = None,
) -> dict[str, Any]:
    """A valid draft matching `PROJECT_BRIEF_DRAFT_SCHEMA`."""

    return {
        "goal": goal,
        "problemStatement": (
            "People experiencing hand tremors need an easy way to capture "
            "motion data outside a clinical setting."
        ),
        "intendedContext": (
            "Worn on the wrist during daily activities to capture naturalistic tremor motion."
        ),
        "projectStage": "concept",
        "scope": scope
        or ["Sense wrist motion", "Record motion data", "Support later offline analysis"],
        "outOfScope": ["Real-time diagnosis", "Clinical certification"],
        "successCriteria": success_criteria
        or [
            "Captures motion data usable for later tremor analysis",
            "Comfortable for daily wrist wear",
        ],
        "assumptions": [
            {
                "statement": "The user will review recorded data outside the device.",
                "sourceType": "system-inferred",
                "confidence": "medium",
                "confirmationStatus": "proposed",
            },
        ],
        "unknownStatements": (
            unknown_statements
            if unknown_statements is not None
            else ["The required battery life is unspecified."]
        ),
    }


def invalid_brief_missing_success_criteria() -> dict[str, Any]:
    """An invalid brief draft: missing the required `successCriteria` field."""

    draft = project_brief_draft()
    del draft["successCriteria"]
    return draft


def requirement_set_draft(
    *,
    local_keys: tuple[str, ...] = DEFAULT_LOCAL_REQUIREMENT_KEYS,
    missing_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """A valid draft matching `REQUIREMENT_SET_DRAFT_SCHEMA` with mixed sourceTypes."""

    return {
        "requirements": [
            {
                "localRequirementKey": local_keys[0],
                "statement": "The device must sense wrist motion consistent with hand tremors.",
                "category": "functional",
                "priority": "must",
                "sourceType": "user-explicit",
                "confidence": "high",
                "confirmationStatus": "confirmed",
                "verificationMethod": "Bench test against a known tremor stimulus.",
            },
            {
                "localRequirementKey": local_keys[1],
                "statement": "The device must record motion data for later analysis.",
                "category": "functional",
                "priority": "must",
                "sourceType": "user-implied",
                "confidence": "high",
                "confirmationStatus": "confirmed",
                "verificationMethod": "Verify recorded data can be exported and reviewed.",
            },
            {
                "localRequirementKey": local_keys[2],
                "statement": (
                    "The device should operate for a full day of typical use on battery power."
                ),
                "category": "resource",
                "priority": "should",
                "sourceType": "system-inferred",
                "confidence": "medium",
                "confirmationStatus": "needs-confirmation",
                "verificationMethod": "Measure battery life under representative use.",
            },
        ],
        "requirementSummary": (
            "Core sensing, logging, and power requirements for a wrist-worn tremor monitor."
        ),
        "missingDimensions": (
            missing_dimensions
            if missing_dimensions is not None
            else ["battery life target", "connectivity requirements"]
        ),
    }


def functional_architecture_draft(
    *,
    local_keys: tuple[str, ...] = DEFAULT_LOCAL_REQUIREMENT_KEYS,
    leak_components: bool = False,
) -> dict[str, Any]:
    """A valid draft matching `FUNCTIONAL_ARCHITECTURE_DRAFT_SCHEMA`.

    When `leak_components` is True, node responsibilities name specific parts
    (ESP32, BMI270) to exercise component-leakage detection in tests.
    """

    sensing_responsibilities = ["Detect wrist motion characteristic of hand tremors."]
    if leak_components:
        sensing_responsibilities = [
            "Use an ESP32 microcontroller with a BMI270 IMU to detect wrist motion."
        ]

    return {
        "systemBoundary": (
            "A wrist-worn sensing unit that captures motion and stores it for later analysis."
        ),
        "nodes": [
            {
                "localNodeKey": "node-sensing",
                "name": "Motion Sensing",
                "functionalType": "sensing",
                "responsibilities": sensing_responsibilities,
                "satisfiesLocalRequirementKeys": [local_keys[0]],
            },
            {
                "localNodeKey": "node-processing",
                "name": "Motion Processing",
                "functionalType": "processing",
                "responsibilities": ["Process raw motion samples into a storable representation."],
                "satisfiesLocalRequirementKeys": [local_keys[0], local_keys[1]],
            },
            {
                "localNodeKey": "node-storage",
                "name": "Data Storage",
                "functionalType": "storage",
                "responsibilities": ["Store processed motion data for later analysis."],
                "satisfiesLocalRequirementKeys": [local_keys[1]],
            },
            {
                "localNodeKey": "node-power",
                "name": "Power Management",
                "functionalType": "power",
                "responsibilities": ["Supply and manage battery power for the device."],
                "satisfiesLocalRequirementKeys": [local_keys[2]],
            },
        ],
        "edges": [
            {
                "localEdgeKey": "edge-1",
                "fromLocalNodeKey": "node-sensing",
                "toLocalNodeKey": "node-processing",
                "flowType": "data",
                "description": "Raw motion samples flow from sensing to processing.",
            },
            {
                "localEdgeKey": "edge-2",
                "fromLocalNodeKey": "node-processing",
                "toLocalNodeKey": "node-storage",
                "flowType": "data",
                "description": "Processed motion data flows from processing to storage.",
            },
            {
                "localEdgeKey": "edge-3",
                "fromLocalNodeKey": "node-power",
                "toLocalNodeKey": "node-sensing",
                "flowType": "power",
                "description": "Power flows from power management to the sensing subsystem.",
            },
        ],
        "assumptions": [
            {
                "statement": "The device is worn continuously during waking hours.",
                "sourceType": "user-implied",
                "confidence": "medium",
                "confirmationStatus": "proposed",
            },
        ],
        "unresolvedDecisionStatements": [],
        "requirementCoverageLocalKeys": list(local_keys),
    }


def component_leaking_architecture_draft(
    *, local_keys: tuple[str, ...] = DEFAULT_LOCAL_REQUIREMENT_KEYS
) -> dict[str, Any]:
    """A schema-valid but policy-violating draft naming specific components."""

    return functional_architecture_draft(local_keys=local_keys, leak_components=True)


def repair_success_script(repaired_content: dict[str, Any]) -> Script:
    """A repair script that always succeeds with the given fixed content."""

    def _script(
        _task_name: str, _input_payload: dict[str, object], _output_schema: dict[str, object]
    ) -> dict[str, Any]:
        return {"repairedContent": repaired_content}

    return _script


def repair_still_invalid_script(invalid_content: dict[str, Any]) -> Script:
    """A repair script that returns content which still fails draft validation."""

    def _script(
        _task_name: str, _input_payload: dict[str, object], _output_schema: dict[str, object]
    ) -> dict[str, Any]:
        return {"repairedContent": invalid_content}

    return _script


def repair_malformed_script() -> Script:
    """A repair script returning a payload with no usable `repairedContent`."""

    def _script(
        _task_name: str, _input_payload: dict[str, object], _output_schema: dict[str, object]
    ) -> dict[str, Any]:
        return {"repairedContent": "not-an-object"}

    return _script


def transport_error_script(
    *,
    code: str = "MODEL_PROVIDER_UNAVAILABLE",
    message: str = "Model provider unavailable.",
) -> Script:
    """A script that always raises a transport-level `ModelGatewayError`."""

    def _script(
        _task_name: str, _input_payload: dict[str, object], _output_schema: dict[str, object]
    ) -> ModelGatewayError:
        return ModelGatewayError(code=code, message=message, provider="fake", model="fake-model")

    return _script


def build_success_gateway(
    *,
    interpretation: dict[str, Any] | None = None,
    brief: dict[str, Any] | None = None,
    requirements: dict[str, Any] | None = None,
    architecture: dict[str, Any] | None = None,
) -> FakeModelGateway:
    """Build a `FakeModelGateway` scripted for an end-to-end successful run."""

    gateway = FakeModelGateway()
    gateway.set_script(
        "interpret-project", lambda *_a: interpretation or interpretation_within_boundary()
    )
    gateway.set_script("generate-project-brief", lambda *_a: brief or project_brief_draft())
    gateway.set_script("generate-requirements", lambda *_a: requirements or requirement_set_draft())
    gateway.set_script(
        "generate-functional-architecture",
        lambda *_a: architecture or functional_architecture_draft(),
    )
    return gateway
