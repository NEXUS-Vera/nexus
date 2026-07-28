"""CLI entry point for the embedded-project-initialization eval harness.

Fake mode (the default, and the only mode required by `make check`) never
calls a live model: it exercises the real `LlmInitializationProvider`
pipeline (deterministic boundary check, staged generation, deterministic
assembly, and contract validation) against a scripted `FakeModelGateway`
built from each case's expected fields.

Live mode (`--provider llm`) requires `NEXUS_MODEL_API_KEY` and real model
credentials; it is never used by CI or `make check`.

Usage:
    python -m evals.embedded_project_initialization.runners.run_eval
    python -m evals.embedded_project_initialization.runners.run_eval --case golden-wearable-tremor-monitor
    python -m evals.embedded_project_initialization.runners.run_eval --max-cases 3 --output results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from nexus_embedded_systems.workflows.project_initialization.providers.base import (
    InitializationRequestContext,
)
from nexus_embedded_systems.workflows.project_initialization.providers.llm_provider import (
    LlmInitializationError,
    LlmInitializationProvider,
)
from nexus_model_gateway import ModelPolicy

from ..gates import evaluate_gates
from ..scorers.golden_claims import score_claims
from ..scorers.metrics import aggregate_metrics
from ..scorers.structural import score_structural
from .case_loader import EvalCase, load_all_cases
from .fake_provider import build_gateway_for_case

FAKE_MODEL_POLICY = ModelPolicy(provider="fake", model="fake-eval-model")


def _build_provider(provider_mode: str) -> tuple[LlmInitializationProvider, str]:
    if provider_mode == "fake":
        raise ValueError("Fake-mode providers are built per case; call _build_fake_provider.")

    from nexus_embedded_systems.workflows.project_initialization.providers.factory import (
        build_initialization_provider,
    )

    provider = build_initialization_provider("llm")
    if not isinstance(provider, LlmInitializationProvider):
        raise RuntimeError(
            "NEXUS_MODEL_API_KEY (and related NEXUS_MODEL_* settings) are required "
            "to run the eval harness with --provider llm."
        )
    return provider, "llm"


def _build_fake_provider(case: EvalCase) -> LlmInitializationProvider:
    gateway = build_gateway_for_case(case)
    return LlmInitializationProvider(gateway=gateway, model_policy=FAKE_MODEL_POLICY)


async def run_case(case: EvalCase, *, provider_mode: str = "fake") -> dict[str, Any]:
    """Run a single eval case and score its outcome."""

    provider = (
        _build_fake_provider(case) if provider_mode == "fake" else _build_provider(provider_mode)[0]
    )
    context = InitializationRequestContext(request_id=f"eval_{case.id}")

    outcome: dict[str, Any] = {
        "caseId": case.id,
        "suite": case.suite,
        "category": case.category,
        "expectedOutcome": case.expected_outcome,
    }

    try:
        result = await provider.initialize(case.prompt, "collaborate", context)
    except LlmInitializationError as exc:
        actual_outcome = (
            "unsupported" if exc.code == "UNSUPPORTED_EMBEDDED_PROJECT_INITIALIZATION" else "error"
        )
        outcome_match = case.expected_outcome == "unsupported" and (
            case.expected_error_code is None or case.expected_error_code == exc.code
        )
        outcome.update(
            {
                "actualOutcome": actual_outcome,
                "errorCode": exc.code,
                "outcomeMatch": outcome_match,
                "structural": None,
                "claims": None,
                "passed": outcome_match,
            }
        )
        return outcome

    structural = score_structural(result)
    claims = score_claims(case, result)
    outcome_match = case.expected_outcome == "supported"
    outcome.update(
        {
            "actualOutcome": "supported",
            "errorCode": None,
            "outcomeMatch": outcome_match,
            "structural": asdict(structural),
            "claims": asdict(claims),
            "passed": outcome_match and structural.passed and claims.passed,
        }
    )
    return outcome


async def run_cases(cases: list[EvalCase], *, provider_mode: str = "fake") -> list[dict[str, Any]]:
    return [await run_case(case, provider_mode=provider_mode) for case in cases]


def _select_cases(*, case_id: str | None, max_cases: int | None) -> list[EvalCase]:
    cases = load_all_cases()
    if case_id:
        cases = [c for c in cases if c.id == case_id]
    if max_cases is not None:
        cases = cases[:max_cases]
    return cases


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_eval",
        description="Run the embedded-project-initialization evaluation suite.",
    )
    parser.add_argument(
        "--case", dest="case_id", default=None, help="Run only the case with this id."
    )
    parser.add_argument(
        "--max-cases",
        dest="max_cases",
        type=int,
        default=None,
        help="Limit the number of cases run (applied after --case).",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=None,
        help="Write the JSON report to this path in addition to stdout.",
    )
    parser.add_argument(
        "--provider",
        dest="provider",
        choices=["fake", "llm"],
        default="fake",
        help="Model provider mode. 'fake' (default) requires no credentials.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    cases = _select_cases(case_id=args.case_id, max_cases=args.max_cases)
    if not cases:
        print("run_eval: no matching cases found", file=sys.stderr)
        return 1

    results = asyncio.run(run_cases(cases, provider_mode=args.provider))
    metrics = aggregate_metrics(results)
    gate_result = evaluate_gates(results, metrics)

    report = {
        "provider": args.provider,
        "caseCount": len(results),
        "metrics": asdict(metrics),
        "gates": asdict(gate_result),
        "results": results,
    }
    payload = json.dumps(report, indent=2, sort_keys=True)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")

    print(payload)
    return 0 if gate_result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
