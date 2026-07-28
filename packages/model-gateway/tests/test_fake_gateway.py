"""Basic behavior of the scripted `FakeModelGateway`."""

from __future__ import annotations

import pytest
from nexus_model_gateway import FakeModelGateway, ModelGatewayError, ModelPolicy

POLICY = ModelPolicy(provider="fake", model="fake-model")


async def test_set_script_returns_scripted_output() -> None:
    gateway = FakeModelGateway()
    gateway.set_script("greet", lambda *_a: {"message": "hello"})

    result = await gateway.generate_structured(
        task_name="greet",
        system_instructions="say hello",
        input_payload={},
        output_schema={"type": "object"},
        model_policy=POLICY,
        prompt_id="test.greet.v1",
        prompt_version="1.0.0",
    )

    assert result.parsed_output == {"message": "hello"}
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.prompt_id == "test.greet.v1"
    assert result.prompt_version == "1.0.0"
    assert result.retry_count == 0


async def test_default_script_used_when_task_has_no_specific_script() -> None:
    gateway = FakeModelGateway(default_script=lambda *_a: {"ok": True})

    result = await gateway.generate_structured(
        task_name="unregistered-task",
        system_instructions="",
        input_payload={},
        output_schema={"type": "object"},
        model_policy=POLICY,
    )

    assert result.parsed_output == {"ok": True}


async def test_missing_script_raises_model_gateway_error() -> None:
    gateway = FakeModelGateway()

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.generate_structured(
            task_name="unregistered-task",
            system_instructions="",
            input_payload={},
            output_schema={"type": "object"},
            model_policy=POLICY,
        )

    assert exc_info.value.code == "MODEL_PROVIDER_UNAVAILABLE"


async def test_script_can_raise_model_gateway_error() -> None:
    gateway = FakeModelGateway()
    gateway.set_script(
        "flaky",
        lambda *_a: ModelGatewayError(code="MODEL_STRUCTURED_OUTPUT_INVALID", message="bad output"),
    )

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.generate_structured(
            task_name="flaky",
            system_instructions="",
            input_payload={},
            output_schema={"type": "object"},
            model_policy=POLICY,
        )

    assert exc_info.value.code == "MODEL_STRUCTURED_OUTPUT_INVALID"


async def test_call_log_records_every_invocation() -> None:
    gateway = FakeModelGateway()
    gateway.set_script("task-a", lambda *_a: {"a": 1})
    gateway.set_script("task-b", lambda *_a: {"b": 2})

    await gateway.generate_structured(
        task_name="task-a",
        system_instructions="instructions-a",
        input_payload={"x": 1},
        output_schema={"type": "object"},
        model_policy=POLICY,
    )
    await gateway.generate_structured(
        task_name="task-b",
        system_instructions="instructions-b",
        input_payload={"y": 2},
        output_schema={"type": "object"},
        model_policy=POLICY,
    )

    assert [entry["task_name"] for entry in gateway.call_log] == ["task-a", "task-b"]
    assert gateway.call_log[0]["input_payload"] == {"x": 1}
    assert gateway.call_log[1]["input_payload"] == {"y": 2}


async def test_request_ids_are_unique_per_call() -> None:
    gateway = FakeModelGateway(default_script=lambda *_a: {})

    first = await gateway.generate_structured(
        task_name="task",
        system_instructions="",
        input_payload={},
        output_schema={"type": "object"},
        model_policy=POLICY,
    )
    second = await gateway.generate_structured(
        task_name="task",
        system_instructions="",
        input_payload={},
        output_schema={"type": "object"},
        model_policy=POLICY,
    )

    assert first.request_id != second.request_id
