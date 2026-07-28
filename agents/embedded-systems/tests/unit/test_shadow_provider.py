"""Shadow mode: fixture response is always authoritative; LLM path is private."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from fake_generation_scripts import WEARABLE_TREMOR_PROMPT, build_success_gateway
from nexus_embedded_systems.workflows.project_initialization.providers.base import (
    InitializationRequestContext,
)
from nexus_embedded_systems.workflows.project_initialization.providers.fixture_provider import (
    FixtureInitializationProvider,
)
from nexus_embedded_systems.workflows.project_initialization.providers.llm_provider import (
    LlmInitializationError,
    LlmInitializationProvider,
)
from nexus_embedded_systems.workflows.project_initialization.providers.shadow_provider import (
    ShadowInitializationProvider,
)
from nexus_embedded_systems.workflows.project_initialization.validation import (
    validate_initialization_result_schema,
)
from nexus_model_gateway import ModelPolicy

ROOT = Path(__file__).resolve().parents[4]
FIXTURES_ROOT = ROOT / "packages/contracts/examples/valid"
MODEL_POLICY = ModelPolicy(provider="fake", model="fake-model")


class _RaisingLlmProvider:
    async def initialize(
        self,
        message: str,
        autonomy_mode: str,
        request_context: InitializationRequestContext,
    ) -> dict[str, Any]:
        raise LlmInitializationError(
            code="MODEL_PROVIDER_UNAVAILABLE",
            message="Simulated LLM outage during shadow evaluation.",
        )


def _collect_ids(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        for value in node.values():
            _collect_ids(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_ids(item, found)
    elif (
        isinstance(node, str)
        and "_" in node
        and any(
            node.startswith(p)
            for p in ("proj_", "art_", "req_", "arch_", "node_", "edge_", "turn_", "act_")
        )
    ):
        found.add(node)


async def test_shadow_returns_fixture_result_when_llm_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    shadow = ShadowInitializationProvider(
        fixture_provider=FixtureInitializationProvider(fixtures_root=FIXTURES_ROOT),
        llm_provider=_RaisingLlmProvider(),  # type: ignore[arg-type]
    )
    context = InitializationRequestContext(request_id="req_shadow_1")

    with caplog.at_level(logging.WARNING, logger="nexus.embedded.project_initialization.shadow"):
        result = await shadow.initialize(WEARABLE_TREMOR_PROMPT, "collaborate", context)

    assert validate_initialization_result_schema(result) == []
    assert result["project"]["domain"] == "embedded-products"
    assert any(record.message == "shadow_llm_initialization_failed" for record in caplog.records)
    failed_record = next(
        r for r in caplog.records if r.message == "shadow_llm_initialization_failed"
    )
    assert failed_record.__dict__["error_code"] == "MODEL_PROVIDER_UNAVAILABLE"


async def test_shadow_returns_fixture_result_even_when_llm_succeeds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gateway = build_success_gateway()
    llm_provider = LlmInitializationProvider(gateway=gateway, model_policy=MODEL_POLICY)
    shadow = ShadowInitializationProvider(
        fixture_provider=FixtureInitializationProvider(fixtures_root=FIXTURES_ROOT),
        llm_provider=llm_provider,
    )
    context = InitializationRequestContext(request_id="req_shadow_2")

    with caplog.at_level(logging.INFO, logger="nexus.embedded.project_initialization.shadow"):
        result = await shadow.initialize(WEARABLE_TREMOR_PROMPT, "collaborate", context)

    assert validate_initialization_result_schema(result) == []
    succeeded_record = next(
        r for r in caplog.records if r.message == "shadow_llm_initialization_succeeded"
    )
    shadow_project_id = succeeded_record.__dict__["shadow_project_id"]

    # The user-visible fixture result must never carry the shadow LLM run's IDs.
    fixture_ids: set[str] = set()
    _collect_ids(result, fixture_ids)
    assert shadow_project_id not in fixture_ids
    assert result["project"]["projectId"] != shadow_project_id


async def test_shadow_fixture_ids_are_fresh_across_repeated_calls() -> None:
    shadow = ShadowInitializationProvider(
        fixture_provider=FixtureInitializationProvider(fixtures_root=FIXTURES_ROOT),
        llm_provider=_RaisingLlmProvider(),  # type: ignore[arg-type]
    )
    context = InitializationRequestContext(request_id="req_shadow_3")

    first = await shadow.initialize(WEARABLE_TREMOR_PROMPT, "collaborate", context)
    second = await shadow.initialize(WEARABLE_TREMOR_PROMPT, "collaborate", context)

    assert first["project"]["projectId"] != second["project"]["projectId"]

    first_ids: set[str] = set()
    second_ids: set[str] = set()
    _collect_ids(first, first_ids)
    _collect_ids(second, second_ids)
    assert first_ids.isdisjoint(second_ids)


async def test_shadow_llm_failure_never_propagates_to_caller() -> None:
    class _BoomProvider:
        async def initialize(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("unexpected LLM crash")

    shadow = ShadowInitializationProvider(
        fixture_provider=FixtureInitializationProvider(fixtures_root=FIXTURES_ROOT),
        llm_provider=_BoomProvider(),  # type: ignore[arg-type]
    )
    context = InitializationRequestContext(request_id="req_shadow_4")

    result = await shadow.initialize(WEARABLE_TREMOR_PROMPT, "collaborate", context)
    assert validate_initialization_result_schema(result) == []
