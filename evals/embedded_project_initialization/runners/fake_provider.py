"""Deterministic fake-mode model gateway wiring for the eval harness.

Fake mode never calls a live model. Each case's expected fields (explicit
claims, missing dimensions, forbidden selections) are used to script
plausible, schema-valid drafts so the real `LlmInitializationProvider`
pipeline (boundary check, staged generation, deterministic assembly, and
validation) can be exercised end to end without credentials. This is a
harness concern only: it intentionally does not attempt to simulate an
actual model's judgment, only the shape of its output.
"""

from __future__ import annotations

from typing import Any

from nexus_model_gateway import FakeModelGateway

from .case_loader import EvalCase


def _claims_or_prompt(case: EvalCase) -> list[str]:
    return list(case.expected_explicit_claims) or [case.prompt[:120]]


def interpretation_for_case(case: EvalCase) -> dict[str, Any]:
    claims = _claims_or_prompt(case)
    if case.expected_outcome == "unsupported":
        return {
            "withinBoundary": False,
            "supportedDomain": False,
            "projectStage": "unsupported",
            "primaryGoal": case.prompt[:120],
            "physicalComputingPresent": False,
            "embeddedProductPresent": False,
            "candidateProjectTitle": "Unsupported request",
            "explicitUserClaims": claims,
            "likelyMissingDimensions": [],
            "unsupportedReasons": [
                f"Case '{case.id}' is scripted as out of the initialization boundary."
            ],
        }
    return {
        "withinBoundary": True,
        "supportedDomain": True,
        "projectStage": "concept",
        "primaryGoal": claims[0],
        "physicalComputingPresent": True,
        "embeddedProductPresent": True,
        "candidateProjectTitle": case.category.replace("-", " ").title(),
        "explicitUserClaims": claims,
        "likelyMissingDimensions": list(case.expected_missing_dimensions),
        "unsupportedReasons": [],
    }


def brief_for_case(case: EvalCase) -> dict[str, Any]:
    claims = _claims_or_prompt(case)
    # Deliberately grounded in the extracted claims only, never the raw
    # prompt: a well-behaved generation stage analyzes user content instead
    # of reproducing it verbatim, which also keeps injected instructions in
    # adversarial prompts out of structured output content.
    return {
        "goal": claims[0],
        "problemStatement": f"Addresses the following stated needs: {'; '.join(claims)}.",
        "intendedContext": f"Grounded in the user's stated project context: {'; '.join(claims)}.",
        "projectStage": "concept",
        "scope": claims,
        "outOfScope": [],
        "successCriteria": [f"Delivers on the stated need: {claim}." for claim in claims],
        "assumptions": [],
        "unknownStatements": [
            f"The {dimension} is unspecified." for dimension in case.expected_missing_dimensions
        ],
    }


def requirements_for_case(case: EvalCase) -> tuple[dict[str, Any], tuple[str, ...]]:
    claims = _claims_or_prompt(case)
    requirements: list[dict[str, Any]] = []
    local_keys: list[str] = []
    for index, claim in enumerate(claims, start=1):
        local_key = f"req-{index}"
        local_keys.append(local_key)
        requirements.append(
            {
                "localRequirementKey": local_key,
                "statement": f"The system must address the stated need: {claim}.",
                "category": "functional",
                "priority": "must",
                "sourceType": "user-explicit",
                "confidence": "high",
                "confirmationStatus": "confirmed",
                "verificationMethod": "Manual review against the stated need.",
            }
        )
    draft = {
        "requirements": requirements,
        "requirementSummary": f"Requirements derived from eval case {case.id}.",
        "missingDimensions": list(case.expected_missing_dimensions),
    }
    return draft, tuple(local_keys)


def architecture_for_case(case: EvalCase, local_keys: tuple[str, ...]) -> dict[str, Any]:
    keys = list(local_keys) or ["req-1"]
    return {
        "systemBoundary": f"Functional boundary scripted for eval case {case.id}.",
        "nodes": [
            {
                "localNodeKey": "node-core",
                "name": "Core Processing",
                "functionalType": "processing",
                "responsibilities": [f"Fulfill the requirement(s) traced to: {', '.join(keys)}."],
                "satisfiesLocalRequirementKeys": keys,
            },
        ],
        "edges": [
            {
                "localEdgeKey": "edge-self",
                "fromLocalNodeKey": "node-core",
                "toLocalNodeKey": "node-core",
                "flowType": "control",
                "description": "Internal control loop within the core processing node.",
            },
        ],
        "assumptions": [],
        "unresolvedDecisionStatements": [],
        "requirementCoverageLocalKeys": keys,
    }


def build_gateway_for_case(case: EvalCase) -> FakeModelGateway:
    """Build a `FakeModelGateway` scripted from a single eval case's expectations."""

    gateway = FakeModelGateway()
    gateway.set_script("interpret-project", lambda *_a: interpretation_for_case(case))

    requirements_draft, local_keys = requirements_for_case(case)
    gateway.set_script("generate-project-brief", lambda *_a: brief_for_case(case))
    gateway.set_script("generate-requirements", lambda *_a: requirements_draft)
    gateway.set_script(
        "generate-functional-architecture",
        lambda *_a: architecture_for_case(case, local_keys),
    )
    return gateway
