"""CLI entry for embedded component planning evals.

Fake mode uses fixture initialization (or deterministic composition) and never
calls a live model.

Usage:
    python -m evals.embedded_component_planning.runners.run_eval
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from nexus_embedded_systems.workflows.component_planning import compose_component_plan_content
from nexus_embedded_systems.workflows.project_initialization.providers.base import (
    InitializationRequestContext,
)
from nexus_embedded_systems.workflows.project_initialization.providers.fixture_provider import (
    FixtureInitializationProvider,
    FixtureRoutingError,
)
from nexus_contracts.validation.semantic_validators import validate_component_plan_content

from .case_loader import EvalCase, load_all_cases


def _score_component_plan(case: EvalCase, content: dict[str, Any]) -> dict[str, Any]:
    roles = content.get("componentRoles") or []
    candidates = content.get("candidates") or []
    blob = json.dumps(content).casefold()
    forbidden_hits = [term for term in case.forbidden_selections if term.casefold() in blob]
    sensor_ok = (not case.require_sensor_role) or any(
        r.get("category") == "sensor" for r in roles if isinstance(r, dict)
    )
    maturity_ok = (
        case.expected_maturity is None or content.get("maturity") == case.expected_maturity
    )
    tested_forbidden = not any(
        isinstance(c, dict) and c.get("evidenceStatus") == "tested" for c in candidates
    )
    semantic = validate_component_plan_content(content)
    blocking = [e.code for e in semantic if getattr(e, "blocking", True)]
    passed = (
        len(roles) >= case.min_role_count
        and sensor_ok
        and maturity_ok
        and tested_forbidden
        and not forbidden_hits
        and not blocking
    )
    return {
        "roleCount": len(roles),
        "candidateCount": len(candidates),
        "maturity": content.get("maturity"),
        "sensorRolePresent": sensor_ok,
        "maturityMatch": maturity_ok,
        "forbiddenHits": forbidden_hits,
        "blockingCodes": blocking,
        "passed": passed,
    }


async def run_case(case: EvalCase) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "caseId": case.id,
        "suite": case.suite,
        "category": case.category,
        "expectedOutcome": case.expected_outcome,
    }
    provider = FixtureInitializationProvider()
    try:
        result = await provider.initialize(
            case.prompt,
            "collaborate",
            InitializationRequestContext(request_id=f"cp_eval_{case.id}"),
        )
    except FixtureRoutingError as exc:
        match = case.expected_outcome == "unsupported" and (
            case.expected_error_code is None or case.expected_error_code == exc.code
        )
        outcome.update(
            {
                "actualOutcome": "unsupported",
                "errorCode": exc.code,
                "outcomeMatch": match,
                "passed": match,
            }
        )
        return outcome

    if case.expected_outcome == "unsupported":
        outcome.update({"actualOutcome": "supported", "outcomeMatch": False, "passed": False})
        return outcome

    component = next(
        (a for a in result.get("artifacts") or [] if a.get("artifactType") == "component-plan"),
        None,
    )
    if component is None:
        # Fallback: compose from architecture+requirements if fixture somehow omitted it.
        arch = next(
            (
                a
                for a in result.get("artifacts") or []
                if a.get("artifactType") == "functional-architecture"
            ),
            None,
        )
        reqs = next(
            (
                a
                for a in result.get("artifacts") or []
                if a.get("artifactType") == "requirement-set"
            ),
            None,
        )
        if arch is None or reqs is None:
            outcome.update({"actualOutcome": "error", "passed": False})
            return outcome
        content = compose_component_plan_content(
            architecture_content=arch["content"],
            requirement_set_content=reqs["content"],
            include_candidates=False,
        )
    else:
        content = component["content"]

    score = _score_component_plan(case, content)
    outcome.update(
        {
            "actualOutcome": "supported",
            "outcomeMatch": True,
            "score": score,
            "passed": score["passed"],
        }
    )
    return outcome


async def run_all(cases: list[EvalCase]) -> dict[str, Any]:
    results = [await run_case(case) for case in cases]
    passed = sum(1 for r in results if r.get("passed"))
    return {
        "suite": "embedded_component_planning",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "passRate": (passed / len(results)) if results else 0.0,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run embedded component planning evals")
    parser.add_argument("--case", dest="case_id", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    cases = load_all_cases()
    if args.case_id:
        cases = [c for c in cases if c.id == args.case_id]
        if not cases:
            print(f"No case matching {args.case_id}", file=sys.stderr)
            return 2
    report = asyncio.run(run_all(cases))
    text = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
