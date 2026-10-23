"""Eval harness tests (fake gateway only; no live credentials required)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from evals.embedded_project_initialization.gates import evaluate_gates
from evals.embedded_project_initialization.runners.case_loader import (
    EvalCase,
    load_adversarial_cases,
    load_all_cases,
    load_golden_cases,
)
from evals.embedded_project_initialization.runners.run_eval import (
    build_arg_parser,
    main,
    run_case,
    run_cases,
)
from evals.embedded_project_initialization.scorers.metrics import aggregate_metrics

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_golden_cases_load_five_families() -> None:
    cases = load_golden_cases()
    assert len(cases) == 5
    assert all(case.suite == "golden" for case in cases)
    assert all(case.expected_outcome == "supported" for case in cases)
    assert len({case.category for case in cases}) == 5


def test_adversarial_cases_cover_all_expected_categories() -> None:
    cases = load_adversarial_cases()
    categories = {case.category for case in cases}
    assert categories == {
        "software",
        "component-selection",
        "debugging",
        "multi-product",
        "ambiguous",
        "numeric",
        "contradictory",
        "fixed-component",
        "sparse",
        "prompt-injection",
        "p1-intent",
        "p1-scope",
    }
    assert all(case.suite == "adversarial" for case in cases)


def test_load_all_cases_combines_both_suites() -> None:
    assert len(load_all_cases()) == len(load_golden_cases()) + len(load_adversarial_cases())


async def test_golden_case_passes_in_fake_mode() -> None:
    case = next(c for c in load_golden_cases() if c.id == "golden-wearable-tremor-monitor")
    result = await run_case(case)
    assert result["passed"] is True
    assert result["actualOutcome"] == "supported"
    assert result["structural"]["passed"] is True
    assert result["claims"]["passed"] is True


@pytest.mark.parametrize(
    "case_id",
    [
        "adversarial-software",
        "adversarial-component-selection",
        "adversarial-debugging",
        "adversarial-multi-product",
    ],
)
async def test_unsupported_adversarial_cases_are_rejected(case_id: str) -> None:
    case = next(c for c in load_adversarial_cases() if c.id == case_id)
    result = await run_case(case)
    assert result["actualOutcome"] == "unsupported"
    assert result["errorCode"] == "UNSUPPORTED_EMBEDDED_PROJECT_INITIALIZATION"
    assert result["passed"] is True


async def test_prompt_injection_case_does_not_leak_forbidden_components() -> None:
    case = next(c for c in load_adversarial_cases() if c.id == "adversarial-prompt-injection")
    result = await run_case(case)
    assert result["actualOutcome"] == "supported"
    assert result["claims"]["forbidden_hits"] == ()
    assert result["passed"] is True


async def test_fixed_component_case_allows_user_named_component_only() -> None:
    case = next(c for c in load_adversarial_cases() if c.id == "adversarial-fixed-component")
    result = await run_case(case)
    assert result["passed"] is True
    assert result["claims"]["forbidden_hits"] == ()


async def test_full_suite_passes_all_quality_gates_in_fake_mode() -> None:
    cases = load_all_cases()
    results = await run_cases(cases)
    metrics = aggregate_metrics(results)
    gate_result = evaluate_gates(results, metrics)

    assert metrics.total == len(cases)
    assert gate_result.passed is True, gate_result.failures
    assert metrics.pass_rate == 1.0
    assert metrics.outcome_match_rate == 1.0


async def test_llm_provider_mode_is_rejected_without_credentials() -> None:
    from evals.embedded_project_initialization.runners.case_loader import EvalCase

    case = EvalCase(
        id="unused",
        suite="golden",
        category="unused",
        prompt="unused",
        expected_outcome="supported",
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("NEXUS_MODEL_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="NEXUS_MODEL_API_KEY"):
            await run_case(case, provider_mode="llm")


def test_gates_fail_on_incomplete_run() -> None:
    metrics = aggregate_metrics([])
    gate_result = evaluate_gates([], metrics)
    assert gate_result.passed is False
    assert any("No eval cases" in failure for failure in gate_result.failures)


def test_gates_fail_when_forbidden_hit_present() -> None:
    results = [
        {
            "caseId": "case-1",
            "category": "x",
            "passed": False,
            "outcomeMatch": True,
            "structural": {"passed": True},
            "claims": {"passed": False, "forbidden_hits": ("ESP32",)},
        }
    ]
    metrics = aggregate_metrics(results)
    gate_result = evaluate_gates(results, metrics)
    assert gate_result.passed is False
    assert any("Forbidden component" in failure for failure in gate_result.failures)


def test_arg_parser_defaults_to_fake_provider() -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.provider == "fake"
    assert args.case_id is None
    assert args.max_cases is None
    assert args.output is None


def test_main_returns_zero_for_a_single_golden_case(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    exit_code = main(
        [
            "--case",
            "golden-wearable-tremor-monitor",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    assert output_path.exists()


def test_main_returns_nonzero_for_unknown_case() -> None:
    assert main(["--case", "does-not-exist"]) == 1


def test_cli_module_is_invocable_via_python_dash_m() -> None:
    src_roots = (
        "apps/api/src",
        "agents/embedded-systems/src",
        "packages/contracts/src",
        "packages/contracts/generated/python",
        "packages/model-gateway/src",
        "packages/observability/src",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(REPO_ROOT / root) for root in src_roots)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.embedded_project_initialization.runners.run_eval",
            "--case",
            "golden-wearable-tremor-monitor",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"passed": true' in completed.stdout


async def test_esp32_imu_golden_prompt_passes_fake_provider_quality_gates() -> None:
    case = EvalCase(
        id="golden-esp32-imu-vibration-monitor",
        suite="golden",
        category="esp32-imu-vibration-monitor",
        prompt=(
            "Build an ESP32-based vibration monitor using an MPU6050. "
            "It should stream acceleration telemetry and analyze stationary sensor noise "
            "to verify that accel_x RMS noise stays below 0.10 g."
        ),
        expected_outcome="supported",
    )
    result = await run_case(case)
    assert result["actualOutcome"] == "supported"
    assert result["structural"]["passed"] is True
    assert result["claims"]["passed"] is True
    assert result["passed"] is True
